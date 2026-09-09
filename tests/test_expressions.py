import ast

import pytest

from scicontext.expressions import (
    MAX_EXPRESSION_BYTES, align_expressions, expression_from_ast, parse_expression,
)


def test_ordered_arithmetic_and_explicit_formula_calls():
    tree = parse_expression("sum(rho * volume) / sqrt(t)")
    assert tree["op"] == "div"
    assert tree["args"][0] == {
        "op": "sum", "args": [{"op": "mul", "args": [
            {"op": "symbol", "name": "rho"}, {"op": "symbol", "name": "volume"}]}]}
    assert tree["args"][1]["op"] == "sqrt"
    assert align_expressions(parse_expression("x + y"), parse_expression("y + x"))["status"] == "mismatch"


def test_bindings_are_exact_and_do_not_cascade():
    result = align_expressions(parse_expression("a / b"), parse_expression("b / c"), {"a": "b", "b": "c"})
    assert result["status"] == "match"
    assert any("not mathematical equivalence" in value for value in result["limitations"])
    assert align_expressions(parse_expression("a.x"), parse_expression("b.x"), {"a": "b"})["status"] == "mismatch"


def test_differences_have_ordered_paths():
    result = align_expressions(parse_expression("a + 2 * b"), parse_expression("a - 2 / b"))
    assert result["differences"][0]["path"] == "$"
    result = align_expressions(parse_expression("a + b"), parse_expression("a + c"))
    assert result["differences"] == [{"path": "$/args/1", "kind": "symbol", "expected": "b", "actual": "c"}]


@pytest.mark.parametrize("text", [
    "__import__('os').system('echo unsafe')", "(lambda x: x)(1)", "[x for x in y]",
    "a @ b", "a // b", "a % b", "a[i]", "a[:]", "x.__class__", "1e9999",
    "True", "'units'", "sum(x, axis=0)", "sum(*x)", "sqrt(x, y)", "x := 1",
])
def test_unsupported_and_unsafe_expressions_stay_unknown(text):
    assert parse_expression(text)["op"] == "unknown"


def test_safe_source_calls_require_allowlist():
    source = "np.sqrt(x)"
    node = ast.parse(source, mode="eval").body
    assert expression_from_ast(node, source)["op"] == "unknown"
    assert expression_from_ast(node, source, calls={"np.sqrt": "sqrt"})["op"] == "sqrt"
    assert parse_expression(source)["op"] == "unknown"


def test_dot_and_static_subscript_are_opaque_symbols():
    assert parse_expression("grid.values")["name"] == "grid.values"
    assert parse_expression("grid.values[-1]")["name"] == "grid.values[-1]"
    assert parse_expression("a[1, 2]")["name"] == "a[1, 2]"
    assert parse_expression("a['rho']")["name"] == "a['rho']"
    assert parse_expression("a[True]")["op"] == "unknown"


def test_type_dependent_operators_are_not_algebraically_rewritten():
    result = align_expressions(parse_expression("x * 1"), parse_expression("x"))
    assert result["status"] == "mismatch"
    assert align_expressions(parse_expression("1"), parse_expression("1.0"))["status"] == "mismatch"
    assert align_expressions(parse_expression("x + y"), parse_expression("y + x"))["status"] == "mismatch"


def test_unknown_pair_is_not_a_match_and_partial_mismatches_preserved():
    result = align_expressions(parse_expression("f(x) + a"), parse_expression("f(x) + b"))
    assert result["status"] == "unknown"
    assert [item["kind"] for item in result["differences"]] == ["unknown", "symbol"]
    result = align_expressions(parse_expression("a + f(x)"), parse_expression("a * b"))
    assert result["status"] == "unknown"
    assert result["differences"][0]["kind"] == "operator"


def test_expression_size_and_malformed_graph_limits():
    assert parse_expression("x" * (MAX_EXPRESSION_BYTES + 1))["op"] == "unknown"
    assert parse_expression("+".join(["x"] * 1000))["op"] == "unknown"
    assert align_expressions({"op": "constant", "value": True}, parse_expression("1"))["status"] == "unknown"
    assert align_expressions({"op": "add", "args": []}, parse_expression("1"))["status"] == "unknown"
    cyclic = {"op": "neg"}
    cyclic["args"] = [cyclic]
    assert align_expressions(cyclic, parse_expression("x"))["status"] == "unknown"


def test_bad_bindings_and_nonfinite_constants_do_not_crash():
    assert align_expressions(parse_expression("x"), parse_expression("x"), {"x": None})["status"] == "unknown"
    assert align_expressions({"op": "constant", "value": float("nan")}, parse_expression("1"))["status"] == "unknown"
    assert parse_expression("\ud800")["op"] == "unknown"
