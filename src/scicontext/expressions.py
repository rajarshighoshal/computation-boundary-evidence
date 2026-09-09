"""Bounded expression syntax and ordered, explicitly non-semantic alignment.

No task code is imported or evaluated. ``parse_expression`` accepts the explicit
formula conventions ``sum``, ``sqrt``, ``matmul`` and ``norm``. Source indexing
uses ``expression_from_ast`` with an independently resolved call allowlist;
an arbitrary source function with one of those names is not a known operation.
"""

from __future__ import annotations

import ast
import math
from collections.abc import Mapping
from typing import Any

MAX_EXPRESSION_BYTES = 16_384
MAX_EXPRESSION_NODES = 512
MAX_EXPRESSION_DEPTH = 64
FORMULA_CALLS = {name: name for name in ("sum", "sqrt", "matmul", "norm")}
_BINARY = {
    ast.Add: "add", ast.Sub: "sub", ast.Mult: "mul", ast.Div: "div", ast.Pow: "pow"
}
_ARITY = {"add": 2, "sub": 2, "mul": 2, "div": 2, "pow": 2, "neg": 1,
          "sqrt": 1, "matmul": 2, "norm": 1, "sum": 1}
STRUCTURAL_LIMITATION = (
    "Ordered syntactic correspondence only; not mathematical equivalence, "
    "scientific correctness, runtime type inference, or floating-point equivalence."
)


def _unknown(text: str) -> dict:
    # Bound even malformed/hostile input in the returned artifact.
    bounded = text.encode("utf-8", errors="replace")[:MAX_EXPRESSION_BYTES].decode("utf-8", errors="ignore")
    return {"op": "unknown", "text": bounded}


def _bounded_ast(node: ast.AST) -> bool:
    count = 0
    stack = [(node, 0)]
    while stack:
        current, depth = stack.pop()
        count += 1
        if count > MAX_EXPRESSION_NODES or depth > MAX_EXPRESSION_DEPTH:
            return False
        stack.extend((child, depth + 1) for child in ast.iter_child_nodes(current))
    return True


def _dotted_name(node: ast.AST) -> str | None:
    """Return a plain dotted identifier, never a call or dynamic attribute."""
    parts = []
    while isinstance(node, ast.Attribute):
        if node.attr.startswith("__"):
            return None
        parts.append(node.attr)
        node = node.value
    if not isinstance(node, ast.Name) or node.id.startswith("__"):
        return None
    return ".".join([node.id, *reversed(parts)])


def _static_index(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, str)) \
            and not isinstance(node.value, bool):
        return repr(node.value)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub) \
            and isinstance(node.operand, ast.Constant) \
            and type(node.operand.value) is int:
        return str(-node.operand.value)
    if isinstance(node, ast.Tuple):
        if not node.elts:
            return "()"
        values = [_static_index(value) for value in node.elts]
        if all(value is not None for value in values):
            return ", ".join(values) + ("," if len(values) == 1 else "")
    return None


def symbol_name(node: ast.AST) -> str | None:
    """A lexical symbol spelling; static subscripts stay opaque quantities."""
    dotted = _dotted_name(node)
    if dotted is not None:
        return dotted
    if isinstance(node, ast.Subscript):
        base = _dotted_name(node.value)
        index = _static_index(node.slice)
        if base is not None and index is not None:
            return f"{base}[{index}]"
    return None


def expression_from_ast(
    node: ast.AST, source: str, *, calls: Mapping[str, str] | None = None
) -> dict:
    """Parse source syntax with explicitly resolved call names.

    ``calls`` maps source spellings (such as ``np.sqrt``) to canonical names.
    Keywords, dynamic indexing, comprehensions, overloaded matrix operators,
    and unrecognized calls remain unknown. Ordinary arithmetic is retained as
    syntax, without claiming numeric or array semantics.
    """
    calls = calls or {}

    def text_of(current: ast.AST) -> str:
        return ast.get_source_segment(source, current) or type(current).__name__

    if not _bounded_ast(node):
        return _unknown(text_of(node))

    def convert(current: ast.AST) -> dict:
        name = symbol_name(current)
        if name is not None:
            return {"op": "symbol", "name": name}
        if isinstance(current, ast.Constant):
            value = current.value
            if type(value) is int and value.bit_length() <= 4096:
                return {"op": "constant", "value": value}
            if type(value) is float and math.isfinite(value):
                return {"op": "constant", "value": value}
        elif isinstance(current, ast.BinOp) and type(current.op) in _BINARY:
            return {"op": _BINARY[type(current.op)],
                    "args": [convert(current.left), convert(current.right)]}
        elif isinstance(current, ast.UnaryOp) and isinstance(current.op, ast.USub):
            return {"op": "neg", "args": [convert(current.operand)]}
        elif isinstance(current, ast.Call):
            spelling = _dotted_name(current.func)
            op = calls.get(spelling) if spelling is not None else None
            if op in _ARITY and len(current.args) == _ARITY[op] and not current.keywords \
                    and not any(isinstance(arg, ast.Starred) for arg in current.args):
                return {"op": op, "args": [convert(arg) for arg in current.args]}
        return _unknown(text_of(current))

    return convert(node)


def parse_expression(text: str) -> dict:
    """Parse a formula using the documented, narrow scientific conventions."""
    if not isinstance(text, str):
        return _unknown("non-string expression")
    try:
        if len(text.encode("utf-8")) > MAX_EXPRESSION_BYTES:
            return _unknown(text)
    except UnicodeError:
        return _unknown(text)
    try:
        node = ast.parse(text.strip(), mode="eval").body
    except (SyntaxError, ValueError, UnicodeError, RecursionError, MemoryError):
        return _unknown(text)
    return expression_from_ast(node, text.strip(), calls=FORMULA_CALLS)


def _tree_problem(tree: Any) -> str | None:
    stack = [(tree, 0)]
    visited = set()
    count = 0
    while stack:
        node, depth = stack.pop()
        count += 1
        if count > MAX_EXPRESSION_NODES or depth > MAX_EXPRESSION_DEPTH:
            return "expression tree limit exceeded"
        if not isinstance(node, dict):
            return "expression node is not an object"
        if id(node) in visited:
            # Shared Python objects are legal trees when serialized; cycles are not.
            # Reject both conservatively rather than risk unbounded recursion.
            return "cyclic or shared expression node"
        visited.add(id(node))
        op = node.get("op")
        if op == "symbol":
            if set(node) != {"op", "name"} or not isinstance(node["name"], str) \
                    or not node["name"] or len(node["name"]) > MAX_EXPRESSION_BYTES:
                return "invalid symbol node"
        elif op == "constant":
            if set(node) != {"op", "value"} or type(node["value"]) not in (int, float):
                return "invalid constant node"
            value = node["value"]
            if (type(value) is float and not math.isfinite(value)) \
                    or (type(value) is int and value.bit_length() > 4096):
                return "non-finite or oversized constant"
        elif op == "unknown":
            if set(node) != {"op", "text"} or not isinstance(node["text"], str) \
                    or len(node["text"]) > MAX_EXPRESSION_BYTES:
                return "invalid unknown node"
        elif isinstance(op, str) and op in _ARITY:
            args = node.get("args")
            if set(node) != {"op", "args"} or not isinstance(args, list) \
                    or len(args) != _ARITY[op]:
                return "invalid operator node"
            stack.extend((child, depth + 1) for child in args)
        else:
            return "unsupported expression node"
    return None


def align_expressions(
    expected: dict, actual: dict, bindings: Mapping[str, str] | None = None
) -> dict:
    """Compare ordered structures after exact, non-cascading symbol renaming.

    Unknown subtrees make the result unknown even when other paths mismatch;
    those observed mismatches are retained. Bindings are proposed anchors, not
    facts established by this comparison.
    """
    limitations = [STRUCTURAL_LIMITATION]
    problems = [_tree_problem(expected), _tree_problem(actual)]
    if bindings is None:
        bindings = {}
    if not isinstance(bindings, Mapping) or any(
        not isinstance(key, str) or not isinstance(value, str)
        or not key or not value for key, value in bindings.items()
    ):
        problems.append("bindings must map nonempty symbol strings to symbol strings")
        bindings = {}
    if any(problems):
        return {"status": "unknown", "differences": [],
                "limitations": limitations + [problem for problem in problems if problem]}
    if bindings:
        limitations.append("Symbol bindings are supplied hypotheses, not verified semantic correspondences.")
    differences = []
    # An unsupported descendant must not disappear just because its ancestor
    # has a different operator and comparison stops at that ancestor.
    pending = [expected, actual]
    unknown = False
    while pending:
        node = pending.pop()
        unknown |= node["op"] == "unknown"
        pending.extend(node.get("args", []))
    if unknown:
        limitations.append("At least one subtree has unsupported or unresolved syntax.")

    def compare(left: dict, right: dict, path: str) -> None:
        nonlocal unknown
        if left["op"] == "unknown" or right["op"] == "unknown":
            unknown = True
            differences.append({"path": path, "kind": "unknown",
                                "expected": left, "actual": right})
            return
        if left["op"] != right["op"]:
            differences.append({"path": path, "kind": "operator",
                                "expected": left["op"], "actual": right["op"]})
        elif left["op"] == "symbol":
            renamed = bindings.get(left["name"], left["name"])
            if renamed != right["name"]:
                differences.append({"path": path, "kind": "symbol",
                                    "expected": renamed, "actual": right["name"]})
        elif left["op"] == "constant":
            # Numeric spelling/type matters: Python 1 and 1.0 need not have the
            # same overloaded behaviour, dtype, or downstream dispatch.
            if type(left["value"]) is not type(right["value"]) \
                    or left["value"] != right["value"]:
                differences.append({"path": path, "kind": "constant",
                                    "expected": left["value"], "actual": right["value"]})
        else:
            for index, (lchild, rchild) in enumerate(zip(left["args"], right["args"])):
                compare(lchild, rchild, f"{path}/args/{index}")

    compare(expected, actual, "$")
    return {"status": "unknown" if unknown else "mismatch" if differences else "match",
            "differences": differences, "limitations": limitations}
