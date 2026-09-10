import copy

import pytest

from scicontext.semantics import analyze_graph


def sym(name):
    return {"op": "symbol", "name": name}


def const(value):
    return {"op": "constant", "value": value}


def op(name, *args):
    return {"op": name, "args": list(args)}


def quantity(name, dimensions, meaning="Physical quantity", scale="1", shape=None, status="explicit"):
    return {"id": f"q_{name}", "name": name, "meaning": meaning, "code_symbol": name,
            "dimensions": dimensions, "scale": scale, "shape": shape, "evidence_ids": ["e_doc"], "status": status}


def graph(quantities, relation, actual=None, operation="other", assumptions=None):
    return {"schema_version": "1.0", "task_id": "synthetic", "quantities": quantities,
            "claims": [{"id": "c_test", "description": "Scientific unit conversion and preservation requirement", "relation": relation,
                        "actual": actual, "bindings": [], "quantity_ids": [q["id"] for q in quantities], "evidence_ids": ["e_doc"],
                        "assumptions": assumptions if assumptions is not None else ["Same physical grid, consistent anchors, valid finite inputs."], "operation": operation, "status": "inferred"}],
            "evidence": [{"id": "e_doc"}], "observations": [], "unresolved": []}


def finding(result, kind):
    return next(f for f in result["findings"] if f["kind"] == kind)


def properties(result, side="relation"):
    return finding(result, f"{side}_properties")["properties"]


def test_reciprocal_density_volume_scaling_cancels_exactly():
    quantities = [quantity("rho", {"M": "1", "L": "-3"}, "Mass density", shape=["N"]),
                  quantity("volume", {"L": "3"}, "Cell volume weights", shape=["N"])]
    factor = op("pow", const(1.889726), const(3))
    expected = op("sum", op("mul", sym("rho"), sym("volume")))
    actual = op("sum", op("mul", op("div", sym("rho"), factor), op("mul", sym("volume"), copy.deepcopy(factor))))
    data = graph(quantities, expected, actual, "weighted_sum")
    result = analyze_graph(data)
    assert properties(result) == {"dimensions": {"M": "1"}, "scale": "1", "shape": []}
    assert properties(result, "actual") == properties(result)
    assert finding(result, "scale_comparison")["status"] == "agreement"
    assert "floating-point" in finding(result, "scale_comparison")["explanation"]
    assert finding(result, "semantic_lifting")["status"] == "supported"
    assert all(f["assumptions"] == data["claims"][0]["assumptions"] for f in result["findings"])


def test_unknown_wrapper_does_not_inherit_properties_or_lifting():
    from scicontext.expressions import parse_expression

    quantities = [quantity("rho", {"M": "1", "L": "-3"}, "Mass density", shape=[3]),
                  quantity("volume", {"L": "3"}, "Cell volume weights", shape=[3])]
    relation = parse_expression("float(sum(rho * volume))")
    result = analyze_graph(graph(quantities, relation, operation="weighted_sum"))
    assert properties(result) == {"dimensions": None, "scale": None, "shape": None}
    assert finding(result, "semantic_lifting")["status"] == "unknown"


def test_missing_reciprocal_conversion_retains_conflict():
    quantities = [quantity("rho", {"L": "-3"}, "Density", shape=[3]), quantity("volume", {"L": "3"}, "Cell volume", shape=[3])]
    expected = op("sum", op("mul", sym("rho"), sym("volume")))
    actual = op("sum", op("mul", op("mul", sym("rho"), const(8)), sym("volume")))
    data = graph(quantities, expected, actual, "weighted_sum")
    data["observations"] = [{"description": "Baseline failed the probe", "status": "reported"}]
    before = copy.deepcopy(data)
    result = analyze_graph(data)
    assert finding(result, "scale_comparison")["status"] == "conditional"
    assert "Retain the intended requirement" in finding(result, "scale_comparison")["explanation"]
    assert finding(result, "scale_comparison")["expected_factor"] == "1"
    assert finding(result, "scale_comparison")["actual_factor"] == "8"
    assert data == before


def test_addition_dimension_conflict():
    qs = [quantity("distance", {"L": "1"}, shape=[]), quantity("time", {"T": "1"}, shape=[])]
    result = analyze_graph(graph(qs, op("add", sym("distance"), sym("time"))))
    assert properties(result)["dimensions"] is None
    assert finding(result, "relation_properties")["status"] == "conflict"
    assert any("different dimensions" in f["explanation"] for f in result["findings"])


def test_addition_scale_difference_not_invented_as_sum_value():
    qs = [quantity("metres", {"L": "1"}, scale="1", shape=[]), quantity("kilometres", {"L": "1"}, scale="1000", shape=[])]
    result = analyze_graph(graph(qs, op("add", sym("metres"), sym("kilometres"))))
    assert properties(result)["dimensions"] == {"L": "1"}
    assert properties(result)["scale"] is None
    assert any("different formal scale factors" in f["explanation"] for f in result["findings"])


@pytest.mark.parametrize("first,second", [(2, 3), (1, 1), (2, 2)])
def test_ordinary_additive_coefficients_are_not_unit_conflicts(first, second):
    q = quantity("x", {"L": "1"}, "Distance", shape=[])
    expected = op("add", op("mul", const(first), sym("x")), op("mul", const(second), sym("x")))
    actual = op("mul", const(first + second), sym("x"))
    result = analyze_graph(graph([q], expected, actual))
    assert properties(result)["dimensions"] == {"L": "1"}
    assert properties(result)["scale"] is None
    assert finding(result, "dimensions_comparison")["status"] == "agreement"
    assert finding(result, "scale_comparison")["status"] == "unknown"
    assert not any(f["status"] == "conflict" for f in result["findings"])


def test_literal_factor_difference_is_conditional_not_unit_conflict():
    q = quantity("x", {"L": "1"}, "Distance", shape=[])
    result = analyze_graph(graph([q], op("mul", const(2), sym("x")), op("mul", const(3), sym("x"))))
    assert finding(result, "scale_comparison")["status"] == "conditional"
    assert "not a physical-unit inconsistency" in finding(result, "scale_comparison")["explanation"]
    assert not any(f["status"] == "conflict" for f in result["findings"])


def test_normalization_requires_denominator_assumption():
    q = quantity("v", {"L": "1"}, "Position vector", shape=[3])
    expr = op("div", sym("v"), op("norm", sym("v")))
    data = graph([q], expr, operation="normalization", assumptions=["The vector norm is nonzero and inputs are finite."])
    result = analyze_graph(data)
    assert properties(result) == {"dimensions": {}, "scale": "1", "shape": [3]}
    assert finding(result, "semantic_lifting")["status"] == "supported"
    data["claims"][0]["assumptions"] = []
    result = analyze_graph(data)
    assert finding(result, "semantic_lifting")["status"] == "unknown"
    assert all(f["assumptions"] == [] for f in result["findings"])


def test_operation_tag_without_scientific_meanings_does_not_lift():
    qs = [quantity("x", {}, "Array of numbers", shape=[4]), quantity("y", {}, "Array of numbers", shape=[4])]
    data = graph(qs, op("sum", op("mul", sym("x"), sym("y"))), operation="weighted_sum")
    assert finding(analyze_graph(data), "semantic_lifting")["status"] == "unknown"
    # Unused anchors may not lend their scientific meaning to unrelated operands.
    data["quantities"] += [quantity("rho", {"L": "-3"}, "Density"), quantity("volume", {"L": "3"}, "Cell volume")]
    data["claims"][0]["quantity_ids"] += ["q_rho", "q_volume"]
    assert finding(analyze_graph(data), "semantic_lifting")["status"] == "unknown"


def test_matmul_shapes_and_conditioned_lifting():
    qs = [quantity("R", {}, "Rotation matrix", shape=[3, 3]), quantity("x", {"L": "1"}, "Position vector", shape=[3])]
    data = graph(qs, op("matmul", sym("R"), sym("x")), operation="linear_transform")
    result = analyze_graph(data)
    assert properties(result)["shape"] == [3]
    assert finding(result, "semantic_lifting")["status"] == "supported"
    assert "orthogonality" in finding(result, "semantic_lifting")["explanation"]
    qs[1]["shape"] = [4]
    result = analyze_graph(data)
    assert properties(result)["shape"] is None
    assert finding(result, "relation_properties")["status"] == "conflict"


def test_symbolic_and_batched_matmul_are_unknown_not_false_conflicts():
    qs = [quantity("A", {}, shape=["M", "K"]), quantity("B", {}, shape=["N", "P"])]
    result = analyze_graph(graph(qs, op("matmul", sym("A"), sym("B"))))
    assert properties(result)["shape"] is None
    assert not any(f["status"] == "conflict" for f in result["findings"])
    qs[0]["shape"] = [2, 3, 3]
    qs[1]["shape"] = [2, 3, 3]
    assert any("Batched" in f["explanation"] for f in analyze_graph(graph(qs, op("matmul", sym("A"), sym("B"))))["findings"])


@pytest.mark.parametrize("left,right,status", [(["N"], ["M"], "unknown"), (["N"], [3], "unknown"), (["N", 3], ["M", 4], "conflict"), (["N"], ["N", 1], "conflict")])
def test_shape_comparison_distinguishes_symbolic_unknowns(left, right, status):
    qs = [quantity("x", {}, shape=left), quantity("y", {}, shape=right)]
    result = analyze_graph(graph(qs, sym("x"), sym("y")))
    assert finding(result, "shape_comparison")["status"] == status


@pytest.mark.parametrize("right,expected_shape,conflict", [([3], [2, 3], False), ([1, 3], [2, 3], False), ([4], None, True), (["N"], None, False)])
def test_elementwise_broadcast(right, expected_shape, conflict):
    qs = [quantity("x", {}, shape=[2, 3]), quantity("y", {}, shape=right)]
    result = analyze_graph(graph(qs, op("mul", sym("x"), sym("y"))))
    assert properties(result)["shape"] == expected_shape
    assert any(f["status"] == "conflict" for f in result["findings"]) is conflict


def test_rational_dimensions_and_exact_square_root():
    q = quantity("area", [{"dimension": "L", "exponent": "2"}], scale="4", shape=[])
    result = analyze_graph(graph([q], op("sqrt", sym("area"))))
    assert properties(result) == {"dimensions": {"L": "1"}, "scale": "2", "shape": []}
    result = analyze_graph(graph([q], op("pow", sym("area"), op("div", const(1), const(4)))))
    assert properties(result)["dimensions"] == {"L": "1/2"}
    assert properties(result)["scale"] is None  # sqrt(2) cannot become a fake rational.


def test_negative_exponent_tree():
    q = quantity("length", {"L": "1"}, scale="2", shape=[])
    result = analyze_graph(graph([q], op("pow", sym("length"), op("neg", const(3)))))
    assert properties(result) == {"dimensions": {"L": "-3"}, "scale": "1/8", "shape": []}


def test_unknown_and_ambiguous_anchors():
    q = quantity("x", {"L": "1"}, status="unresolved")
    result = analyze_graph(graph([q], sym("x")))
    assert properties(result) == {"dimensions": None, "scale": None, "shape": None}
    assert finding(result, "relation_properties")["status"] == "unknown"
    result = analyze_graph(graph([], sym("missing")))
    assert "no semantic anchor" in " ".join(f["explanation"] for f in result["findings"])
    q2 = dict(quantity("y", {"T": "1"}), code_symbol="x")
    result = analyze_graph(graph([dict(q, status="explicit"), q2], sym("x")))
    assert properties(result)["dimensions"] is None
    assert "ambiguous" in " ".join(f["explanation"] for f in result["findings"])


def test_bindings_array_and_internal_mapping():
    q = quantity("field", {"L": "1"}, scale="1", shape=[])
    for binding in ([{"expected": "x", "actual": "field"}], {"x": "field"}):
        data = graph([q], sym("x"), sym("field"))
        data["claims"][0]["bindings"] = binding
        assert finding(analyze_graph(data), "dimensions_comparison")["status"] == "agreement"


def test_binding_never_invents_a_unit_for_unanchored_actual_symbol():
    q = quantity("field", None, scale=None, shape=[])
    data = graph([q], sym("rho"), sym("field"))
    data["claims"][0]["bindings"] = [{"expected": "rho", "actual": "field"}]
    result = analyze_graph(data)
    assert properties(result)["dimensions"] is None
    assert properties(result, "actual")["dimensions"] is None
    assert finding(result, "dimensions_comparison")["status"] == "unknown"


@pytest.mark.parametrize("expr", [
    {"op": "call", "args": [], "name": "eval"},
    {"op": "mul", "args": ["__import__('os')", const(2)]},
    {"op": "symbol", "name": "x", "execute": "evil"},
    {"op": []},
    const(float("nan")), const(True), op("div", const(1), const(0)),
])
def test_unsafe_trees_do_not_execute_or_crash(expr):
    result = analyze_graph(graph([], expr, operation="weighted_sum"))
    assert any(f["status"] in {"unknown", "conflict"} for f in result["findings"])


def test_cyclic_tree_and_huge_exponent_are_bounded():
    expr = op("neg", const(1))
    expr["args"] = [expr]
    result = analyze_graph(graph([], expr))
    assert any("cyclic" in f["explanation"] for f in result["findings"])
    result = analyze_graph(graph([], op("pow", const(2), const(10 ** 90))))
    assert properties(result)["scale"] is None
    expr = const(2)
    for _ in range(10):
        expr = op("pow", expr, const(64))
    assert properties(analyze_graph(graph([], expr)))["scale"] is None


def test_scientific_lifting_requires_source_evidence():
    qs = [quantity("rho", {}, "Density"), quantity("weight", {}, "Cell volume")]
    data = graph(qs, op("sum", op("mul", sym("rho"), sym("weight"))), operation="weighted_sum")
    data["evidence"] = []
    assert finding(analyze_graph(data), "semantic_lifting")["status"] == "unknown"


def test_supported_conversion_not_declared_as_correct_factor():
    q = quantity("distance", {"L": "1"}, "Distance in metres", shape=[])
    result = analyze_graph(graph([q], op("div", sym("distance"), const(1000)), operation="unit_conversion"))
    assert finding(result, "semantic_lifting")["status"] == "supported"
    assert "evidence-dependent" in finding(result, "semantic_lifting")["explanation"]
