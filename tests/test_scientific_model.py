"""Code/model/guide contract tests; fixture interpretations are not model-quality results."""
import asyncio
import copy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scicontext.controller import TrialConfig, run_trial
from scicontext.io import write_json
from scicontext.object_context import enrichment_input, object_bundle, render_guide
from scicontext.packet import build_packet
from scicontext.pier_agent import ScientificCodex
from scicontext.scientific_model import reading_input, VERSION
from scicontext.scientific_objects import extract_objects
from scicontext.tool_cli import main as helper


@pytest.fixture
def case(tmp_path):
    (tmp_path / "model.py").write_text('def advance(previous, flux, duration):\n'
        '    """Flux is outward transport per unit time."""\n'
        '    loss = flux * duration\n    result = previous - loss\n'
        '    if result < 0:\n        raise ValueError("negative inventory")\n    return result\n')
    (tmp_path / "README.md").write_text("This model tracks stored material. Positive flux leaves the store.\n"
        "Duration uses the same time unit as flux.\n")
    packet = build_packet(tmp_path, multilingual=True)
    graph = extract_objects(tmp_path, packet)
    graph["task_id"] = "synthetic"
    view = reading_input(enrichment_input(graph, packet))
    computation = next(c for c in view["computations"] if "advance" in c["name"])
    flux = next(o for o in graph["objects"] if o["symbol"] == "flux")
    doc = next(s for s in view["sources"] if s["path"] == "README.md")
    def claim(text):
        return {"text": text, "source_ids": [doc["id"]]}
    response = {"schema_version": VERSION, "purpose": claim("Track stored material under outward transport."),
        "computations": [{"computation_id": computation["id"],
            "meaning": claim("Subtract the transported amount from the previous inventory."),
            "quantities": [{"object_id": flux["id"], "meaning": claim("Outward material transport rate.")}],
            "conventions": [claim("Positive flux leaves the store; duration and flux use matching time units.")],
            "assumptions": ["This reading does not establish whether negative inventory must always be rejected."]}]}
    return graph, view, response


def test_source_owned_structure_and_scientific_meaning_join_without_mutation(case):
    graph, view, response = case
    old = copy.deepcopy((graph, view, response))
    bundle = object_bundle(graph, response, view)
    assert (graph, view, response) == old
    assert bundle["assembly"]["usable"]
    model = bundle["graph"]["scientific_model"]
    assert model["computations"][0]["interpretation"] == response["computations"][0]
    assert bundle["graph"]["operations"] == graph["operations"]
    assert bundle["graph"]["links"] == graph["links"]
    ids = {e["id"] for e in model["entities"]}
    assert all(r["source"] in ids and r["target"] in ids for r in model["relations"])
    guide = render_guide(bundle["graph"])
    assert "outward transport" in guide and "matching time units" in guide
    assert "Code relationships:" in guide and "flux * duration" in guide
    assert "README.md:1" in guide and "Assumption:" in guide
    assert "Code predicate: result < 0" in guide
    assert "scientific-model.json" in guide
    assert len(guide) <= 9000
    assert "not mechanically established" in model["validation"]


def test_observation_does_not_become_requirement_or_failure_label(case):
    graph, view, response = case
    view["observations"] = [{"collapse": False, "unchanged_output": True, "build_exit": 1}]
    model = object_bundle(graph, response, view)["graph"]
    guide = render_guide(model)
    assert "containment violation" not in guide and "must change" not in guide
    assert model["scientific_model"]["observations"] == view["observations"]


@pytest.mark.parametrize("mutation,reason", [
    (lambda r: r["computations"][0].update(computation_id="fabricated"), "unknown_computation"),
    (lambda r: r["computations"][0]["meaning"].update(source_ids=["fabricated"]), "unknown_source_citation"),
    (lambda r: r["computations"][0]["quantities"][0].update(object_id="fabricated"), "quantity_outside_computation"),
    (lambda r: r["computations"][0].update(edges=[{"source": "x", "target": "y"}]), "invalid_computation_fields"),
    (lambda r: r["computations"][0].update(probes=["assert x"]), "invalid_computation_fields"),
])
def test_unanchored_or_structural_model_output_is_not_delivered(case, mutation, reason):
    graph, view, response = case
    mutation(response)
    bundle = object_bundle(graph, response, view)
    assert not bundle["assembly"]["usable"]
    assert bundle["handoff"] == ""
    assert bundle["assembly"]["enrichment"]["dropped"][0]["reason"] == reason


@pytest.mark.parametrize("response", [None, {"schema_version": VERSION, "purpose": {}, "computations": []},
                                      {"schema_version": "object-enrichment-1.0", "annotations": []}])
def test_failed_or_legacy_response_is_not_silent_code_only_v2_treatment(case, response):
    graph, view, _ = case
    bundle = object_bundle(graph, response, view)
    assert not bundle["assembly"]["usable"]
    assert bundle["assembly"]["status"] == "no_scientific_model"


def test_real_assembly_helper_uses_supplied_citations(case, tmp_path, capsys):
    graph, view, response = case
    for name, value in (("graph", graph), ("input", view), ("response", response)):
        write_json(tmp_path / f"{name}.json", value)
    helper(["assemble-objects", "--graph", str(tmp_path / "graph.json"), "--annotations", str(tmp_path / "response.json"),
            "--context-input", str(tmp_path / "input.json"), "--output", str(tmp_path / "bundle.json")])
    capsys.readouterr()
    result = json.loads((tmp_path / "bundle.json").read_text())
    assert result["assembly"]["usable"] and result["validation"]["valid"]
    assert "outward transport" in result["handoff"]


def test_guide_keeps_conditions_and_assumptions_with_each_displayed_computation(case):
    graph, view, response = case
    c = response["computations"][0]
    c["meaning"]["text"] = "M" * 600
    c["conventions"] = [{"text": f"CONDITION {i}: " + "c" * 580, "source_ids": c["meaning"]["source_ids"]} for i in range(4)]
    c["assumptions"] = ["ASSUMPTION " + "a" * 220]
    guide = object_bundle(graph, response, view)["handoff"]
    assert all(f"CONDITION {i}" in guide for i in range(4)) and "ASSUMPTION" in guide


def test_same_names_in_different_scopes_do_not_share_quantity_identity(tmp_path):
    (tmp_path / "model.py").write_text("def a(x):\n    return x * 2\ndef b(x):\n    return x + 1\n")
    packet = build_packet(tmp_path, multilingual=True)
    graph = extract_objects(tmp_path, packet)
    view = reading_input(enrichment_input(graph, packet))
    scopes = [set(c["entity_ids"]) for c in view["computations"] if c["name"].endswith(("a@1", "b@3"))]
    assert len(scopes) == 2 and not scopes[0] & scopes[1]
    assert view == reading_input(enrichment_input(graph, packet))


def test_omitted_operands_remain_explicit_unknowns():
    payload = {"context": {"code_passages": [{"id": "expr", "path": "m.py", "scope": "<module>",
        "start_line": 1, "end_line": 1, "kind": "assignment", "text": "y = external(x)",
        "local_dependencies": [{"name": "x", "definition_id": "not_supplied", "status": "resolved"}]}]},
        "unsupported": [{"reason": "partial_parse"}]}
    view = reading_input(payload)
    binding = next(b for b in view["entities"][0]["bindings"] if b["name"] == "x")
    assert binding["definition_id"] is None and binding["status"] == "outside_selected_view"
    assert view["coverage"]["unsupported_counts"] == {"partial_parse": 1}


def test_long_valid_computation_is_not_silently_reduced_to_a_file_pointer(case):
    graph, view, response = case
    c = response["computations"][0]
    for i, identifier in enumerate(view["computations"][0]["entity_ids"][:8]):
        c["quantities"].append({"object_id": identifier, "meaning": {"text": "q" * 600, "source_ids": c["meaning"]["source_ids"]}})
    c["quantities"] = list({q["object_id"]: q for q in c["quantities"]}.values())[:8]
    c["conventions"] = [{"text": f"IMPORTANT {i}:" + "c" * 580, "source_ids": c["meaning"]["source_ids"]} for i in range(4)]
    c["assumptions"] = ["a" * 240] * 3
    bundle = object_bundle(graph, response, view)
    assert bundle["assembly"]["usable"]
    assert "Subtract the transported amount" in bundle["handoff"]
    assert all(f"IMPORTANT {i}" in bundle["handoff"] for i in range(4))
    assert "Code predicate: result < 0" in bundle["handoff"]


def test_distinct_conventions_remain_with_their_own_computation(case):
    graph, view, response = case
    second = copy.deepcopy(view["computations"][0])
    second["id"], second["name"] = "second_definition", "inward_convention"
    view["entities"].append({"id": "second_definition", "kind": "code_interface", "source_ids": second["source_ids"]})
    second["entity_ids"] = ["second_definition", *second["entity_ids"]]
    view["computations"].append(second)
    interpretation = copy.deepcopy(response["computations"][0])
    interpretation["computation_id"] = "second_definition"
    interpretation["conventions"][0]["text"] = "INWARD convention requires separate interpretation."
    response["computations"].append(interpretation)
    guide = object_bundle(graph, response, view)["handoff"]
    first, second_text = guide.split("## inward_convention")
    assert "Positive flux leaves" in first and "INWARD convention" not in first
    assert "INWARD convention" in second_text and "Positive flux leaves" not in second_text


def test_top_level_operations_are_not_invented_function_definitions():
    rows = [{"id": name, "kind": "assignment", "text": text, "path": "m.py", "scope": "<module>",
             "start_line": i, "end_line": i} for i, (name, text) in enumerate((("first", "x = 1"), ("second", "y = x * 2")), 1)]
    view = reading_input({"context": {"code_passages": rows}})
    assert [c["entity_ids"] for c in view["computations"]] == [["first"], ["second"]]


def test_analyzer_without_source_expressions_does_not_invent_source_computations():
    rows = [{"id": name, "kind": "IDENTIFIER", "analyzer": "joern", "path": "m.cpp", "start_line": 1,
             "end_line": 1, "text": "x", "scope": name} for name in ("a", "b")]
    view = reading_input({"context": {"analysis_sources": rows}})
    assert not view["computations"]
    assert view["coverage"]["joern_unprojected_kinds"] == {"IDENTIFIER": 2}


def test_analyzer_generated_predicate_is_not_presented_as_literal_source(case):
    graph, view, response = case
    bundle = object_bundle(graph, response, view)
    model = bundle["graph"]["scientific_model"]
    c = model["computations"][0]
    model["entities"].extend([
        {"id": "control", "kind": "CONTROL_STRUCTURE", "source_ids": []},
        {"id": "generated", "kind": "CALL", "source_ids": ["generated"]}])
    model["sources"].append({"id": "generated", "kind": "analyzer", "path": "model.py",
                             "start_line": 3, "end_line": 3, "text": "iteratorNonEmptyOrException"})
    model["relations"].append({"id": "generated_edge", "source": "control", "target": "generated", "relation": "CONDITION"})
    c["entity_ids"].extend(["control", "generated"])
    c["relation_ids"].append("generated_edge")
    guide = render_guide(bundle["graph"])
    assert "iteratorNonEmptyOrException" not in guide
    assert "Code predicate: result < 0" in guide
    assert any(s["text"] == "iteratorNonEmptyOrException" for s in model["sources"])


def test_long_purpose_is_not_an_envelope_failure(case):
    graph, view, response = case
    response["purpose"]["text"] = "Source-supported task description. " * 30
    assert len(response["purpose"]["text"]) > 600
    bundle = object_bundle(graph, response, view)
    assert bundle["assembly"]["usable"]
    assert response["purpose"]["text"] in bundle["handoff"]


def test_recorded_operation_is_a_valid_computation_target(case):
    graph, view, response = case
    source_id = next(s["id"] for s in view["sources"] if s["text"] == "loss = flux * duration")
    operation = next(e for e in view["entities"] if e["id"] == source_id)
    response["computations"][0]["computation_id"] = operation["id"]
    response["computations"][0]["meaning"]["text"] = "Compute the transported amount from outward flux and elapsed duration."
    bundle = object_bundle(graph, response, view)
    assert bundle["assembly"]["usable"]
    c = bundle["graph"]["scientific_model"]["computations"][0]
    assert c["id"] == operation["id"] and c["relation_ids"]


def test_non_string_computation_id_is_rejected_without_crashing(case):
    graph, view, response = case
    response["computations"][0]["computation_id"] = ["invalid"]
    bundle = object_bundle(graph, response, view)
    assert not bundle["assembly"]["usable"]
    assert bundle["assembly"]["enrichment"]["dropped"][0]["reason"] == "invalid_computation_fields"
