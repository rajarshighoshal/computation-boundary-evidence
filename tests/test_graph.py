import copy
import hashlib
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from scicontext.graph import graph_schema, render_graph, validate_graph


def empty_graph():
    return {"schema_version": "1.0", "task_id": "002", "quantities": [], "claims": [], "evidence": [], "observations": [], "unresolved": []}


def quantity(identifier="q_density"):
    return {"id": identifier, "name": "density", "meaning": "Mass density on the grid", "code_symbol": "density",
            "dimensions": [{"dimension": "M", "exponent": "1"}, {"dimension": "L", "exponent": "-3"}],
            "scale": "1", "shape": ["N"], "evidence_ids": ["e_doc"], "status": "inferred"}


def claim(identifier="c_mass"):
    return {"id": identifier, "description": "A density representation requires reciprocal volume scaling.",
            "relation": {"op": "symbol", "name": "rho"}, "actual": {"op": "symbol", "name": "density"},
            "bindings": [{"expected": "rho", "actual": "density"}], "quantity_ids": ["q_density"],
            "evidence_ids": ["e_doc"], "assumptions": ["The grid represents the same physical domain."],
            "operation": "unit_conversion", "status": "inferred"}


@pytest.fixture
def backed_graph(tmp_path):
    source = tmp_path / "README.md"
    source.write_bytes(b"Scientific specification\nMass density is sampled on the grid.\n")
    graph = empty_graph()
    graph["quantities"] = [quantity()]
    graph["claims"] = [claim()]
    graph["evidence"] = [{"id": "e_doc", "path": "README.md", "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                          "start_line": 2, "end_line": 2, "quote": "Mass density is sampled on the grid."}]
    return graph, tmp_path


def test_minimal_and_backed_graph(backed_graph):
    graph, root = backed_graph
    assert validate_graph(empty_graph(), root)["valid"]
    assert validate_graph(graph, root)["valid"]
    assert any("not scientific correctness" in warning for warning in validate_graph(graph, root)["warnings"])


def test_schema_has_strict_objects_only():
    schema = graph_schema()
    Draft202012Validator.check_schema(schema)

    def visit(value):
        if isinstance(value, dict):
            if value.get("type") == "object":
                assert value["additionalProperties"] is False
                assert set(value["required"]) == set(value["properties"])
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(schema)
    assert graph_schema() is not schema
    schema["properties"]["quantities"]["items"]["properties"]["id"]["maxLength"] = 1
    assert graph_schema()["properties"]["quantities"]["items"]["properties"]["id"]["maxLength"] == 120


@pytest.mark.parametrize("field,value", [("sha256", "0" * 64), ("quote", "Invented assertion."), ("start_line", 3), ("end_line", 50)])
def test_exact_evidence_required(backed_graph, field, value):
    graph, root = backed_graph
    graph["evidence"][0][field] = value
    assert not validate_graph(graph, root)["valid"]


@pytest.mark.parametrize("path", ["../README.md", "/etc/passwd", ".codex/auth.json", "auth.json", "private/test.py", "tests/private_tests.py", "tests/verifier.py", "docs/credentials.json", "x\\auth.json"])
def test_unsafe_paths_rejected_without_reading(backed_graph, path):
    graph, root = backed_graph
    graph["evidence"][0]["path"] = path
    result = validate_graph(graph, root)
    assert not result["valid"]
    assert any("unsafe evidence path" in e for e in result["errors"])


def test_symlink_even_inside_root_is_rejected(backed_graph):
    graph, root = backed_graph
    (root / "linked.md").symlink_to(root / "README.md")
    graph["evidence"][0]["path"] = "linked.md"
    assert "symlink" in " ".join(validate_graph(graph, root)["errors"])


def test_parent_symlink_rejected(backed_graph):
    graph, root = backed_graph
    (root / "docs").symlink_to(root, target_is_directory=True)
    graph["evidence"][0]["path"] = "docs/README.md"
    assert not validate_graph(graph, root)["valid"]


def test_non_regular_source_rejected(backed_graph):
    import os

    graph, root = backed_graph
    os.mkfifo(root / "pipe")
    graph["evidence"][0]["path"] = "pipe"
    assert not validate_graph(graph, root)["valid"]


def test_ids_references_caps_and_strict_fields(backed_graph):
    original, root = backed_graph
    for modify in (
        lambda g: g["quantities"].append(copy.deepcopy(g["quantities"][0])),
        lambda g: g["claims"][0]["evidence_ids"].append("missing"),
        lambda g: g["claims"][0]["quantity_ids"].append("missing"),
        lambda g: g["claims"][0]["bindings"].append({"expected": "rho", "actual": "other"}),
        lambda g: g["claims"][0].update(unexpected=True),
        lambda g: g["quantities"][0].update(dimensions={"L": "-3"}),
    ):
        graph = copy.deepcopy(original)
        modify(graph)
        assert not validate_graph(graph, root)["valid"]
    assert not validate_graph(original, root, max_claims=0)["valid"]
    assert not validate_graph(original, root, max_nodes=2)["valid"]
    graph = copy.deepcopy(original)
    graph["claims"] = [claim(f"c_{i}") for i in range(13)]
    assert not validate_graph(graph, root)["valid"]
    graph = empty_graph()
    graph["quantities"] = [dict(quantity(f"q_{i}"), evidence_ids=[], status="unresolved") for i in range(64)]
    assert validate_graph(graph, root)["valid"]
    graph["claims"] = [dict(claim(), quantity_ids=[], evidence_ids=[], status="unresolved")]
    assert not validate_graph(graph, root)["valid"]


@pytest.mark.parametrize("scale", ["0", "-1", "1/0", "nan", "__import__('os')"])
def test_invalid_scales_rejected(backed_graph, scale):
    graph, root = backed_graph
    graph["quantities"][0]["scale"] = scale
    assert not validate_graph(graph, root)["valid"]


def test_rational_exponents_and_duplicate_dimensions(backed_graph):
    graph, root = backed_graph
    graph["quantities"][0]["dimensions"] = [{"dimension": "L", "exponent": "1/2"}]
    assert validate_graph(graph, root)["valid"]
    graph["quantities"][0]["dimensions"].append({"dimension": "L", "exponent": "2"})
    assert not validate_graph(graph, root)["valid"]


@pytest.mark.parametrize("expression", [
    {"op": "call", "name": "eval", "args": []},
    {"op": "mul", "args": []},
    {"op": "constant", "value": True},
    {"op": "constant", "value": float("inf")},
    {"op": "symbol", "name": "x", "code": "unsafe"},
])
def test_unsafe_or_malformed_expression(backed_graph, expression):
    graph, root = backed_graph
    graph["claims"][0]["relation"] = expression
    assert not validate_graph(graph, root)["valid"]


def test_deep_and_cyclic_expression_do_not_recurse_unbounded(backed_graph):
    graph, root = backed_graph
    expr = {"op": "symbol", "name": "x"}
    for _ in range(70):
        expr = {"op": "neg", "args": [expr]}
    graph["claims"][0]["relation"] = expr
    assert not validate_graph(graph, root)["valid"]
    expr["args"] = [expr]
    assert not validate_graph(graph, root)["valid"]


def test_shared_python_expression_is_valid_json(backed_graph):
    graph, root = backed_graph
    graph["claims"][0]["actual"] = graph["claims"][0]["relation"]
    assert validate_graph(graph, root)["valid"]


def test_reported_probe_is_not_certified(backed_graph):
    graph, root = backed_graph
    graph["observations"] = [{"id": "o_probe", "claim_id": "c_mass", "description": "The baseline violates the rule.", "status": "reported", "artifact": "probes/check.json"}]
    result = validate_graph(graph, root)
    assert result["valid"]
    assert any("requires corroborating" in text for text in result["warnings"])
    assert graph["claims"][0]["status"] == "inferred"


def test_render_preserves_claims_assumptions_and_conflicts(backed_graph):
    graph, _ = backed_graph
    analysis = {"findings": [{"claim_id": "c_mass", "kind": "scale", "status": "conflict", "explanation": "Contradictory factor", "assumptions": graph["claims"][0]["assumptions"]}]}
    rendered = render_graph(graph, analysis)
    assert "same physical domain" in rendered
    assert "conflict" in rendered and "inferred" in rendered
    assert "unit_conversion" in rendered and "Scientific context for task 002" in rendered
    assert render_graph(json.loads(json.dumps(graph)), analysis) == rendered


def test_explicit_claim_requires_citation(backed_graph):
    graph, root = backed_graph
    graph["claims"][0].update(status="explicit", evidence_ids=[])
    assert not validate_graph(graph, root)["valid"]
