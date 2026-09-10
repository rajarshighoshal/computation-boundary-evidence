"""Synthetic scientific-object bindings and interpretation-bound probe receipts."""
import copy
import hashlib

import pytest

from scicontext.annotations import assemble_annotations, annotation_references
from scicontext.evidence import extract_evidence
from scicontext.graph import validate_graph
from scicontext.packet import render_catalog


@pytest.fixture
def example(tmp_path):
    (tmp_path / "science.py").write_text(
        "def collect(samples, output):\n"
        "    selected = samples\n"
        "    output.append(selected)\n"
        "    output += selected\n"
        "    return output\n")
    packet = {"entries": extract_evidence(tmp_path)["entries"]}
    entries = {entry["kind"]: entry for entry in packet["entries"]}
    draft = {"schema_version": "annotations-1.0", "quantities": [], "claims": [{
        "id": "c", "description": "Samples retain their grouping", "status": "unresolved",
        "scientific_object": "A collection of observed samples",
        "applicability": "Only if each input is one observation group",
        "alternative_interpretation": "Inputs may already be individual observations",
        "discriminating_observation": "Compare nested and flat input groups",
        "evidence": [entries["return"]["id"]],
        "consumer_ids": [entries["container_mutation"]["id"]]}]}
    return tmp_path, packet, entries, draft


@pytest.mark.parametrize("kind,symbol", [("parameter", "output"), ("assignment", "selected"),
    ("container_mutation", "output"), ("augmented_assignment", "output"), ("return", "output")])
def test_entity_ids_are_stable_selectable_and_not_equation_proof(example, kind, symbol):
    root, packet, entries, draft = example
    entity = entries[kind]
    draft["quantities"] = [{"id": "q", "meaning": "Observation collection", "entity_id": entity["id"]}]
    draft["claims"][0]["quantities"] = ["q"]
    draft["claims"][0]["implementation_id"] = entity["id"] if kind in {"parameter", "container_mutation", "augmented_assignment"} else None
    result = assemble_annotations(draft, packet, root)
    assert result["validation"]["valid"]
    assert result["graph"]["quantities"][0]["entity_id"] == entity["id"]
    assert result["graph"]["quantities"][0]["code_symbol"] == symbol
    assert result["graph"]["claims"][0]["quantity_ids"] == ["q"]
    assert result["analysis"]["alignments"][0]["status"] == "unknown"
    assert result["graph"]["quantities"][0]["dimensions"] is None
    assert result["assembly"]["code_bindings"][0]["binding_kind"] == "entity"
    assert f"entity_id={entity['id']}" in render_catalog(packet)
    assert extract_evidence(root)["entries"] == packet["entries"]
    assert "alternative_interpretation" in result["handoff"]
    assert "selected consumer" in result["handoff"]
    refs, keep = annotation_references(draft)
    assert entity["id"] in keep and entries["container_mutation"]["id"] in keep


def test_parameter_exact_span_resolves_wide_span_ambiguity_does_not(example):
    root, packet, entries, draft = example
    for end, status in [(1, "source_matched"), (5, "unknown")]:
        draft["quantities"] = [{"id": "q", "meaning": "collection", "code_ref": {
            "path": "science.py", "start_line": 1, "end_line": end, "symbol": "output"}}]
        result = assemble_annotations(draft, packet, root)
        assert result["assembly"]["code_bindings"][0]["status"] == status


def test_multiple_assignment_carriers_require_symbol_and_stale_ids_fail(tmp_path):
    path = tmp_path / "science.py"
    path.write_text("a = b = []\n")
    packet = {"entries": extract_evidence(tmp_path)["entries"]}
    entity_id = packet["entries"][0]["id"]
    draft = {"schema_version": "annotations-1.0", "claims": [],
             "quantities": [{"id": "q", "meaning": "Collection", "entity_id": entity_id}]}
    assert assemble_annotations(draft, packet, tmp_path)["assembly"]["code_bindings"][0]["status"] == "unknown"
    draft["quantities"][0]["symbol"] = "b"
    assert assemble_annotations(draft, packet, tmp_path)["assembly"]["code_bindings"][0]["status"] == "source_matched"
    path.write_text("a = b = [1]\n")
    assert assemble_annotations(draft, packet, tmp_path)["assembly"]["code_bindings"][0]["status"] == "unknown"


def test_probe_identity_tracks_claim_source_bindings_and_script(example):
    root, packet, entries, draft = example
    draft["quantities"] = [{"id": "q", "meaning": "Collection", "entity_id": entries["return"]["id"]}]
    draft["claims"][0]["quantities"] = ["q"]
    draft["probes"] = [{"id": "p", "claim_ids": ["c"], "script": "probes/check.py",
                        "source": "print('observed')\n", "description": "Observe grouping"}]
    initial = assemble_annotations(draft, packet, root)
    fingerprint = initial["probes"][0]["fingerprint"]
    receipt = {"id": "p", "claim_ids": ["c"], "description": "Observation", "status": "completed",
        "exit_code": 0, "duration_seconds": .1, "fingerprint": fingerprint,
        "script_sha256": hashlib.sha256(draft["probes"][0]["source"].encode()).hexdigest(),
        "artifact": "probes/p.json"}
    verified = assemble_annotations(draft, packet, root, probe_results=[receipt])
    assert verified["graph"]["observations"]
    assert "identity verified" in verified["handoff"] and "not scientific proof" in verified["handoff"]
    assert "print('observed')" in verified["handoff"]
    assert "unexecuted" in initial["handoff"]
    for group, field, value in [("claims", "applicability", "Different scope"),
                                ("quantities", "meaning", "Individual values"),
                                ("quantities", "entity_id", entries["assignment"]["id"]),
                                ("probes", "source", "print('changed')\n")]:
        changed = copy.deepcopy(draft)
        changed[group][0][field] = value
        result = assemble_annotations(changed, packet, root, probe_results=[receipt])
        assert result["probes"][0]["fingerprint"] != fingerprint
        assert not result["graph"]["observations"]
        assert "unexecuted" in result["handoff"]
    legacy = {key: value for key, value in receipt.items() if key != "fingerprint"}
    assert not assemble_annotations(draft, packet, root, probe_results=[legacy])["graph"]["observations"]


def test_legacy_graph_remains_readable(example):
    root, packet, _, draft = example
    graph = assemble_annotations(draft, packet, root)["graph"]
    for claim in graph["claims"]:
        for key in ("scientific_object", "applicability", "alternative_interpretation", "discriminating_observation", "consumer_ids"):
            claim.pop(key)
    assert validate_graph(graph, root)["valid"]


def test_probe_source_delivery_limit_is_explicit(example, monkeypatch):
    root, packet, _, draft = example
    base = assemble_annotations(draft, packet, root)
    cap = len(base["handoff"].encode()) + 2200
    monkeypatch.setattr("scicontext.annotations.MAX_HANDOFF_BYTES", cap)
    draft["probes"] = [{"id": "p", "claim_ids": ["c"], "script": "probes/check.py",
                        "source": "# public observation\n" * 500, "description": "Observe input"}]
    result = assemble_annotations(draft, packet, root)
    assert result["assembly"]["usable"]
    assert len(result["handoff"].encode()) <= cap
    assert "Probe source NOT supplied" in result["handoff"]
    assert "unexecuted" in result["handoff"]
    assert "public probe source omitted" in " ".join(result["assembly"]["unresolved"])


def test_ambiguous_binding_diagnostic_supplies_inspected_candidates(example):
    root, packet, entries, draft = example
    draft["quantities"] = [{"id": "q", "meaning": "Collection", "code_ref": {
        "path": "science.py", "start_line": 1, "end_line": 5, "symbol": "output"}}]
    result = assemble_annotations(draft, packet, root)
    reason = result["assembly"]["code_bindings"][0]["reason"]
    assert entries["container_mutation"]["id"] in reason
    assert "Inspected source candidates (syntax only)" in reason


@pytest.mark.parametrize("source", ["if measurement > 0:\n    pass\n", "assert measurement\n"])
def test_legacy_comparison_operand_reference_is_not_entity_carrier(tmp_path, source):
    (tmp_path / "science.py").write_text(source)
    packet = {"entries": extract_evidence(tmp_path)["entries"]}
    draft = {"schema_version": "annotations-1.0", "claims": [], "quantities": [{
        "id": "q", "meaning": "Measured value", "code_ref": {
            "path": "science.py", "start_line": 1, "end_line": 1, "symbol": "measurement"}}]}
    result = assemble_annotations(draft, packet, tmp_path)
    assert result["validation"]["valid"]
    assert result["assembly"]["code_bindings"][0]["status"] == "source_matched"
    assert result["assembly"]["code_bindings"][0]["binding_kind"] == "expression_operand"
    assert result["graph"]["quantities"][0]["entity_id"] is None
    assert result["graph"]["quantities"][0]["code_symbol"] == "measurement"


def test_rhs_operand_and_assignment_carrier_have_distinct_binding_kinds(tmp_path):
    (tmp_path / "science.py").write_text("result = measurement * 2\n")
    packet = {"entries": extract_evidence(tmp_path)["entries"]}
    entity_id = packet["entries"][0]["id"]
    draft = {"schema_version": "annotations-1.0", "claims": [], "quantities": [
        {"id": "q_operand", "meaning": "Measured input", "code_ref": {
            "path": "science.py", "start_line": 1, "end_line": 1, "symbol": "measurement"}},
        {"id": "q_carrier", "meaning": "Computed output", "code_ref": {
            "path": "science.py", "start_line": 1, "end_line": 1, "symbol": "result"}},
        {"id": "q_wrong_entity", "meaning": "Input is not this assignment's carrier",
         "entity_id": entity_id, "symbol": "measurement"}]}
    result = assemble_annotations(draft, packet, tmp_path)
    bindings = result["assembly"]["code_bindings"]
    assert bindings[0]["binding_kind"] == "expression_operand" and bindings[0]["entity_role"] is None
    assert bindings[1]["binding_kind"] == "entity" and bindings[1]["entity_role"] == "assignment"
    assert bindings[2]["status"] == "unknown"
    assert [q["entity_id"] for q in result["graph"]["quantities"]] == [None, entity_id, None]


def test_legacy_assertion_comparison_overlap_remains_ambiguous(tmp_path):
    (tmp_path / "science.py").write_text("assert measurement > 0\n")
    packet = {"entries": extract_evidence(tmp_path)["entries"]}
    draft = {"schema_version": "annotations-1.0", "claims": [], "quantities": [{
        "id": "q", "meaning": "Measured input", "code_ref": {
            "path": "science.py", "start_line": 1, "end_line": 1, "symbol": "measurement"}}]}
    result = assemble_annotations(draft, packet, tmp_path)
    assert result["assembly"]["code_bindings"][0]["status"] == "unknown"
    assert result["graph"]["quantities"][0]["entity_id"] is None


def test_mutation_argument_is_source_occurrence_not_receiver_entity(tmp_path):
    (tmp_path / "science.py").write_text("collection.append(measurement)\n")
    packet = {"entries": extract_evidence(tmp_path)["entries"]}
    draft = {"schema_version": "annotations-1.0", "claims": [], "quantities": [{
        "id": "q", "meaning": "Measured input", "code_ref": {
            "path": "science.py", "start_line": 1, "end_line": 1, "symbol": "measurement"}}]}
    result = assemble_annotations(draft, packet, tmp_path)
    assert result["assembly"]["code_bindings"][0]["status"] == "source_matched"
    assert result["assembly"]["code_bindings"][0]["binding_kind"] == "source_occurrence"
    assert result["graph"]["quantities"][0]["entity_id"] is None
