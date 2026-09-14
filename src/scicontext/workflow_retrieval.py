"""Task-workflow source references, not a claim about runtime dispatch or science."""
from __future__ import annotations

import ast
from collections import Counter, deque
import math
from pathlib import Path
import re

from . import evidence
from .language_frontends import source_language, _tree_sitter_entries, _group_comments

MAX_FILES = 48
MAX_REFERENCES = 128
MAX_DEPTH = 3


def retrieve(root, paths, seed_paths, task_text="", executed=()):
    """Lexical workflow retrieval; `executed` seeds traced (path, qualname) pairs.

    Follow the public workflow before the bulk of executed definitions, so
    import-time helpers cannot exhaust the parser allowance before the task's
    entry point. Execution seeds still cover dynamically reached definitions.
    This remains lexical analysis, not proof of runtime dispatch.
    """
    sources = sorted(p for p in paths if source_language(p))
    cache, references, unresolved = {}, [], []
    queue, visited, reference_keys = deque(), {}, {}

    def parse(path):
        if path in cache:
            return cache[path]
        if len(cache) >= MAX_FILES or evidence._safe_file(root, path)[1]:
            return None
        cache[path] = None
        try:
            raw = evidence._read_regular(root, path)
            language = source_language(path)
            if language == "python":
                tree = ast.parse(raw, filename=path)
                if not evidence._ast_within_limits(tree):
                    return None
                definitions = []
                def visit(node, owner=""):
                    for child in ast.iter_child_nodes(node):
                        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                            qualified = owner + "." + child.name if owner else child.name
                            definitions.append({"name": child.name, "qualified": qualified, "owner": owner,
                                "line": child.lineno, "end": child.end_lineno, "node": child,
                                "description": ast.get_docstring(child) or "",
                                "class": isinstance(child, ast.ClassDef)})
                            visit(child, qualified)
                        else:
                            visit(child, owner)
                visit(tree)
                value = {"language": language, "tree": tree, "definitions": definitions,
                         "scope_index": evidence._ScopeIndex(tree)}
            else:
                if language == "cython":
                    from .cython_frontend import cython_entries
                    entries, _, _ = cython_entries(path, raw)
                else:
                    entries, _, _ = _tree_sitter_entries(path, raw, language)
                entries = _group_comments(entries, raw)
                definitions = [{"name": e["native"]["function_name"], "qualified": e["native"]["function_name"],
                    "owner": "", "line": e["start_line"],
                    "end": max((c["end_line"] for c in entries if c.get("function_scope") == e["scope"]), default=e["end_line"]),
                    "scope": e["scope"], "entry": e, "class": False}
                    for e in entries if e["kind"] == "signature" and e.get("native", {}).get("function_name") and
                    not e["native"].get("declaration_only")]
                for definition in definitions:
                    comments = [e for e in entries if e["kind"] == "docstring" and
                                e.get("function_scope") == definition["scope"]]
                    definition["description"] = comments[0]["text"] if comments else ""
                value = {"language": language, "entries": entries, "definitions": definitions}
            cache[path] = value
        except (OSError, ValueError, SyntaxError, UnicodeError, RecursionError) as error:
            unresolved.append({"path": path, "reason": "workflow_parse_failure", "error": type(error).__name__})
        return cache[path]

    def enqueue(path, symbol, depth, via, caller=None):
        if path in sources and depth <= MAX_DEPTH:
            item = (path, symbol, depth, via, caller)
            # Finish the already-located call chain before unrelated seeds.
            (queue.appendleft if caller or via in {"used_import", "literal_source_path"} else queue.append)(item)
        elif path in sources:
            issue = {"path": path, "symbol": symbol, "reason": "workflow_depth_limit"}
            if issue not in unresolved:
                unresolved.append(issue)

    def file_targets(name, language=None):
        return [p for p in sources if (Path(p).stem.casefold() == name.casefold() if language == "fortran" else Path(p).stem == name)
                and (language is None or source_language(p) == language)]

    def calls_in(expression):
        if isinstance(expression, dict):
            if expression.get("kind") == "call":
                yield expression
            for child in expression.values():
                yield from calls_in(child)
        elif isinstance(expression, list):
            for child in expression:
                yield from calls_in(child)

    for path in sorted(seed_paths, key=lambda p: (not Path(p).stem.startswith("repro"), p)):
        enqueue(path, None, 0, "public_workflow")
    for name in re.findall(r"`([A-Za-z_]\w*)`", task_text[:65536]):
        for path in file_targets(name):
            enqueue(path, name, 0, "task_named_file_function")
    for path, symbol in executed:
        enqueue(path, symbol, 0, "executed_function")

    while queue and len(references) < MAX_REFERENCES:
        path, symbol, depth, via, caller = queue.popleft()
        data = parse(path)
        if data is None:
            continue
        definitions = data["definitions"]
        normal = str.casefold if data["language"] == "fortran" else str
        focus = [d for d in definitions if symbol is not None and normal(d["qualified"]) == normal(symbol)]
        if symbol is not None and not focus:
            unresolved.append({"path": path, "symbol": symbol, "reason": "requested_definition_not_found"})
            continue  # A missing symbol must not trigger exploration of the whole module.
        if symbol is None:
            focus = [d for d in definitions if d["name"] == Path(path).stem]
        for definition in focus:
            reference = {"path": path, "start_line": definition["line"],
                "end_line": definition["line"] if definition["class"] else definition["end"],
                "symbol": definition["qualified"], "via": via, "depth": depth,
                "description": definition.get("description", "")[:8000],
                "priority": 0 if caller else 1, "caller": caller,
                "callers": [caller] if caller else [],
                "runtime_invocation": "not_established"}
            key = (path, definition["line"])
            if key not in reference_keys:
                reference_keys[key] = reference
                references.append(reference)
            else:
                previous = reference_keys[key]
                previous["depth"] = min(depth, previous["depth"])
                previous["priority"] = min(reference["priority"], previous["priority"])
                if caller and caller not in previous["callers"] and len(previous["callers"]) < MAX_REFERENCES:
                    previous["callers"].append(caller)
                    if previous["caller"] is None:
                        previous["caller"] = caller
                elif caller and caller not in previous["callers"]:
                    issue = {"path": path, "symbol": symbol, "reason": "workflow_callsite_limit"}
                    if issue not in unresolved:
                        unresolved.append(issue)
        visit_key = (path, focus[0]["qualified"] if len(focus) == 1 else symbol)
        if visited.get(visit_key, MAX_DEPTH + 1) <= depth:
            continue
        visited[visit_key] = depth
        if data["language"] == "python":
            if focus:
                nodes = [n for d in focus if not d["class"] for n in ast.walk(d["node"])]
            else:
                nodes = list(ast.walk(data["tree"])) if via == "public_workflow" else [n for n in data["tree"].body if not isinstance(n, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))]
                if via != "public_workflow":
                    nodes = [n for top in nodes for n in ast.walk(top)]
            calls = [n for n in nodes if isinstance(n, ast.Call)]
            imported_classes = []
            scope_index = data["scope_index"]
            def imported_at(node, alias, qualified):
                scope = scope_index.scopes.get(id(node))
                return scope is not None and scope.imported_names(node.lineno).get(alias) == qualified
            for node in ast.walk(data["tree"]):
                if not isinstance(node, ast.ImportFrom) or node.level or not node.module:
                    continue
                suffix = node.module.replace(".", "/")
                matches = [p for p in sources if p.endswith("/" + suffix + ".py") or p == suffix + ".py"]
                if len(matches) != 1:
                    continue
                for alias in node.names:
                    imported_name = node.module + "." + alias.name
                    if not any(isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load) and n.id == (alias.asname or alias.name)
                               and imported_at(n, n.id, imported_name) for n in nodes):
                        continue
                    target = parse(matches[0])
                    if not target:
                        continue
                    defs = [d for d in target["definitions"] if d["qualified"] == alias.name]
                    enqueue(matches[0], alias.name, depth + 1, "used_import", None)
                    for call in calls:
                        if isinstance(call.func, ast.Name) and call.func.id == (alias.asname or alias.name) and imported_at(call, call.func.id, imported_name):
                            enqueue(matches[0], alias.name, depth + 1, "import_call_candidate",
                                {"path": path, "start_line": call.lineno, "start_col": call.col_offset, "callee": call.func.id})
                    imported_classes.extend((matches[0], d["qualified"]) for d in defs if d["class"])
            for call in calls:
                name = evidence.symbol_name(call.func)
                if not name:
                    continue
                site = {"path": path, "start_line": call.lineno, "start_col": call.col_offset, "callee": name}
                scope = scope_index.scopes.get(id(call))
                _, bindings = scope.lookup(name) if scope and isinstance(call.func, ast.Name) else (None, [])
                local = [d for d in definitions if d["name"] == name and len(bindings) == 1 and d["line"] == bindings[0].line
                         and not bindings[0].imported and not bindings[0].branch and not scope.is_dynamic()]
                for definition in local:
                    enqueue(path, definition["qualified"], depth + 1, "same_file_call", site)
                if isinstance(call.func, ast.Attribute):
                    if isinstance(call.func.value, ast.Name) and call.func.value.id in {"self", "cls"}:
                        owners = [d for d in definitions if not d["class"] and d["owner"] and d["line"] <= call.lineno <= d["end"]]
                        if owners:
                            owner = min(owners, key=lambda d: d["end"] - d["line"])["owner"]
                            method = owner + "." + call.func.attr
                            # Match Python's lexical spelling of private names.
                            if any(d["qualified"] == method for d in definitions):
                                enqueue(path, method, depth + 1, "same_class_method_candidate", site)
                    for target, owner in imported_classes:
                        definition = owner + "." + call.func.attr
                        if any(d["qualified"] == definition for d in parse(target)["definitions"]):
                            enqueue(target, definition, depth + 1, "imported_class_method_candidate", site)
            for node in nodes:
                if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
                    continue
                value = node.value
                generated_key = any(isinstance(parent, ast.Dict) and any(key is node and isinstance(body, ast.Constant) and
                    isinstance(body.value, str) and body.value.lstrip().startswith("function ")
                    for key, body in zip(parent.keys, parent.values)) for parent in nodes)
                if source_language(value) and "\n" not in value and not generated_key:
                    for target in sources:
                        if target == value or target.endswith("/" + value):
                            enqueue(target, None, depth, "literal_source_path")
                if "\n" in value and ("function " in value or re.search(r";\s*\n", value)):
                    for match in re.finditer(r"(?<![\w.])([A-Za-z_]\w*)\s*\(", value):
                        line_start = value.rfind("\n", 0, match.start()) + 1
                        if value[line_start:match.start()].lstrip().startswith(("function ", "%")):
                            continue  # A generated definition/comment is not a call.
                        for target in file_targets(match[1], "matlab"):
                            enqueue(target, match[1], depth + 1, "embedded_call_spelling",
                                {"path": path, "start_line": node.lineno, "start_col": node.col_offset,
                                 "callee": match[1], "embedded_string": True})
        else:
            scopes = {d["scope"] for d in focus}
            for entry in data["entries"]:
                if scopes and entry.get("function_scope") not in scopes:
                    continue
                for call in calls_in(entry.get("native_expression")):
                    name = call["callee"]
                    if not name.isidentifier():
                        continue
                    site = {"path": path, "start_line": entry["start_line"], "start_col": entry["start_col"], "callee": name}
                    local = [d for d in definitions if normal(d["name"]) == normal(name)]
                    for definition in local:
                        enqueue(path, definition["qualified"], depth + 1, "native_local_call_candidate", site)
                    if not local:
                        for target in file_targets(name, data["language"]):
                            enqueue(target, name, depth + 1, "native_file_function_candidate", site)
    query = task_text
    for path in ("paper.md", "README.md", "source/README.md"):
        if path in paths and not evidence._safe_file(root, path)[1]:
            try:
                query += "\n" + evidence._read_regular(root, path).decode("utf-8")[:12000]
            except (OSError, ValueError, UnicodeError):
                pass
    def terms(text):
        return Counter(re.findall(r"[a-z]{3,}", text.lower()))
    documents = [terms(r["description"]) for r in references]
    frequency = Counter(t for document in documents for t in document)
    idf = {t: math.log((1 + len(documents)) / (1 + n)) + 1 for t, n in frequency.items()}
    def vector(tokens):
        return {t: (1 + math.log(n)) * idf[t] for t, n in tokens.items() if t in idf}
    q = vector(terms(query)); qnorm = math.sqrt(sum(v*v for v in q.values()))
    for reference, document in zip(references, documents):
        v = vector(document); norm = math.sqrt(sum(x*x for x in v.values()))
        reference["relevance_score"] = round(sum(q.get(t, 0)*x for t, x in v.items()) / (norm*qnorm), 8) if norm*qnorm else 0.0
    references.sort(key=lambda r: (-r["relevance_score"], r["priority"], r["depth"], r["path"], r["start_line"], r["via"]))
    return references[:MAX_REFERENCES], {"references": references[:MAX_REFERENCES], "unresolved": unresolved,
        "files_parsed": len(cache), "truncated": bool(queue) or len(cache) >= MAX_FILES or any(u["reason"].endswith("_limit") for u in unresolved),
        "ranking": "TF-IDF cosine of source docstrings against public task and scientific documentation; exact workflow evidence supplies candidates",
        "scope": "Lexical workflow retrieval, including ambiguous candidates; not runtime dispatch or value-flow proof"}
