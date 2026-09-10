"""Bounded lexical import/call retrieval; never import the target package."""
import ast
import re
from pathlib import PurePosixPath

from . import evidence

MAX_SEED_FILES = 32
MAX_REFERENCES = 128


def seed_references(root, paths, seed_paths, task_text=""):
    sources = sorted(p for p in paths if p.endswith(".py"))
    cache, references, unresolved = {}, [], []

    def parse(path):
        if path in cache:
            return cache[path]
        if len(cache) >= MAX_SEED_FILES or evidence._safe_file(root, path)[1]:
            return None
        cache[path] = None
        try:
            tree = ast.parse(evidence._read_regular(root, path), filename=path)
            if evidence._ast_within_limits(tree):
                cache[path] = tree
        except (OSError, SyntaxError, ValueError, RecursionError):
            pass
        return cache[path]

    def module_paths(module):
        suffix = module.replace(".", "/")
        return [p for p in sources if p == suffix + ".py" or p.endswith("/" + suffix + ".py")
                or p == suffix + "/__init__.py" or p.endswith("/" + suffix + "/__init__.py")]

    queue = [(p, None, "public_reproducer_or_task_path") for p in sorted(seed_paths) if p.endswith('.py')][:MAX_SEED_FILES]
    # Exact identifiers inside backticks or call syntax, not fuzzy prose names.
    names = set(re.findall(r"`([A-Za-z_]\w*)`|\b([A-Za-z_]\w*)\s*\(", task_text[:65536]))
    task_names = {name for pair in names for name in pair if name}
    if task_names:
        queue.extend((path, None, 'task_named_symbol') for path in sources if path not in seed_paths)
    visited = set()
    depths = {path: 0 for path in seed_paths}
    while queue and len(references) < MAX_REFERENCES:
        path, symbol, via = queue.pop(0)
        if (path, symbol) in visited:
            continue
        visited.add((path, symbol))
        tree = parse(path)
        if tree is None:
            continue
        definitions = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
        focus = [n for n in definitions if n.name == symbol or (symbol is None and n.name in task_names)]
        for node in focus:
            references.append({"path": path, "start_line": node.lineno,
                               "end_line": node.lineno if isinstance(node, ast.ClassDef) else node.end_lineno,
                               "symbol": node.name, "via": via})
        nodes = [part for node in focus for part in ast.walk(node)] if focus else list(ast.walk(tree))
        calls = {evidence.symbol_name(n.func) for n in nodes if isinstance(n, ast.Call)}
        for node in ast.walk(tree):
            imported = []
            if isinstance(node, ast.ImportFrom):
                imported = [(node.module or '', alias.name, alias.asname or alias.name) for alias in node.names]
            elif isinstance(node, ast.Import):
                imported = [(alias.name, None, alias.asname or alias.name) for alias in node.names]
            for module, member, alias in imported:
                if depths.get(path, 0) >= 3:
                    continue
                used = sorted(c for c in calls if c and (c == alias or c.startswith(alias + ".")))
                if symbol == alias:
                    used.append(alias)
                if not used:
                    continue
                if isinstance(node, ast.ImportFrom) and node.level:
                    parent = PurePosixPath(path).parent
                    for _ in range(node.level - 1):
                        parent = parent.parent
                    stem = (parent / module.replace('.', '/')).as_posix()
                    matches = [p for p in sources if p in {stem + '.py', stem + '/__init__.py'}]
                else:
                    matches = module_paths(module)
                if len(matches) != 1:
                    unresolved.append({"path": path, "import": module, "reason": "ambiguous_or_external_import"})
                    continue
                target = member or used[0].removeprefix(alias + ".").split(".")[0]
                depths[matches[0]] = min(depths.get(matches[0], 3), depths.get(path, 0) + 1)
                queue.insert(0, (matches[0], target, "import_call:" + path))
                for call in used:
                    if member and call.startswith(alias + '.'):
                        queue.insert(0, (matches[0], call.split('.')[-1], "import_member_call:" + path))
        # Immediate exact same-file calls (including self.method) are useful
        # retrieval seeds, not asserted runtime call edges.
        for definition in definitions:
            if definition.name in calls or "self." + definition.name in calls or "cls." + definition.name in calls:
                queue.append((path, definition.name, "local_call:" + path))
    return references[:MAX_REFERENCES], {"seed_files_parsed": len(cache), "references": references[:MAX_REFERENCES],
                                         "unresolved": unresolved,
                                         "truncated": bool(queue) or len(references) > MAX_REFERENCES
                                         or len(cache) >= MAX_SEED_FILES}
