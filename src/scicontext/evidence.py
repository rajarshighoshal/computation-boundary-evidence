"""Read-only, bounded source evidence for the allowed task-visible repository.

This index is syntactic. It records lexical scopes and control-flow branches,
not a whole-program dataflow proof or the scientific correctness of task code.
The caller must supply an already isolated public-task root; path filtering is
defence in depth, not a replacement for the benchmark information boundary.
"""

from __future__ import annotations

import ast
import hashlib
import io
import json
import os
import re
import stat
import tokenize
from dataclasses import dataclass, field
from pathlib import Path

from .expressions import expression_from_ast, symbol_name

MAX_FILE_BYTES = 1_048_576
MAX_FILE_AST_NODES = 50_000
MAX_FILE_AST_DEPTH = 128
MAX_WALK_DIRECTORIES = 2000
_BLOCKED_PARTS = {
    "auth", "authentication", "credentials", "secrets", "verifier", "verifiers",
    "private", "private_tests", "private-tests", "hidden_tests", "hidden-tests",
    "gold", "gold_patch", "gold_patches", "__pycache__", "node_modules",
    "site-packages", "venv", "env", "dist", "build",
}
_BLOCKED_NAMES = {"auth.json", "credentials.json", "credentials.toml", "token", "tokens"}
_KNOWN_CALLS = {
    "math.sqrt": "sqrt", "numpy.sum": "sum",
    "numpy.sqrt": "sqrt", "numpy.matmul": "matmul", "numpy.linalg.norm": "norm",
}
_LIMITATIONS = [
    "Syntactic index only; references do not establish complete dataflow or scientific meaning.",
    "Arithmetic operators may be overloaded; operand types and runtime library identity are not proved.",
    "Import resolution is conservative lexical analysis; runtime monkey-patching and external mutation are not modelled.",
    "Static subscript and attribute symbols are opaque references, not alias or shape inference.",
    "Only caller-supplied public task roots are permitted; filename filtering cannot identify every private artifact.",
]


class _FileTooLarge(ValueError):
    pass


def _blocked(path: Path) -> bool:
    # The extractor may write this task-root subtree. Its probe products are
    # observations, never evidence of the original candidate implementation.
    # A nested scientific package named source/outputs remains eligible.
    if path.parts[:1] == ("outputs",):
        return True
    for component in path.parts:
        lowered = component.casefold()
        if lowered.startswith(".") or lowered in _BLOCKED_PARTS or lowered in _BLOCKED_NAMES:
            return True
        if re.search(r"(^|[_-])(auth|authentication|tokens?|verifier|credentials|secrets|private)([_\-.]|$)", lowered):
            return True
    return path.suffix.casefold() in {".pem", ".key", ".p12", ".pfx"}


def _valid_limit(value: int, name: str) -> None:
    if type(value) is not int or value < 1:
        raise ValueError(f"{name} must be a positive integer")


def _safe_file(root: Path, relative: str) -> tuple[Path | None, str | None]:
    if not isinstance(relative, str) or not relative or "\x00" in relative:
        return None, "invalid_path"
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts or "\\" in relative:
        return None, "path_outside_root"
    if _blocked(path):
        return None, "excluded_path"
    candidate = root
    try:
        for part in path.parts:
            candidate = candidate / part
            if candidate.is_symlink():
                return None, "symlink"
        if not candidate.resolve(strict=True).is_relative_to(root):
            return None, "path_outside_root"
        if not candidate.is_file():
            return None, "not_regular_file"
    except (OSError, ValueError, RuntimeError):
        return None, "unreadable_path"
    return candidate, None


def _span_text(source: str, node: ast.AST) -> str:
    return ast.get_source_segment(source, node) or ""


def _read_regular(root: Path, relative: str) -> bytes:
    """Open each path component without following a symlink, including races.

    Evidence extraction runs on POSIX benchmark/host environments. ``dir_fd``
    pins each directory while walking so replacing a parent path cannot redirect
    the read outside the public root. Nonblocking open avoids hanging on a FIFO
    swapped in between validation and open.
    """
    descriptors = []
    try:
        directory = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        descriptors.append(directory)
        parts = Path(relative).parts
        for part in parts[:-1]:
            directory = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
            descriptors.append(directory)
        descriptor = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
        descriptors.append(descriptor)
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise ValueError("source is not a regular file")
        if metadata.st_size > MAX_FILE_BYTES:
            raise _FileTooLarge("file exceeds source byte limit")
        chunks = []
        remaining = MAX_FILE_BYTES + 1
        while remaining:
            chunk = os.read(descriptor, min(remaining, 65536))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


def _ast_within_limits(tree: ast.AST) -> bool:
    stack = [(tree, 0)]
    count = 0
    while stack:
        node, depth = stack.pop()
        count += 1
        if count > MAX_FILE_AST_NODES or depth > MAX_FILE_AST_DEPTH:
            return False
        stack.extend((child, depth + 1) for child in ast.iter_child_nodes(node))
    return True


@dataclass
class _Binding:
    line: int
    branch: tuple[str, ...]
    imported: str | None = None


@dataclass
class _Scope:
    name: str
    kind: str
    parent: _Scope | None = None
    bindings: dict[str, list[_Binding]] = field(default_factory=dict)
    dynamic: bool = False

    def bind(self, name: str, line: int, branch: tuple[str, ...], imported: str | None = None) -> None:
        self.bindings.setdefault(name, []).append(_Binding(line, branch, imported))

    def lookup(self, name: str) -> tuple[_Scope | None, list[_Binding]]:
        if name in self.bindings:
            return self, self.bindings[name]
        if self.parent is not None:
            return self.parent.lookup(name)
        return None, []

    def is_dynamic(self) -> bool:
        return self.dynamic or (self.parent is not None and self.parent.is_dynamic())

    def imported_names(self, line: int) -> dict[str, str]:
        names = self.parent.imported_names(line) if self.parent else {}
        for name, bindings in self.bindings.items():
            names.pop(name, None)
            if len(bindings) == 1 and bindings[0].imported is not None \
                    and not bindings[0].branch and bindings[0].line <= line:
                names[name] = bindings[0].imported
        return {} if self.is_dynamic() else names

    def calls(self, line: int) -> dict[str, str]:
        result = {}
        if self.is_dynamic():
            return result
        for alias, imported in self.imported_names(line).items():
            for qualified, canonical in _KNOWN_CALLS.items():
                if qualified == imported:
                    result[alias] = canonical
                elif qualified.startswith(imported + "."):
                    result[alias + qualified[len(imported):]] = canonical
        return result


class _ScopeIndex(ast.NodeVisitor):
    """Map AST nodes to lexical scopes/branches before resolving any call."""

    def __init__(self, tree: ast.AST):
        self.scope = _Scope("<module>", "module")
        self.module = self.scope
        self.branch: tuple[str, ...] = ()
        self.scopes: dict[int, _Scope] = {}
        self.branches: dict[int, tuple[str, ...]] = {}
        self.visit(tree)

    def visit(self, node: ast.AST):
        self.scopes[id(node)] = self.scope
        self.branches[id(node)] = self.branch
        return super().visit(node)

    def _bind_target(self, node: ast.AST) -> None:
        if isinstance(node, ast.Name):
            self.scope.bind(node.id, node.lineno, self.branch)
        elif isinstance(node, (ast.Tuple, ast.List)):
            for child in node.elts:
                self._bind_target(child)
        elif isinstance(node, ast.Starred):
            self._bind_target(node.value)
        elif isinstance(node, (ast.Attribute, ast.Subscript)):
            base = node.value
            while isinstance(base, (ast.Attribute, ast.Subscript)):
                base = base.value
            if isinstance(base, ast.Name):
                # An attribute mutation may overwrite an imported operation.
                self.scope.bind(base.id, node.lineno, self.branch)

    def _function(self, node: ast.FunctionDef | ast.AsyncFunctionDef):
        self.scope.bind(node.name, node.lineno, self.branch)
        for child in [*node.decorator_list, *node.args.defaults,
                      *(value for value in node.args.kw_defaults if value is not None)]:
            self.visit(child)
        parent = self.scope
        lexical_parent = parent.parent if parent.kind == "class" else parent
        self.scope = _Scope(f"{parent.name}.{node.name}@{node.lineno}", "function", lexical_parent)
        saved_branch, self.branch = self.branch, ()
        self.scopes[id(node)] = self.scope
        args = [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
        args.extend(arg for arg in [node.args.vararg, node.args.kwarg] if arg is not None)
        for arg in args:
            self.scope.bind(arg.arg, node.lineno, ())
        for statement in node.body:
            self.visit(statement)
        self.scope, self.branch = parent, saved_branch

    visit_FunctionDef = _function
    visit_AsyncFunctionDef = _function

    def visit_ClassDef(self, node: ast.ClassDef):
        self.scope.bind(node.name, node.lineno, self.branch)
        for child in [*node.bases, *node.decorator_list]:
            self.visit(child)
        parent = self.scope
        self.scope = _Scope(f"{parent.name}.{node.name}@{node.lineno}", "class", parent)
        saved_branch, self.branch = self.branch, ()
        self.scopes[id(node)] = self.scope
        for statement in node.body:
            self.visit(statement)
        self.scope, self.branch = parent, saved_branch

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            name = alias.asname or alias.name.split(".")[0]
            imported = alias.name if alias.asname else alias.name.split(".")[0]
            self.scope.bind(name, node.lineno, self.branch, imported)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        for alias in node.names:
            if alias.name == "*":
                self.scope.dynamic = True
            else:
                imported = f"{node.module}.{alias.name}" if node.module and not node.level else None
                self.scope.bind(alias.asname or alias.name, node.lineno, self.branch, imported)

    def visit_Assign(self, node: ast.Assign):
        for target in node.targets:
            self._bind_target(target)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign):
        self._bind_target(node.target)
        self.generic_visit(node)

    visit_AugAssign = visit_AnnAssign

    def visit_NamedExpr(self, node: ast.NamedExpr):
        self._bind_target(node.target)
        self.generic_visit(node)

    def visit_Delete(self, node: ast.Delete):
        for target in node.targets:
            self._bind_target(target)

    def visit_Global(self, node: ast.Global):
        for name in node.names:
            self.scope.bind(name, node.lineno, self.branch)

    visit_Nonlocal = visit_Global

    def visit_Lambda(self, node: ast.Lambda):
        # Lambda/local comprehension expressions are unsupported, rather than
        # incorrectly assigning their variables to the enclosing scope.
        return

    def _comprehension(self, node: ast.AST):
        if any(isinstance(child, ast.NamedExpr) for child in ast.walk(node)):
            self.scope.dynamic = True

    visit_ListComp = _comprehension
    visit_SetComp = _comprehension
    visit_DictComp = _comprehension
    visit_GeneratorExp = _comprehension

    def visit_Call(self, node: ast.Call):
        if isinstance(node.func, ast.Name) and node.func.id in {"exec", "eval", "globals", "locals", "setattr", "delattr"}:
            self.scope.dynamic = True
        self.generic_visit(node)

    def _branch_visit(self, nodes: list[ast.AST], label: str):
        previous = self.branch
        self.branch = (*previous, label)
        for child in nodes:
            self.visit(child)
        self.branch = previous

    def visit_If(self, node: ast.If):
        self.visit(node.test)
        self._branch_visit(node.body, f"if@{node.lineno}:body")
        self._branch_visit(node.orelse, f"if@{node.lineno}:else")

    def visit_While(self, node: ast.While):
        self.visit(node.test)
        self._branch_visit(node.body, f"while@{node.lineno}:body")
        self._branch_visit(node.orelse, f"while@{node.lineno}:else")

    def visit_For(self, node: ast.For | ast.AsyncFor):
        self._bind_target(node.target)
        self.visit(node.iter)
        self._branch_visit(node.body, f"for@{node.lineno}:body")
        self._branch_visit(node.orelse, f"for@{node.lineno}:else")

    visit_AsyncFor = visit_For

    def visit_With(self, node: ast.With | ast.AsyncWith):
        for item in node.items:
            if item.optional_vars is not None:
                self._bind_target(item.optional_vars)
            self.visit(item.context_expr)
        self._branch_visit(node.body, f"with@{node.lineno}:body")

    visit_AsyncWith = visit_With

    def visit_Try(self, node: ast.Try):
        self._branch_visit(node.body, f"try@{node.lineno}:body")
        for index, handler in enumerate(node.handlers):
            if handler.name:
                self.scope.bind(handler.name, handler.lineno, self.branch)
            self._branch_visit(handler.body, f"try@{node.lineno}:except{index}")
        self._branch_visit(node.orelse, f"try@{node.lineno}:else")
        self._branch_visit(node.finalbody, f"try@{node.lineno}:finally")

    visit_TryStar = visit_Try

    def visit_Match(self, node):
        self.visit(node.subject)
        for index, case in enumerate(node.cases):
            for part in ast.walk(case.pattern):
                for name in (getattr(part, "name", None), getattr(part, "rest", None)):
                    if name:
                        self.scope.bind(name, node.lineno, self.branch)
            if case.guard:
                self.visit(case.guard)
            self._branch_visit(case.body, f"match@{node.lineno}:case{index}")


def _expression_symbols(expression: dict) -> list[str]:
    result = []
    stack = [expression]
    while stack:
        node = stack.pop()
        if node["op"] == "symbol":
            result.append(node["name"])
        stack.extend(reversed(node.get("args", [])))
    return list(dict.fromkeys(result))


def _has_unknown(expression: dict | None) -> bool:
    if expression is None:
        return False
    stack = [expression]
    while stack:
        node = stack.pop()
        if node["op"] == "unknown":
            return True
        stack.extend(node.get("args", []))
    return False


def _file_entries(path: str, raw: bytes, source: str, tree: ast.AST, limit: int,
                  references: list[dict] | None = None) -> tuple[list[dict], bool]:
    digest = hashlib.sha256(raw).hexdigest()
    index = _ScopeIndex(tree)
    entries = []
    candidates = []
    docstrings = {
        id(node.body[0]) for node in ast.walk(tree)
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        and node.body and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Constant) and isinstance(node.body[0].value.value, str)
    }
    for node in ast.walk(tree):
        if id(node) not in index.scopes:
            continue
        kind, expression_node = None, None
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            kind, expression_node = "assignment", node.value
        elif isinstance(node, ast.AugAssign):
            kind = "augmented_assignment"
            # Do not turn a += b into a = a + b: in-place and ordinary
            # operators can differ. The RHS remains separately inspectable.
            expression_node = node.value
        elif isinstance(node, ast.Return):
            kind, expression_node = "return", node.value
        elif isinstance(node, ast.Assert):
            kind, expression_node = "assertion", node.test
        elif isinstance(node, ast.Compare):
            kind, expression_node = "comparison", node
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            kind = "import"
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            kind = "signature"
        elif id(node) in docstrings:
            kind = "docstring"
        if kind is not None:
            candidates.append((node, kind, expression_node))
    candidates.sort(key=lambda item: (item[0].lineno, item[0].col_offset, item[1]))
    regions = []
    for ref in references or []:
        if ref.get("path") != path:
            continue
        start, end = ref.get("start_line"), ref.get("end_line")
        if type(start) is not int or type(end) is not int or start < 1 or end < start:
            continue
        enclosing = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                     and n.lineno <= start <= end <= n.end_lineno]
        owner = min(enclosing, key=lambda n: n.end_lineno - n.lineno) if enclosing else None
        regions.append((start, end, owner.lineno if owner else max(1, start - 3),
                        owner.end_lineno if owner else end + 3))
    if regions:
        def priority(item):
            node = item[0]
            direct = any(node.lineno <= end and node.end_lineno >= start for start, end, _, _ in regions)
            nearby = any(lo <= node.lineno <= hi for _, _, lo, hi in regions)
            return (0 if direct and item[1] != "signature" else 1 if nearby else 2,
                    node.lineno, node.col_offset, item[1])
        candidates.sort(key=priority)
    entry_nodes = {}
    for node, kind, expression_node in candidates[:limit]:
        scope = index.scopes[id(node)]
        line = node.lineno
        source_text = _span_text(source, node)
        start_col, end_col = node.col_offset, node.end_col_offset
        end_line = node.end_lineno
        if kind == "signature":
            # Token-aware header boundary preserves annotations/defaults with
            # colons. Using the whole definition would inflate tiny indexes.
            source_lines = source.splitlines(keepends=True)
            header_lines = source_lines[line - 1:]
            header = "".join(header_lines)
            header = header.encode("utf-8")[start_col:].decode("utf-8")
            try:
                depth = 0
                for token in tokenize.generate_tokens(io.StringIO(header).readline):
                    if token.type == tokenize.OP:
                        if token.string in "([{":
                            depth += 1
                        elif token.string in ")]}":
                            depth -= 1
                        elif token.string == ":" and depth == 0:
                            row, col = token.end
                            end_line = line + row - 1
                            header_line = header.splitlines()[row - 1]
                            end_col = len(header_line[:col].encode("utf-8")) + (start_col if row == 1 else 0)
                            segment_lines = source_lines[line - 1:end_line]
                            segment_lines[-1] = segment_lines[-1].encode("utf-8")[:end_col].decode("utf-8")
                            segment_lines[0] = segment_lines[0].encode("utf-8")[start_col:].decode("utf-8")
                            source_text = "".join(segment_lines)
                            break
            except (tokenize.TokenError, IndentationError, UnicodeError):
                # Whole definition is still an exact span if tokenization
                # cannot establish a smaller header boundary.
                pass
        expression = expression_from_ast(expression_node, source, calls=scope.calls(line)) \
            if expression_node is not None else None
        identity = [path, digest, line, start_col, end_line, end_col, kind]
        identifier = "ev_" + hashlib.sha256(json.dumps(identity, separators=(",", ":")).encode()).hexdigest()[:24]
        entry = {
            "id": identifier, "path": path, "sha256": digest,
            "start_line": line, "end_line": end_line,
            "start_col": start_col, "end_col": end_col,
            "column_encoding": "utf-8-bytes", "scope": scope.name,
            "branch": list(index.branches[id(node)]), "kind": kind,
            "text": source_text, "expression": expression,
            "expression_text": _span_text(source, expression_node) if expression_node is not None else None,
            "expression_span": {
                "start_line": expression_node.lineno, "end_line": expression_node.end_lineno,
                "start_col": expression_node.col_offset, "end_col": expression_node.end_col_offset,
            } if expression_node is not None else None,
            "imports": scope.imported_names(line), "limitations": [],
        }
        if expression is not None:
            binding_scopes = {}
            for name in _expression_symbols(expression):
                base = re.split(r"[.\[]", name, maxsplit=1)[0]
                bound_scope, _ = scope.lookup(base)
                binding_scopes[name] = bound_scope.name if bound_scope is not None else None
            entry["symbol_scopes"] = binding_scopes
        if isinstance(node, ast.Assign):
            entry["targets"] = [_span_text(source, target) for target in node.targets]
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
            entry["targets"] = [_span_text(source, node.target)]
        if isinstance(node, ast.AugAssign):
            entry["limitations"].append("In-place operator semantics are not expanded; expression is RHS only.")
        if isinstance(node, ast.Compare):
            entry["comparison_operators"] = [type(op).__name__ for op in node.ops]
            entry["comparison_operands"] = [
                expression_from_ast(operand, source, calls=scope.calls(line))
                for operand in [node.left, *node.comparators]
            ]
            entry["limitations"].append("Comparison is recorded, not evaluated or converted to an arithmetic equality.")
        if _has_unknown(expression):
            entry["limitations"].append("Expression contains unsupported or unresolved syntax.")
        if entry["branch"]:
            entry["limitations"].append("Evidence is branch-dependent; execution of this branch is not established.")
        entries.append(entry)
        entry_nodes[entry["id"]] = node
    definitions = {}
    for entry in entries:
        for target in entry.get("targets", []):
            if target.isidentifier():
                definitions[(entry["scope"], target, entry["start_line"])] = entry["id"]
    for entry in entries:
        node = entry_nodes[entry["id"]]
        scope = index.scopes[id(node)]
        # AST reads preserve operands even when the expression parser cannot
        # represent an operation. Names are exact, never similarity matches.
        value = getattr(node, "value", None)
        nested_binding = isinstance(value, ast.AST) and any(
            isinstance(part, (ast.Lambda, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp))
            for part in ast.walk(value)
        )
        reads = sorted({part.id for part in ast.walk(value) if isinstance(part, ast.Name)
                        and isinstance(part.ctx, ast.Load)}) if isinstance(value, ast.AST) else []
        if isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name):
            reads = sorted(set(reads) | {node.target.id})
        entry["reads"] = reads
        links = []
        for name in reads:
            owner, bindings = scope.lookup(name)
            prior = [binding for binding in bindings if binding.line < node.lineno]
            latest = max(prior, key=lambda binding: binding.line) if prior else None
            reason = "no_local_definition"
            definition = None
            if nested_binding:
                # Reads below these constructs do not all belong to the
                # statement's scope. This local index deliberately declines
                # to resolve them rather than borrowing an outer namesake.
                reason = "nested_binding_construct"
            elif any(binding.line == node.lineno for binding in bindings):
                # Bindings currently retain lines, not execution positions.
                # A same-line assignment can precede this read (including
                # one omitted by entry budgeting); do not select an older one.
                reason = "same_line_binding_ambiguity"
            elif owner is not scope:
                reason = "nonlocal_or_external"
            elif latest is not None:
                definition = definitions.get((scope.name, name, latest.line))
                if scope.is_dynamic() or latest.branch or entry["branch"]:
                    reason, definition = "branch_or_dynamic_binding", None
                elif latest.imported is not None:
                    reason, definition = "import_or_external_call", None
                elif definition is None:
                    reason = "parameter_alias_or_unindexed_definition"
                else:
                    reason = None
            links.append({"name": name, "scope": owner.name if owner else None,
                          "definition_id": definition, "status": "resolved" if definition else "unresolved",
                          "reason": reason})
        entry["local_dependencies"] = links
        entry["unresolved_operations"] = sorted({"call" for part in ast.walk(value) if isinstance(part, ast.Call)}
                                                | {"alias_or_index" for part in ast.walk(value)
                                                   if isinstance(part, (ast.Attribute, ast.Subscript))}) if isinstance(value, ast.AST) else []
    return entries, len(candidates) > limit


def extract_evidence(
    root: Path, paths: list[str] | None = None, *, max_files: int = 200, max_entries: int = 2000,
    references: list[dict] | None = None
) -> dict:
    """Index bounded Python evidence without following symlinks or executing code."""
    _valid_limit(max_files, "max_files")
    _valid_limit(max_entries, "max_entries")
    root = Path(root).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("root must be a directory")
    coverage = {
        "files_considered": 0, "files_parsed": 0, "entries": 0,
        "expressions": 0, "supported_expressions": 0,
        "files_truncated": False, "entries_truncated": False,
        "directories_truncated": False, "skipped": [], "limitations": list(_LIMITATIONS),
    }
    selected = []
    if paths is not None:
        if not isinstance(paths, list) or any(not isinstance(path, str) for path in paths):
            raise ValueError("paths must be a list of relative path strings")
        selected = sorted(set(paths))
        if len(selected) > max_files:
            coverage["files_truncated"] = True
            selected = selected[:max_files]
    else:
        directories = 0
        for current, dirs, files in os.walk(root, followlinks=False):
            directories += 1
            if directories > MAX_WALK_DIRECTORIES:
                coverage["directories_truncated"] = True
                break
            relative_dir = Path(current).relative_to(root)
            accepted_dirs = []
            for name in sorted(dirs):
                relative = relative_dir / name
                if _blocked(relative):
                    coverage["skipped"].append({"path": relative.as_posix(), "reason": "excluded_directory"})
                elif (root / relative).is_symlink():
                    coverage["skipped"].append({"path": relative.as_posix(), "reason": "symlink"})
                else:
                    accepted_dirs.append(name)
            dirs[:] = accepted_dirs
            for name in sorted(files):
                relative = (relative_dir / name).as_posix()
                if len(selected) >= max_files:
                    coverage["files_truncated"] = True
                    break
                selected.append(relative)
            if coverage["files_truncated"]:
                break
    entries = []
    for relative in selected:
        if len(entries) >= max_entries:
            coverage["entries_truncated"] = True
            break
        coverage["files_considered"] += 1
        path, problem = _safe_file(root, relative)
        if problem is not None:
            coverage["skipped"].append({"path": relative, "reason": problem})
            continue
        if path.suffix.casefold() != ".py":
            coverage["skipped"].append({"path": relative, "reason": "unsupported_language"})
            continue
        try:
            if path.stat().st_size > MAX_FILE_BYTES:
                coverage["skipped"].append({"path": relative, "reason": "file_size_limit"})
                continue
            raw = _read_regular(root, relative)
            if len(raw) > MAX_FILE_BYTES:
                coverage["skipped"].append({"path": relative, "reason": "file_size_limit"})
                continue
            encoding, _ = tokenize.detect_encoding(io.BytesIO(raw).readline)
            source = raw.decode(encoding)
            tree = ast.parse(source, filename=relative)
            if not _ast_within_limits(tree):
                coverage["skipped"].append({"path": relative, "reason": "ast_size_or_depth_limit"})
                continue
            file_entries, truncated = _file_entries(relative, raw, source, tree, max_entries - len(entries), references)
        except _FileTooLarge:
            coverage["skipped"].append({"path": relative, "reason": "file_size_limit"})
            continue
        except (OSError, SyntaxError, UnicodeError, LookupError, ValueError, RecursionError, MemoryError) as exc:
            coverage["skipped"].append({"path": relative, "reason": "parse_or_read_failure", "error_type": type(exc).__name__})
            continue
        entries.extend(file_entries)
        coverage["files_parsed"] += 1
        coverage["entries_truncated"] |= truncated
    coverage["entries"] = len(entries)
    coverage["expressions"] = sum(entry["expression"] is not None for entry in entries)
    coverage["supported_expressions"] = sum(
        entry["expression"] is not None and not _has_unknown(entry["expression"]) for entry in entries
    )
    return {"schema_version": "1.0", "entries": entries, "coverage": coverage}
