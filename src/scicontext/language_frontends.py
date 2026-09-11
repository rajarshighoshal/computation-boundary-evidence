"""Existing-parser frontends for source/interface evidence, not scientific guesses.

Native expressions are normalised as syntax and never sent through Python AST.
Their physical meaning belongs to the shared scientific-context interpretation.
"""
from __future__ import annotations

import hashlib
import importlib
from collections import defaultdict, deque
from pathlib import Path

from . import evidence
from .io import digest_json


SUFFIXES = {
    ".py": "python", ".pyx": "cython", ".pxd": "cython", ".pxi": "cython",
    ".c": "c", ".cpp": "cpp", ".cc": "cpp", ".cxx": "cpp", ".hpp": "cpp",
    ".hxx": "cpp", ".hh": "cpp", ".h": "cpp", ".m": "matlab",
    ".f": "fortran", ".for": "fortran", ".f77": "fortran", ".f90": "fortran",
    ".f95": "fortran", ".f03": "fortran", ".f08": "fortran",
}


def source_language(path: str) -> str | None:
    suffix = Path(path).suffix
    return "cpp" if suffix == ".C" else SUFFIXES.get(suffix.lower())


def _walk(node):
    yield node
    for child in node.named_children:
        yield from _walk(child)


def _text(node):
    return node.text.decode("utf-8") if node is not None else ""


def _child(node, *kinds):
    return next((c for c in node.named_children if c.type in kinds), None) if node else None


def _declarator_name(node):
    if node is None:
        return None
    if node.type in {"identifier", "field_identifier", "qualified_identifier", "name", "operator_name"}:
        return _text(node)
    nested = node.child_by_field_name("declarator")
    if nested:
        return _declarator_name(nested)
    return _declarator_name(node.named_children[0]) if node.named_children else None


def _function(node, language):
    if language in {"c", "cpp"} and node.type == "function_definition":
        declarator = node.child_by_field_name("declarator")
        fn = next((n for n in _walk(declarator) if n.type == "function_declarator" and
                   n.child_by_field_name("declarator") is not None and n.child_by_field_name("declarator").type in
                   {"identifier", "qualified_identifier", "field_identifier", "operator_name", "destructor_name"}), None) if declarator else None
        params = fn.child_by_field_name("parameters") if fn else None
        return (_declarator_name(fn), list(params.named_children) if params else [],
                node.child_by_field_name("body"), [])
    if language == "fortran" and node.type in {"function", "subroutine", "program"}:
        header = _child(node, node.type + "_statement")
        name = _text(header.child_by_field_name("name")) if header else ""
        params = header.child_by_field_name("parameters") if header else None
        result = _child(header, "function_result")
        outputs = [_text(n) for n in result.named_children] if result else [name] if node.type == "function" else []
        return name, list(params.named_children) if params else [], None, outputs
    if language == "matlab" and node.type == "function_definition":
        args, out = _child(node, "function_arguments"), _child(node, "function_output")
        outputs = [_text(n) for n in _walk(out) if n.type == "identifier"] if out else []
        return _text(node.child_by_field_name("name")), list(args.named_children) if args else [], _child(node, "block"), outputs
    return None


def _expression(node, language):
    if node is None:
        return None
    result = {"text": _text(node), "span": [node.start_byte, node.end_byte]}
    if node.type in {"identifier", "name"}:
        return {**result, "kind": "name", "name": _text(node)}
    if node.type in {"number", "number_literal", "string_literal", "string", "true", "false", "boolean_literal"}:
        return {**result, "kind": "literal"}
    left, right = node.child_by_field_name("left"), node.child_by_field_name("right")
    if left is not None and right is not None and node.type not in {"assignment", "assignment_expression", "assignment_statement"}:
        operator = node.child_by_field_name("operator")
        spelling = _text(operator) if operator else node.text[left.end_byte - node.start_byte:right.start_byte - node.start_byte].decode().strip()
        return {**result, "kind": "binary", "operator": spelling,
                "left": _expression(left, language), "right": _expression(right, language)}
    if node.type in {"call_expression", "function_call", "subroutine_call"}:
        callee = (node.child_by_field_name("function") or node.child_by_field_name("name")
                  or node.child_by_field_name("subroutine") or (node.named_children[0] if node.named_children else None))
        args = node.child_by_field_name("arguments") or _child(node, "argument_list", "arguments")
        return {**result, "kind": "call", "callee": _text(callee),
                "callee_kind": callee.type if callee else None,
                "receiver": _expression(callee.named_children[0], language) if callee and
                    callee.type in {"field_expression", "member_expression", "derived_type_member_expression"} and callee.named_children else None,
                "index_ambiguous": language in {"matlab", "fortran"} and node.type != "subroutine_call",
                "arguments": [_expression(n, language) for n in args.named_children] if args else []}
    if node.type in {"parenthesized_expression", "parenthesis"} and len(node.named_children) == 1:
        return _expression(node.named_children[0], language)
    if node.type in {"unary_expression", "unary_operator", "unary_math_expression"}:
        operand = node.child_by_field_name("argument") or (node.named_children[-1] if node.named_children else None)
        return {**result, "kind": "unary", "operator": _text(node.child_by_field_name("operator")) or
                (node.text[:operand.start_byte - node.start_byte].decode().strip() if operand else ""),
                "operand": _expression(operand, language)}
    return {**result, "kind": "unknown", "syntax_kind": node.type,
            "children": [_expression(n, language) for n in node.named_children]}


def _scope_and_branch(node, language, functions):
    ancestors, cursor = [], node
    while cursor is not None:
        ancestors.append(cursor)
        cursor = cursor.parent
    chain, branch, function_scope = ["<module>"], [], None
    for ancestor in reversed(ancestors):
        fn = functions.get(ancestor.id)
        if fn:
            chain.append(chain[-1] + f".{fn[0]}@{ancestor.start_point.row + 1}:{ancestor.start_byte}")
            function_scope = chain[-1]
        elif ancestor.type in {"namespace_definition", "module", "class_specifier", "class_definition",
                               "struct_specifier", "union_specifier"}:
            name = _text(ancestor.child_by_field_name("name"))
            chain.append(chain[-1] + f".{ancestor.type}:{name}@{ancestor.start_byte}")
        elif ancestor.type == "compound_statement" and ancestor.parent is not None and ancestor.parent.id not in functions:
            chain.append(chain[-1] + f".block@{ancestor.start_byte}")
        if ancestor.type in {"if_statement", "if_block", "for_statement", "while_statement", "do_loop", "switch_statement", "try_statement"}:
            child = node
            while child.parent is not None and child.parent.id != ancestor.id:
                child = child.parent
            arm = "else" if "else" in child.type else "body"
            branch.append(f"{ancestor.type}@{ancestor.start_byte}:{arm}")
        elif ancestor.type in {"else_clause", "elseif_clause", "case_statement", "catch_clause"}:
            branch.append(f"{ancestor.type}@{ancestor.start_byte}")
    return chain, branch, function_scope


def _tree_sitter_entries(path, raw, language):
    from tree_sitter import Language, Parser
    grammar = importlib.import_module("tree_sitter_" + language)
    tree = Parser(Language(grammar.language())).parse(raw)
    nodes = list(_walk(tree.root_node))
    functions = {n.id: f for n in nodes if (f := _function(n, language)) and f[0]}
    digest = hashlib.sha256(raw).hexdigest()
    entries, unsupported = [], []

    def add(node, kind, *, symbol=None, expression=None, native=None, scope_node=None):
        chain, branch, function_scope = _scope_and_branch(scope_node or node, language, functions)
        identity = [path, digest, node.start_byte, node.end_byte, kind, symbol]
        entry = {"id": "ev_" + digest_json(identity)[:24], "path": path, "sha256": digest,
            "start_line": node.start_point.row + 1, "end_line": node.end_point.row + 1,
            "start_col": node.start_point.column, "end_col": node.end_point.column,
            "column_encoding": "utf-8-bytes", "scope": chain[-1], "scope_chain": chain,
            "function_scope": function_scope, "branch": branch, "kind": kind, "language": language,
            "text": _text(node), "expression": None, "expression_text": None,
            "imports": {}, "entity_symbols": [symbol] if symbol else [],
            "native_expression": expression, "native": native or {}, "limitations": []}
        if path.lower().endswith(".h"):
            entry["limitations"].append("Header parsed as C++-compatible syntax; C versus C++ dialect is not established.")
        entries.append(entry)
        return entry

    for node in nodes:
        if node.type == "ERROR" or node.is_missing:
            unsupported.append({"path": path, "reason": "parse_error", "language": language,
                                "start_line": node.start_point.row + 1, "end_line": node.end_point.row + 1})
            continue
        if node.has_error:
            continue
        fn = functions.get(node.id)
        if fn:
            name, params, body, outputs = fn
            signature = (node.child_by_field_name("declarator") or
                         _child(node, "function_statement", "subroutine_statement", "program_statement") or node)
            entry = add(signature, "signature", symbol=name, scope_node=node,
                native={"function_name": name, "interface_only": True,
                        "return_type": _text(node.child_by_field_name("type"))})
            if language == "matlab" and body:
                entry["text"] = raw[node.start_byte:body.start_byte].decode("utf-8").rstrip()
                entry["end_line"] = entry["start_line"] + len(entry["text"].splitlines()) - 1
                entry["end_col"] = len(entry["text"].splitlines()[-1].encode())
            for param in params:
                symbol = _declarator_name(param.child_by_field_name("declarator")) if language in {"c", "cpp"} else _text(param)
                if symbol:
                    add(param, "parameter", symbol=symbol, scope_node=param,
                        native={"declaration_text": _text(param)})
            if outputs:
                end = _child(node, "function_output") if language == "matlab" else node.named_children[-1]
                for symbol in outputs:
                    add(end, "return", expression={"kind": "name", "name": symbol, "text": symbol,
                        "span": [end.start_byte, end.end_byte]}, scope_node=node,
                        native={"implicit_output": symbol, "binding_at": "function_exit",
                                "order_start": [node.end_point.row + 1, node.end_point.column]})
            continue
        if node.type in {"comment", "comment_block"}:
            add(node, "docstring")
        elif node.type in {"init_declarator", "variable_declaration"} or node.type == "declaration" and language in {"c", "cpp"}:
            declarators = ([node.child_by_field_name("declarator")] if node.type == "init_declarator" else
                           node.children_by_field_name("declarator"))
            for decl in declarators:
                if decl is None or node.type == "declaration" and decl.type == "init_declarator":
                    continue
                symbol = _declarator_name(decl)
                if symbol:
                    fn_decl = next((n for n in _walk(decl) if n.type == "function_declarator" and
                        n.child_by_field_name("declarator") is not None and n.child_by_field_name("declarator").type in
                        {"identifier", "qualified_identifier", "field_identifier", "operator_name", "destructor_name"}), None)
                    if language in {"c", "cpp"} and fn_decl is not None:
                        add(node, "signature", symbol=symbol, native={"function_name": symbol,
                            "declaration_only": True, "declaration_text": _text(node)})
                        continue
                    value = node.child_by_field_name("value") or decl.child_by_field_name("value") or decl.child_by_field_name("right")
                    add(node, "assignment" if value else "declaration", symbol=symbol,
                        expression=_expression(value, language),
                        native={"declaration_text": _text(node), "declaration": True,
                                "type_qualifiers": [_text(c) for c in node.named_children if c.type == "type_qualifier"],
                                "type_annotation": language == "fortran"})
        elif node.type in {"assignment_expression", "assignment_statement", "assignment"}:
            left, right = node.child_by_field_name("left"), node.child_by_field_name("right")
            symbol = _text(left) if left and left.type == "identifier" else None
            add(node, "assignment", symbol=symbol, expression=_expression(right, language),
                native={"target": _text(left), "operator": _text(node.child_by_field_name("operator")) or "=",
                        "nonlocal_write": symbol is None, "writes_root": _declarator_name(left) or ""})
        elif node.type == "update_expression":
            target = node.child_by_field_name("argument") or _child(node, "identifier", "subscript_expression", "field_expression")
            add(node, "assignment", native={"target": _text(target),
                "operator": _text(node.child_by_field_name("operator")), "nonlocal_write": True,
                "writes_root": _declarator_name(target) or ""})
        elif node.type == "return_statement":
            add(node, "return", expression=_expression(node.named_children[0], language) if node.named_children else None)
        elif node.type in {"call_expression", "function_call", "subroutine_call"}:
            # Calls embedded in another expression are already represented there.
            if node.parent and node.parent.type in {"expression_statement", "block", "subroutine", "function", "translation_unit", "source_file"}:
                add(node, "call", expression=_expression(node, language))
    declarations = [e for e in entries if e["kind"] in {"parameter", "declaration"} or e["native"].get("declaration")]
    for entry in entries:
        if language == "fortran" and entry["kind"] == "parameter":
            matches = [d for d in declarations if d["kind"] == "declaration" and d["scope"] == entry["scope"] and
                       {n.casefold() for n in d["entity_symbols"]} & {n.casefold() for n in entry["entity_symbols"]}]
            if matches:
                entry["native"]["declaration_text"] = "\n".join(dict.fromkeys(d["text"] for d in matches))
                entry["native"]["type_qualifiers"] = list(dict.fromkeys(q for d in matches for q in d["native"].get("type_qualifiers", [])))
        if language not in {"c", "cpp"} or entry["kind"] != "assignment" or entry["native"].get("declaration"):
            continue
        for scope in reversed(entry["scope_chain"]):
            owners = [d for d in declarations if d["scope"] == scope and _position(d) < _position(entry) and
                      set(d["entity_symbols"]) & set(entry["entity_symbols"])]
            if owners:
                entry["native"]["binding_scope"] = scope
                break
    return entries, unsupported, tree.root_node.has_error


def _group_comments(entries, raw):
    """One contiguous scientific passage is one entry, not one per comment line."""
    lines = raw.decode("utf-8").splitlines(keepends=True)
    grouped = []
    for entry in sorted(entries, key=lambda e: (e["start_line"], e["start_col"], e["id"])):
        previous = grouped[-1] if grouped else None
        if (previous and previous["kind"] == entry["kind"] == "docstring" and
                previous["scope"] == entry["scope"] and previous["end_line"] < entry["start_line"] and
                not "".join(lines[previous["end_line"]:entry["start_line"] - 1]).strip()):
            previous.update(end_line=entry["end_line"], end_col=entry["end_col"])
            segment = lines[previous["start_line"] - 1:previous["end_line"]]
            segment[-1] = segment[-1].encode()[:previous["end_col"]].decode()
            segment[0] = segment[0].encode()[previous["start_col"]:].decode()
            previous["text"] = "".join(segment)
            previous["id"] = "ev_" + digest_json([previous["path"], previous["sha256"],
                previous["start_line"], previous["start_col"], previous["end_line"], previous["end_col"], "comment_block"])[:24]
        else:
            grouped.append(entry)
    return grouped


def _position(entry):
    return tuple(entry.get("native", {}).get("order_start", (entry["start_line"], entry["start_col"])))


def _select_entries(entries, limit, refs):
    """Balance scientific passages, interfaces and computation; disclose lost definitions."""
    focused = {e.get("function_scope") or e["scope"] for e in entries if any(
        e["start_line"] <= r["end_line"] and e["end_line"] >= r["start_line"] for r in refs)}
    queues = defaultdict(deque)
    outputs = {(e.get("function_scope"), n.casefold() if e["language"] == "fortran" else n)
               for e in entries if e["kind"] == "parameter" and any(
                   q.replace(" ", "").casefold() in {"intent(out)", "intent(inout)"}
                   for q in e.get("native", {}).get("type_qualifiers", [])) for n in e["entity_symbols"]}
    outputs.update((e.get("function_scope"), e["native"]["implicit_output"].casefold() if e["language"] == "fortran" else e["native"]["implicit_output"])
                   for e in entries if e.get("native", {}).get("implicit_output"))
    def computational_priority(entry):
        target = entry.get("native", {}).get("writes_root", "")
        if entry["language"] == "fortran":
            target = target.casefold()
        if entry["kind"] == "return":
            return 0
        if (entry.get("function_scope"), target) in outputs:
            return 1
        return 2
    for entry in entries:
        category = ("interface" if entry["kind"] in {"signature", "parameter"} else
                    "documentation" if entry["kind"] == "docstring" else
                    "declaration" if entry["kind"] == "declaration" else "computation")
        focus = 0 if (entry.get("function_scope") or entry["scope"]) in focused else 1
        queues[(focus, category)].append(entry)
    for focus in (0, 1):
        queues[(focus, "computation")] = deque(sorted(queues[(focus, "computation")], key=computational_priority))
        for category in ("interface", "documentation", "computation", "declaration"):
            by_scope = defaultdict(deque)
            for entry in queues[(focus, category)]:
                by_scope[entry.get("function_scope") or entry["scope"]].append(entry)
            balanced = deque()
            while any(by_scope.values()):
                for group in by_scope.values():
                    if group:
                        balanced.append(group.popleft())
            queues[(focus, category)] = balanced
    selected = []
    for focus in (0, 1):
        # Uninitialised declarations cannot consume the entire computational slice.
        categories = ("interface", "documentation", "computation", "declaration")
        while len(selected) < limit and any(queues[(focus, c)] for c in categories):
            for category in categories:
                if queues[(focus, category)] and len(selected) < limit:
                    selected.append(queues[(focus, category)].popleft())
    kept = {e["id"] for e in selected}
    omitted = [e for e in entries if e["id"] not in kept and
               e["kind"] in {"parameter", "assignment", "declaration"}]
    for entry in selected:
        def names(value):
            if isinstance(value, dict):
                if value.get("kind") == "name":
                    yield value["name"]
                for child in value.values():
                    yield from names(child)
            elif isinstance(value, list):
                for child in value:
                    yield from names(child)
        normal = str.casefold if entry["language"] == "fortran" else str
        used = {normal(n) for n in names(entry.get("native_expression"))}
        used.update(normal(n) for n in entry.get("entity_symbols", []))
        barriers = set()
        for lost in omitted:
            if _position(lost) >= _position(entry):
                continue
            symbols = {normal(n) for n in lost.get("entity_symbols", [])}
            symbols.add(normal(lost.get("native", {}).get("writes_root", "")))
            visible = lost.get("native", {}).get("binding_scope", lost["scope"]) in entry["scope_chain"] or (
                lost.get("native", {}).get("nonlocal_write") and
                lost.get("function_scope") == entry.get("function_scope"))
            if visible:
                barriers.update(used & symbols)
        if barriers:
            entry["native"]["omitted_prior_bindings"] = sorted(barriers)
    return sorted(selected, key=lambda e: (e["start_line"], e["start_col"], e["id"]))


def extract_native_evidence(root: Path, paths: list[str], *, max_entries=128, references=None) -> dict:
    entries, skipped, parsed = [], [], 0
    truncated = False
    for path in paths:
        language = source_language(path)
        if language in {None, "python"}:
            skipped.append({"path": path, "reason": "unsupported_native_language"})
            continue
        _, problem = evidence._safe_file(root, path)
        if problem:
            skipped.append({"path": path, "reason": problem})
            continue
        try:
            raw = evidence._read_regular(root, path)
            if len(raw) > evidence.MAX_FILE_BYTES:
                raise ValueError("source_file_size_limit")
            if language == "cython":
                from .cython_frontend import cython_entries
                current, issues, partial = cython_entries(path, raw)
            else:
                current, issues, partial = _tree_sitter_entries(path, raw, language)
            parsed += 1
            skipped.extend(issues)
            if partial:
                skipped.append({"path": path, "reason": "partial_parse", "language": language})
            current = _group_comments(current, raw)
            refs = [r for r in references or [] if r.get("path") == path]
            remaining = max(0, max_entries - len(entries))
            truncated |= len(current) > remaining
            if len(current) > remaining:
                skipped.append({"path": path, "reason": "native_entry_limit", "available": len(current),
                    "retained": remaining, "selection": "reference_scopes_then_balanced_evidence_kinds"})
            entries.extend(_select_entries(current, remaining, refs))
        except (OSError, ValueError, UnicodeError, RecursionError) as error:
            skipped.append({"path": path, "reason": "parse_or_read_failure", "error": type(error).__name__})
    return {"entries": entries, "coverage": {"files_considered": len(paths), "files_parsed": parsed,
        "entries": len(entries), "expressions": sum(e.get("native_expression") is not None for e in entries),
        "supported_expressions": 0, "entries_truncated": truncated, "skipped": skipped}}
