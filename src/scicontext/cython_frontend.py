"""Cython's own parser, with compile-time evaluation and includes disabled."""
from __future__ import annotations

import hashlib
from io import StringIO
import tokenize

from .io import digest_json


def _children(node):
    for field in getattr(node, "child_attrs", ()):
        value = getattr(node, field, None)
        for child in value if isinstance(value, (list, tuple)) else [value]:
            if child is not None and hasattr(child, "pos"):
                yield child


def _positions(node):
    values = [node.pos[1:]] if getattr(node, "pos", None) else []
    for child in _children(node):
        values.extend(_positions(child))
    return values


def _name(node):
    while node is not None:
        if hasattr(node, "name") and isinstance(node.name, str):
            return node.name
        node = getattr(node, "base", None)
    return None


def _callee(node):
    if type(node).__name__ == "NameNode":
        return str(node.name)
    if type(node).__name__ == "AttributeNode":
        base = _callee(node.obj)
        return base + "." + node.attribute if base else None
    return None


def _target_root(node):
    if type(node).__name__ == "NameNode":
        return str(node.name)
    for field in ("base", "obj"):
        child = getattr(node, field, None)
        if child is not None:
            return _target_root(child)
    return ""


def _expression(node, lines):
    if node is None:
        return None
    cls = type(node).__name__
    points = _positions(node)
    start, end = min(points), max(points)
    text = "\n".join(lines[start[0] - 1:end[0]])
    base = {"span": [*start, *end], "text": text, "position_kind": "cython_ast_line_envelope"}
    if cls == "NameNode":
        return {**base, "kind": "name", "name": str(node.name)}
    if cls in {"IntNode", "FloatNode", "ImagNode", "UnicodeNode", "BytesNode", "BoolNode", "NoneNode"}:
        return {**base, "kind": "literal", "text": repr(getattr(node, "value", None))}
    if hasattr(node, "operand1") and hasattr(node, "operand2"):
        return {**base, "kind": "binary", "operator": node.operator,
                "left": _expression(node.operand1, lines), "right": _expression(node.operand2, lines)}
    if cls in {"SimpleCallNode", "GeneralCallNode"}:
        args = node.args if cls == "SimpleCallNode" else getattr(node.positional_args, "args", [])
        result = {**base, "kind": "call", "callee": _callee(node.function) or "<dynamic-call>",
                  "arguments": [_expression(a, lines) for a in args], "index_ambiguous": False,
                  "receiver": _expression(node.function.obj, lines) if type(node.function).__name__ == "AttributeNode" else None}
        if cls == "GeneralCallNode" and node.keyword_args is not None:
            result["arguments"].extend(_expression(item.value, lines) for item in
                                      getattr(node.keyword_args, "key_value_pairs", []))
            result["keywords_present"] = True
        return result
    if hasattr(node, "operand"):
        return {**base, "kind": "unary", "operator": getattr(node, "operator", cls),
                "operand": _expression(node.operand, lines)}
    return {**base, "kind": "unknown", "syntax_kind": cls,
            "children": [_expression(child, lines) for child in _children(node)]}


def cython_entries(path: str, raw: bytes):
    from Cython.Compiler import Errors, Parsing, TreeFragment
    from Cython.Compiler.Scanning import PyrexScanner, StringSourceDescriptor

    source = raw.decode("utf-8")
    lines = source.splitlines()
    digest = hashlib.sha256(raw).hexdigest()
    module = "scicontext_" + hashlib.sha256(path.encode()).hexdigest()[:16]
    context = TreeFragment.StringParseContext(module, cpp=True)
    position = (module, 1, 0)
    scope = context.find_module(module, pos=position, need_pxd=False)
    scanner = PyrexScanner(StringIO(source), StringSourceDescriptor(path, source),
        source_encoding="UTF-8", scope=scope, context=context, initial_pos=position)
    scanner.compile_time_eval = False
    issues, passages = [], []
    first = True
    try:
        for token in tokenize.generate_tokens(StringIO(source).readline):
            if token.type == tokenize.COMMENT or first and token.type == tokenize.STRING:
                passages.append(token)
            if token.type == tokenize.NEWLINE:
                first = True
            elif token.type not in {tokenize.INDENT, tokenize.DEDENT, tokenize.COMMENT, tokenize.NL}:
                if first and token.type == tokenize.NAME and token.string in {"DEF", "IF", "ELIF", "ELSE", "include"}:
                    issues.append({"path": path, "reason": "cython_compile_time_region_not_evaluated",
                                   "start_line": token.start[0], "text": token.line.rstrip()})
                first = False
    except (tokenize.TokenError, IndentationError) as error:
        issues.append({"path": path, "reason": "cython_lexical_diagnostic", "message": str(error)})
    entries, regions, function_scopes = [], [], set()

    def add(node, kind, chain, branch, *, symbol=None, expression=None, native=None, header_end=None, span=None):
        points = list(span) if span else _positions(node)
        start, end = min(points), max(points)
        if header_end is not None:
            end = (max(start[0], header_end), 0)
        text = "\n".join(lines[start[0] - 1:end[0]])
        entry = {"id": "ev_" + digest_json([path, digest, start, end, kind, symbol])[:24],
            "path": path, "sha256": digest, "start_line": start[0], "end_line": end[0],
            "start_col": 0, "end_col": len(lines[end[0] - 1].encode()) if lines else 0,
            "column_encoding": "utf-8-bytes", "scope": chain[-1], "scope_chain": list(chain),
            "function_scope": next((s for s in reversed(chain) if s in function_scopes), None), "branch": list(branch),
            "kind": kind, "language": "cython", "text": text, "expression": None,
            "expression_text": None, "native_expression": expression, "imports": {},
            "native": {"span_kind": "ast_line_envelope_not_exclusive_token_span", "order_start": list(start), **(native or {})},
            "entity_symbols": [symbol] if symbol else [],
            "limitations": ["Cython AST positions form a line envelope; closing delimiters may extend beyond it."]}
        entries.append(entry)

    def visit(node, chain, branch):
        cls = type(node).__name__
        if cls in {"CClassDefNode", "PyClassDefNode", "CppClassNode"}:
            name = (getattr(node, "as_name", None) or node.class_name) if cls == "CClassDefNode" else node.name
            nested = [*chain, chain[-1] + f".class:{name}@{node.pos[1]}:{node.pos[2]}"]
            points = _positions(node)
            regions.append((min(points), max(points), nested))
            body = list(getattr(node, "attributes", []) or []) if cls == "CppClassNode" else [node.body]
            body_start = min((min(_positions(n))[0] for n in body if n is not None), default=node.pos[1] + 1)
            add(node, "signature", nested, branch, symbol=name, header_end=body_start - 1,
                native={"class_name": name, "interface_kind": "class", "docstring": str(getattr(node, "doc", "") or "")})
            for child in body:
                if child is not None:
                    visit(child, nested, branch)
            return
        if cls in {"CFuncDefNode", "DefNode"}:
            declarator = getattr(node, "declarator", None)
            fn_decl = declarator
            while fn_decl is not None and type(fn_decl).__name__ != "CFuncDeclaratorNode":
                fn_decl = getattr(fn_decl, "base", None)
            name = _name(declarator) if declarator else node.name
            nested = [*chain, chain[-1] + f".{name}@{node.pos[1]}:{node.pos[2]}"]
            function_scopes.add(nested[-1])
            points = _positions(node)
            regions.append((min(points), max(points), nested))
            body_start = min(_positions(node.body))[0] if node.body else node.pos[1] + 1
            add(node, "signature", nested, [], symbol=name, header_end=body_start - 1,
                native={"function_name": name, "interface_only": True, "docstring": str(node.doc) if node.doc else None})
            args = fn_decl.args if fn_decl else node.args
            for arg in args:
                symbol = _name(getattr(arg, "declarator", None)) or getattr(arg, "name", None)
                base_type = getattr(arg, "base_type", None)
                inferred_untyped = not symbol and type(getattr(arg, "declarator", None)).__name__ == "CNameDeclaratorNode" and \
                    bool(getattr(base_type, "name", None)) and not getattr(base_type, "is_basic_c_type", False)
                if inferred_untyped:
                    symbol = base_type.name
                if symbol:
                    add(arg, "parameter", nested, [], symbol=symbol,
                        native={"declaration_text": "untyped parameter" if inferred_untyped else
                                str(getattr(base_type, "name", "unknown"))})
            if node.body:
                visit(node.body, nested, [])
            return
        if cls in {"SingleAssignmentNode", "InPlaceAssignmentNode"}:
            lhs = getattr(node, "lhs", None)
            symbol = lhs.name if type(lhs).__name__ == "NameNode" else None
            add(node, "assignment", chain, branch, symbol=symbol, expression=_expression(node.rhs, lines),
                native={"target": symbol or "<compound-target>", "nonlocal_write": symbol is None,
                        "writes_root": _target_root(lhs),
                        "operator": "=" if cls == "SingleAssignmentNode" else node.operator + "="})
            return
        if cls == "ReturnStatNode":
            add(node, "return", chain, branch, expression=_expression(node.value, lines))
            return
        if cls == "ExprStatNode":
            add(node, "call", chain, branch, expression=_expression(node.expr, lines))
            return
        if cls == "CVarDefNode":
            for decl in node.declarators:
                name = _name(decl)
                if not name:
                    continue
                fn = decl
                while fn is not None and type(fn).__name__ != "CFuncDeclaratorNode":
                    fn = getattr(fn, "base", None)
                if fn is not None:
                    add(node, "signature", chain, branch, symbol=name,
                        native={"function_name": name, "declaration_only": True})
                else:
                    default = getattr(decl, "default", None)
                    add(node, "assignment" if default else "declaration", chain, branch, symbol=name,
                        expression=_expression(default, lines), native={"declaration": True,
                        "declaration_text": str(getattr(node.base_type, "name", "unknown"))})
            return
        control = cls in {"IfStatNode", "IfClauseNode", "ForInStatNode", "ForFromStatNode", "WhileStatNode", "TryExceptStatNode"}
        if cls in {"IfClauseNode", "WhileStatNode"} and getattr(node, "condition", None) is not None:
            add(node.condition, "predicate", chain, branch, expression=_expression(node.condition, lines),
                native={"condition": True, "condition_for": f"{cls}@{node.pos[1]}:{node.pos[2]}"})
        nested_branch = [*branch, f"{cls}@{node.pos[1]}:{node.pos[2]}"] if control else branch
        for child in _children(node):
            visit(child, chain, nested_branch)

    try:
        with Errors.local_errors(ignore=True) as errors:
            tree = Parsing.p_module(scanner, path.lower().endswith(".pxd"), module, ctx=Parsing.Ctx())
        if errors:
            issues.extend({"path": path, "reason": "cython_parse_diagnostic", "message": str(error)} for error in errors)
        visit(tree, ["<module>"], [])
        for token in passages:
            owners = [chain for start, end, chain in regions if start <= token.start <= end]
            chain = max(owners, key=len) if owners else ["<module>"]
            add(None, "docstring", chain, [], span=(token.start, token.end))
        return entries, issues, bool(errors)
    except Errors.CompileError as error:
        issues.append({"path": path, "reason": "cython_parse_error", "message": error.message_only})
        return entries, issues, True
