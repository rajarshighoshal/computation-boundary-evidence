"""Connected interpreter inputs: source-backed, bounded, no model/candidate execution."""
import copy
import asyncio
import hashlib
import json
from pathlib import Path

import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from scicontext.evidence_packets import build_connected_input
from scicontext.object_context import enrichment_input
from scicontext.packet import build_packet
from scicontext.scientific_objects import extract_objects
from scicontext.tool_cli import main as helper_main


@pytest.fixture
def chain(tmp_path):
    root = tmp_path / "task"
    root.mkdir()
    (root / "model.py").write_text(
        'raise RuntimeError("candidate code must not run")\n'
        'def advance_inventory(volume, flux, dt):\n'
        '    """Positive flux leaves the reservoir; dt is elapsed time."""\n'
        '    return volume - flux * dt\n\n'
        'def report_mass(volume, density):\n'
        '    """Density converts volume into stored mass."""\n'
        '    return volume * density\n')
    (root / "reproduce.py").write_text(
        'from model import advance_inventory, report_mass\n'
        'initial = 10.0\nflux = 0.1\ndt = 2.0\ndensity = 1000.0\n'
        'updated = advance_inventory(initial, flux, dt)\n'
        'mass = report_mass(updated, density)\n'
        'assert mass >= 0\n')
    (root / "README.md").write_text("Stored mass equals density times volume. Positive flux removes water.\n")
    context = tmp_path / "context"
    context.mkdir()
    (context / "task_statement.md").write_text("Repair the stored mass reported after an outward flux changes the inventory.\n")
    packet = build_packet(root, context, multilingual=True)
    graph = extract_objects(root, packet)
    return root, context, packet, graph


def test_connected_packet_keeps_calculation_chain_and_complete_bodies(chain):
    root, _, packet, graph = chain
    original = copy.deepcopy((graph, packet))
    result = build_connected_input(graph, packet, root)
    assert result == build_connected_input(graph, packet, root)
    assert (graph, packet) == original
    bodies = result["context"]["function_bodies"]
    assert any("def advance_inventory" in b["text"] and "return volume - flux * dt" in b["text"] for b in bodies)
    assert any("def report_mass" in b["text"] and "return volume * density" in b["text"] for b in bodies)
    assert "Positive flux" in json.dumps(result["context"])
    assert any(b["anchor"]["reason"] == "workflow_comparison" for b in result["evidence_packets"])
    object_ids = {o["id"] for o in result["objects"]}
    node_ids = object_ids | {o["id"] for o in result["operations"]}
    assert all(l["source"] in node_ids and l["target"] in node_ids for l in result["links"])
    for op in result["operations"]:
        assert set(op["output_ids"]) <= object_ids
        assert all(i.get("object_id") is None or i["object_id"] in object_ids for i in op["inputs"])
    for bundle in result["evidence_packets"]:
        assert set(bundle["object_ids"]) <= object_ids
        assert "no new scientific requirements" in bundle["claim_scope"]
    original_objects = {o["id"]: o for o in graph["objects"]}
    assert all(o == original_objects[o["id"]] for o in result["objects"])


def test_candidate_callee_links_remain_candidates(chain):
    root, _, packet, graph = chain
    result = build_connected_input(graph, packet, root)
    candidates = [l for b in result["evidence_packets"] for l in b["candidate_call_links"]]
    assert candidates
    assert all(l in graph["links"] for l in candidates)
    assert all(l["relation"].startswith(("possible_", "may_")) for l in candidates)


def test_source_hash_changes_are_reported_not_silently_reread(chain):
    root, _, packet, graph = chain
    (root / "model.py").write_text("def other():\n    return 999\n")
    result = build_connected_input(graph, packet, root)
    assert not any(b["path"] == "model.py" for b in result["context"]["function_bodies"])
    assert any(g["reason"] == "source_hash_mismatch" for b in result["evidence_packets"] for g in b["gaps"])


def test_body_retrieval_does_not_follow_symlinks(chain, tmp_path):
    root, _, packet, graph = chain
    outside = tmp_path / "outside.py"
    outside.write_text("private_material = 'do not read'\n")
    (root / "model.py").unlink()
    (root / "model.py").symlink_to(outside)
    result = build_connected_input(graph, packet, root)
    assert "private_material" not in json.dumps(result)
    assert any(g["reason"] == "symlink" for b in result["evidence_packets"] for g in b["gaps"])


def test_archived_records_without_source_keep_explicit_body_gap(chain):
    _, _, packet, graph = chain
    result = build_connected_input(graph, packet)
    assert result["context"]["function_bodies"] == []
    assert result["context"]["code_passages"]
    assert any(g["reason"] == "source_root_unavailable" for b in result["evidence_packets"] for g in b["gaps"])


def test_budget_omits_whole_packets_not_required_operation_operands(chain):
    root, _, packet, graph = chain
    result = build_connected_input(graph, packet, root, max_objects=1)
    assert len(result["objects"]) <= 1
    assert result["selection"]["omitted_packets"]
    assert all(set(op["output_ids"]) <= {o["id"] for o in result["objects"]} for op in result["operations"])
    small = build_connected_input(graph, packet, root, max_bytes=5000)
    assert len(json.dumps(small, ensure_ascii=False).encode()) <= 5000


def test_source_associated_observations_are_retained_without_new_violation(chain):
    root, _, packet, graph = chain
    observation = {"id": "cl_observed", "kind": "constraint_locus", "path": "reproduce.py",
                   "scope": "<script>", "source_span": {"start_line": 0, "end_line": 0},
                   "source_entry_ids": [], "properties": {"status": "observed", "measures": {"mass": 1.0}}}
    graph["objects"].append(observation)
    result = build_connected_input(graph, packet, root)
    assert observation in result["objects"]
    assert any("cl_observed" in b["observation_ids"] for b in result["evidence_packets"])


def test_helper_wires_connected_input_without_changing_enrichment_schema(chain, capsys):
    root, context, _, _ = chain
    out = root / "outputs"
    helper_main(["packet", "--root", str(root), "--context-root", str(context), "--task-id", "synthetic",
                 "--output", str(out / "packet.json"), "--catalog", str(out / "catalog.md"),
                 "--objects-output", str(out / "graph.json"), "--enrichment-input", str(out / "input.json"),
                 "--connected-evidence"])
    capsys.readouterr()
    result = json.loads((out / "input.json").read_text())
    assert result["selection"]["strategy"] == "connected_evidence_packets_v1"
    assert result["evidence_packets"] and result["context"]["function_bodies"]
    assert json.loads((out / "graph.json").read_text())["schema_version"] == "scientific-objects-1.0"


def test_existing_input_api_preserves_historical_strategy_unless_opted_in(chain):
    root, _, packet, graph = chain
    before = enrichment_input(graph, packet)
    after = enrichment_input(graph, packet, root=root, connected=True)
    assert "evidence_packets" not in before
    assert after["evidence_packets"]


def test_oversized_body_is_reported_as_missing_not_cut_mid_function(chain, monkeypatch):
    import scicontext.evidence_packets as module
    root, _, packet, graph = chain
    monkeypatch.setattr(module, "MAX_BODY_CHARS", 20)
    result = build_connected_input(graph, packet, root)
    assert result["context"]["function_bodies"] == []
    assert any(g["reason"] == "function_body_exceeds_limit" for b in result["evidence_packets"] for g in b["gaps"])


def test_missing_dependency_is_explicit(chain):
    root, _, packet, graph = chain
    for op in graph["operations"]:
        graph["links"].append({"source": "missing_recorded_value", "target": op["id"], "relation": "input:unknown"})
    result = build_connected_input(graph, packet, root)
    assert any(g.get("node_id") == "missing_recorded_value" and g["reason"] == "graph_endpoint_missing"
               for b in result["evidence_packets"] for g in b["gaps"])


def test_native_recorded_function_region_is_not_mislabeled_as_proven_dispatch(tmp_path):
    text = "double pressure(double mass, double volume) {\n  return mass / volume;\n}\n"
    (tmp_path / "model.cpp").write_text(text)
    entry = {"id": "ev_fn", "kind": "signature", "path": "model.cpp", "start_line": 1,
             "end_line": 1, "scope": "pressure", "sha256": hashlib.sha256(text.encode()).hexdigest(),
             "entity_symbols": ["pressure"], "text": "double pressure(double mass, double volume)"}
    graph = {"objects": [{"id": "so_fn", "kind": "code_interface", "source_entry_ids": ["ev_fn"],
                           "path": "model.cpp", "scope": "pressure", "properties": {}, "roles": []}],
             "operations": [], "links": [], "unsupported": []}
    packet = {"entries": [entry], "documents": [], "coverage": {"workflow_retrieval": {"references": [
        {"path": "model.cpp", "start_line": 1, "end_line": 3}]}}}
    result = build_connected_input(graph, packet, tmp_path)
    body = result["context"]["function_bodies"][0]
    assert body["text"] == text.rstrip("\n")
    assert body["kind"] == "recorded_function_region"
    assert result["evidence_packets"][0]["candidate_call_links"] == []


def test_production_preparation_requests_connected_input_in_both_helper_stages():
    from scicontext.pier_agent import ScientificCodex
    helper = AsyncMock(return_value={"status": "ready"})
    driver = SimpleNamespace(condition="science", root="/app/task_synthetic", task_id="synthetic", _helper=helper)
    asyncio.run(ScientificCodex.prepare(driver, 1200))
    commands = [call.args[0] for call in helper.await_args_list]
    input_stages = [command for command in commands if "--enrichment-input" in command]
    assert len(input_stages) == 2
    assert all("--connected-evidence" in command for command in input_stages)
