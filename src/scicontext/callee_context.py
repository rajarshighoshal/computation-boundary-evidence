"""Source-only helper retrieval for connected packets, not a runtime call graph.

Uses the existing reader and scope index. Bindings describe call syntax; they do
not claim value equality, execution, or scientific meaning.
"""
from __future__ import annotations

import ast
from collections import deque
from pathlib import PurePosixPath

from . import evidence

MAX_HELPER_DEPTH = 4
MAX_HELPER_BODIES = 32
MAX_HELPER_FILES = 24


def _owned_nodes(function):
    """Do not attribute a nested function's calls/returns to its enclosing one."""
    for statement in function.body:
        pending = [statement]
        while pending:
            node = pending.pop()
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
                continue
            yield node
            pending.extend(reversed(list(ast.iter_child_nodes(node))))


def _arguments(call, function):
    """Conservative syntactic actual/formal mapping, including defaults."""
    positional = function.args.posonlyargs + function.args.args
    names = [arg.arg for arg in positional + function.args.kwonlyargs]
    if any(isinstance(arg, ast.Starred) for arg in call.args) or any(k.arg is None for k in call.keywords):
        return [], "star_arguments_not_expanded"
    if len(call.args) > len(positional):
        return [], "variadic_or_invalid_arguments"
    values = {arg.arg: ast.unparse(value) for arg, value in zip(positional, call.args)}
    for keyword in call.keywords:
        if keyword.arg not in names or keyword.arg in values or keyword.arg in {a.arg for a in function.args.posonlyargs}:
            return [], "variadic_or_invalid_arguments"
        values[keyword.arg] = ast.unparse(keyword.value)
    defaults = dict(zip([a.arg for a in positional[-len(function.args.defaults):]], function.args.defaults))
    defaults.update({a.arg: value for a, value in zip(function.args.kwonlyargs, function.args.kw_defaults) if value is not None})
    bindings = []
    for name in names:
        if name in values:
            bindings.append({"parameter": name, "expression": values[name], "origin": "caller"})
        elif name in defaults:
            bindings.append({"parameter": name, "expression": ast.unparse(defaults[name]), "origin": "callee_default"})
        else:
            return [], "required_argument_missing"
    return bindings, "syntactic_only"


class HelperRetriever:
    def __init__(self, sources):
        self.sources = sources
        self.calls_cache = {}

    def _module(self, caller_path, module, level):
        parent = PurePosixPath(caller_path).parent
        if level:
            if level > len(parent.parts):
                return None
            bases = [parent.parents[level - 2] if level > 1 else parent]
        else:
            bases = [parent, *parent.parents]
        suffix = module.replace(".", "/")
        candidates = set()
        for base in bases:
            stem = base / suffix if suffix else base
            for path in (str(stem) + ".py", str(stem / "__init__.py")):
                if evidence._safe_file(self.sources.root, path)[1] is None:
                    candidates.add(path)
        return next(iter(candidates)) if len(candidates) == 1 else None

    def _target(self, path, call):
        tree, index = self.sources.trees[path]
        name = evidence.symbol_name(call.func)
        if not name:
            return None, "dynamic_callee"
        base, *attributes = name.split(".")
        scope = index.scopes.get(id(call))
        _, bindings = scope.lookup(base) if scope else (None, [])
        if not scope or scope.is_dynamic() or len(bindings) != 1 or bindings[0].branch:
            return None, "unresolved_or_rebound_callee"
        binding = bindings[0]
        # Match the exact scope binding's declaration, not a same-named function.
        declarations = [n for n in ast.walk(tree) if getattr(n, "lineno", None) == binding.line]
        local = [n for n in declarations if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == base]
        if local and not attributes:
            return (path, local[0]), None
        if binding.line > call.lineno:
            return None, "import_after_call"
        for declaration in declarations:
            if not isinstance(declaration, (ast.Import, ast.ImportFrom)):
                continue
            for alias in declaration.names:
                alias_name = alias.asname or (alias.name.split(".")[0] if isinstance(declaration, ast.Import) else alias.name)
                if alias_name != base:
                    continue
                if isinstance(declaration, ast.ImportFrom):
                    module, level = declaration.module or "", declaration.level
                    symbol = alias.name
                    if attributes:  # from . import helpers; helpers.calculate(...)
                        module = ".".join(filter(None, [module, symbol, *attributes[:-1]]))
                        symbol = attributes[-1]
                else:
                    level = 0
                    qualified = ([alias.name] + attributes) if alias.asname else name.split(".")
                    if len(qualified) < 2:
                        continue
                    module, symbol = ".".join(qualified[:-1]), qualified[-1]
                target = self._module(path, module, level)
                if target is None:
                    return None, "external_missing_or_ambiguous_module"
                if target not in self.sources.cache and len(self.sources.cache) >= MAX_HELPER_FILES:
                    return None, "helper_file_limit"
                _, _, _, problem = self.sources.load(target)
                if problem or target not in self.sources.trees:
                    return None, problem or "unsupported_helper_language"
                target_tree, target_index = self.sources.trees[target]
                module_scope = target_index.scopes[id(target_tree)]
                _, target_bindings = module_scope.lookup(symbol)
                definitions = [n for n in target_tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == symbol]
                if len(definitions) == 1 and len(target_bindings) == 1 and not target_bindings[0].branch and not module_scope.is_dynamic():
                    return (target, definitions[0]), None
                return None, "helper_definition_missing_or_rebound"
        return None, "unsupported_callee_binding"

    def _calls(self, body):
        if body["id"] in self.calls_cache:
            return self.calls_cache[body["id"]]
        path = body["path"]
        if path not in self.sources.trees:
            return [], []
        tree, index = self.sources.trees[path]
        functions = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.lineno == body["start_line"]]
        if not functions:
            return [], []
        records, gaps = [], []
        for call in (n for n in _owned_nodes(functions[0]) if isinstance(n, ast.Call)):
            site = {"path": path, "start_line": call.lineno, "start_col": call.col_offset,
                    "expression": ast.unparse(call), "branch": list(index.branches.get(id(call), ()))}
            target, problem = self._target(path, call)
            if target is None:
                gaps.append({"caller_body_id": body["id"], "call_site": site, "reason": problem})
                continue
            target_path, function = target
            if function.decorator_list or isinstance(function, ast.AsyncFunctionDef):
                gaps.append({"caller_body_id": body["id"], "call_site": site, "reason": "decorated_or_async_helper"})
                continue
            callee, problem = self.sources.body({"path": target_path, "start_line": function.lineno})
            if not callee:
                gaps.append({"caller_body_id": body["id"], "call_site": site, "reason": problem})
                continue
            arguments, status = _arguments(call, function)
            returns = [{"start_line": n.lineno, "expression": ast.unparse(n.value) if n.value else "None",
                        "branch": list(self.sources.trees[target_path][1].branches.get(id(n), ()))}
                       for n in _owned_nodes(function) if isinstance(n, ast.Return)]
            records.append((callee, {"caller_body_id": body["id"], "callee_body_id": callee["id"],
                "callee_symbol": function.name, "call_site": site, "argument_bindings": arguments,
                "binding_status": status, "return_sites": returns,
                "status": "static_candidate_not_runtime_dispatch"}))
        self.calls_cache[body["id"]] = records, gaps
        return records, gaps

    def expand(self, initial):
        bodies, links, gaps = dict(initial), [], []
        queue = deque((b, 0) for b in initial.values())
        visited = set()
        while queue:
            body, depth = queue.popleft()
            if body["id"] in visited:
                continue
            visited.add(body["id"])
            records, issues = self._calls(body)
            gaps.extend(issues)
            for callee, link in records:
                if callee["id"] not in bodies:
                    reason = "helper_depth_limit" if depth >= MAX_HELPER_DEPTH else "helper_body_limit" if len(bodies) >= MAX_HELPER_BODIES else None
                    if reason:
                        gaps.append({"caller_body_id": body["id"], "call_site": link["call_site"], "reason": reason})
                        continue
                    bodies[callee["id"]] = callee
                    queue.append((callee, depth + 1))
                if link not in links:
                    links.append(link)
        return bodies, links, gaps
