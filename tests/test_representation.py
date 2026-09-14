"""Scientific structure preservation and counterexamples; no model/candidate execution."""
import copy

import pytest

from scicontext.object_context import enrichment_input, object_bundle
from scicontext.packet import build_packet
from scicontext.representation import _pattern, reading_input, render_reading
from scicontext.scientific_model import VERSION
from scicontext.scientific_objects import extract_objects


def build(root, code, name="model.py"):
    (root / name).write_text(code)
    (root / "README.md").write_text("The stored quantity loses outward transport. The flag enables this computation.")
    packet = build_packet(root, multilingual=True)
    graph = extract_objects(root, packet)
    view = reading_input(enrichment_input(graph, packet))
    return graph, view, packet


def assert_closed(view):
    entities = {e["id"] for e in view["entities"]}
    templates = {t["id"] for t in view["templates"]}
    sources = {s["id"] for s in view["sources"]}
    for entity in view["entities"]:
        assert set(entity["source_ids"]) <= sources
        assert not entity.get("template_id") or entity["template_id"] in templates
        assert all(b.get("definition_id") is None or b["definition_id"] in entities for b in entity.get("bindings", []))
        assert all(c.get("predicate_id") is None or c["predicate_id"] in entities for c in entity.get("condition_refs", []))
    assert all(r["source"] in entities and r["target"] in entities for r in view["relations"])


def test_common_structure_keeps_distinct_bindings_not_value_equality(tmp_path):
    graph, view, packet = build(tmp_path, "def f(a, b):\n    x = a * b\n    y = b * a\n    return x-y\n")
    expressions = {e["id"]: e for e in view["entities"] if e["kind"] == "source_computation"}
    ids = {s["text"]: s["id"] for s in view["sources"]}
    x, y = (expressions[ids[text]] for text in ("x = a * b", "y = b * a"))
    assert x["template_id"] == y["template_id"]
    assert [b["name"] for b in x["bindings"]] == ["x", "a", "b"]
    assert [b["name"] for b in y["bindings"]] == ["y", "b", "a"]
    assert x["id"] != y["id"]
    assert "not equal values" in render_reading(view)
    assert view == reading_input(enrichment_input(graph, packet))
    assert_closed(view)


@pytest.mark.parametrize("first,second", [
    ("x = a - (b - c)", "x = (a - b) - c"),
    ("x = a[0]", "x = a[1]"),
    ("x = a * 0.5", "x = a * 2"),
    ("x = f(a, axis=0)", "x = f(a, axis=1)"),
    ("x = a + a", "x = a + b"),
    ("x += y", "x -= y"),
])
def test_template_identity_preserves_order_indices_coefficients_and_update_operator(first, second):
    assert _pattern({"text": first})[0] != _pattern({"text": second})[0]


def test_nested_bound_names_are_not_rewritten_into_dangling_free_variables():
    structure, bindings, _ = _pattern({"text": "f = lambda x: x + y"})
    assert structure["expression"] == "f = lambda x: x + y"
    assert bindings == []


def test_cython_keyword_names_are_not_lost_by_structural_parameterization(tmp_path):
    _, view, _ = build(tmp_path, "cdef double f(double x):\n    a = other(x, axis=0)\n    b = other(x, dim=0)\n    return a+b\n", "model.pyx")
    patterns = [t["structure"] for t in view["templates"]]
    assert any("axis=0" in p.get("expression", "") for p in patterns)
    assert any("dim=0" in p.get("expression", "") for p in patterns)


def test_large_literal_collection_is_data_without_element_expansion(tmp_path):
    _, view, _ = build(tmp_path, "table = " + repr(list(range(400))) + "\n")
    entity = next(e for e in view["entities"] if e["kind"] == "data_initializer")
    template = next(t["structure"] for t in view["templates"] if t["id"] == entity["template_id"])
    assert template["literal_collection"]["entries"] == 400
    assert "399" not in render_reading(view)
    assert_closed(view)


def test_native_symbolic_initializer_retains_dependencies(tmp_path):
    _, view, _ = build(tmp_path, "double a=2;\ndouble table[64]={" + ",".join(["a"]*64) + "};\n", "model.cpp")
    entity = next(e for e in view["entities"] if e["kind"] == "data_initializer")
    assert [b["name"] for b in entity["bindings"]] == ["a"]
    template = next(t["structure"] for t in view["templates"] if t["id"] == entity["template_id"])
    assert template["data_initializer"]["constant_evaluation"] == "not_established"
    assert_closed(view)


@pytest.mark.parametrize("name,code", [
    ("model.py", "def f(x, flag):\n    if flag:\n        x = x * 2\n    return x\n"),
    ("model.c", "double f(double x, int flag) { while(flag) { x=x*2; flag=0; } return x; }\n"),
    ("model.m", "function y=f(x,flag)\nwhile flag\nx=x*2;\nflag=0;\nend\ny=x;\nend\n"),
    ("model.f90", "function f(x,flag) result(y)\nreal :: x,y\nlogical :: flag\nif (flag) then\ny=x*2\nelse\ny=x\nend if\nend function\n"),
    ("model.pyx", "cdef double f(double x, bint flag):\n    if flag:\n        x = x * 2\n    return x\n"),
])
def test_control_predicates_are_source_evidence_across_frontends(tmp_path, name, code):
    _, view, packet = build(tmp_path, code, name)
    predicates = [e for e in packet["entries"] if e["kind"] in {"predicate", "comparison"}]
    assert any("flag" in e["text"] for e in predicates)
    assert any(c["predicate_id"] for e in view["entities"] for c in e.get("condition_refs", []))
    assert_closed(view)


def test_join_closes_transitive_bindings_conditions_and_templates(tmp_path):
    graph, view, _ = build(tmp_path, "def f(seed, flag):\n    a=seed*2\n    b=a+1\n    c=b*3\n    if flag:\n        c=c-1\n    return c\n")
    c = next(s["id"] for s in view["sources"] if s["text"] == "c=b*3")
    doc = next(s["id"] for s in view["sources"] if s["path"] == "README.md")
    claim = {"text": "Selected material computation.", "source_ids": [doc]}
    response = {"schema_version": VERSION, "purpose": claim, "computations": [{"computation_id": c,
        "meaning": claim, "expression_ids": [c], "quantities": [], "conventions": [], "assumptions": []}]}
    original = copy.deepcopy(view)
    bundle = object_bundle(graph, response, view)
    assert bundle["assembly"]["usable"]
    assert view == original
    assert_closed(bundle["graph"]["scientific_model"])
    assert "c=b*3" in bundle["handoff"]
    assert any(s["text"] == "a=seed*2" for s in bundle["graph"]["scientific_model"]["sources"])


def test_unknown_selected_expression_cannot_be_injected_into_guide(tmp_path):
    graph, view, _ = build(tmp_path, "def f(x):\n    return x * 2\n")
    c = view["computations"][0]
    doc = next(s["id"] for s in view["sources"] if s["path"] == "README.md")
    claim = {"text": "Computation.", "source_ids": [doc]}
    response = {"schema_version": VERSION, "purpose": claim, "computations": [{"computation_id": c["id"],
        "meaning": claim, "expression_ids": ["invented"], "quantities": [], "conventions": [], "assumptions": []}]}
    assert not object_bundle(graph, response, view)["assembly"]["usable"]


def test_duplicate_document_text_retains_distinct_origins():
    view = reading_input({"context": {"scientific_passages": [
        {"id": "a", "path": "paper.md", "quote": "Same text"},
        {"id": "b", "path": "task.md", "quote": "Same text"}]}})
    assert len(view["sources"]) == 1
    assert view["sources"][0]["additional_origins"] == [{"id": "b", "path": "task.md"}]


def test_task_slice_follows_definitions_but_not_unrelated_inventory(tmp_path):
    _, _, packet = build(tmp_path, "def useful(x):\n    a=x*2\n    return a\ndef unrelated(y):\n    return y+100\n")
    graph = extract_objects(tmp_path, packet)
    payload = enrichment_input(graph, packet)
    payload["context"]["analysis_regions"] = [{"path": "model.py", "start_line": 3, "end_line": 3}]
    view = reading_input(payload)
    text = render_reading(view)
    assert "a=x*2" in text and "return a" in text
    assert "y+100" not in text
    assert_closed(view)


def test_task_slice_retains_guard_outside_requested_source_line(tmp_path):
    graph, _, packet = build(tmp_path, "def f(flag,x):\n    if flag:\n        y=x*2\n    return y\n")
    payload = enrichment_input(graph, packet)
    payload["context"]["analysis_regions"] = [{"path": "model.py", "start_line": 3, "end_line": 3}]
    view = reading_input(payload)
    assert any(c["predicate_id"] for e in view["entities"] for c in e.get("condition_refs", []))
    assert any(s["text"] == "flag" for s in view["sources"])
    assert_closed(view)


def test_reader_defines_boundary_quantities_not_only_function_members(tmp_path):
    _, view, _ = build(tmp_path, "G=6.67e-11\ndef force(mass,distance):\n    return G*mass/distance**2\n")
    text = render_reading(view)
    for relation in view["relations"]:
        assert "[" + relation["source"] + "]" in text
        assert "[" + relation["target"] + "]" in text
