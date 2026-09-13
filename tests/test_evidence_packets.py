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


def helper_case(tmp_path, adapter, kernel):
    package = tmp_path / "pkg"
    package.mkdir()
    (package / "__init__.py").write_text("")
    (package / "adapter.py").write_text(adapter)
    (package / "kernel.py").write_text('raise RuntimeError("must not execute")\n' + kernel)
    packet = build_packet(tmp_path, multilingual=True)
    # Simulate the saved input: adapter entries exist, kernel entries do not.
    packet["entries"] = [e for e in packet["entries"] if e["path"] == "pkg/adapter.py"]
    packet["coverage"]["workflow_retrieval"] = {"references": []}
    graph = extract_objects(tmp_path, packet)
    return packet, graph


def test_missing_relative_helper_retrieved_with_bindings_branches_and_result_ids(tmp_path):
    packet, graph = helper_case(tmp_path,
        'from .kernel import advance as step\n'
        'def calculate(x, enabled):\n'
        '    if enabled:\n'
        '        return step(x, gain=2)\n'
        '    return step(x)\n',
        'def advance(value, gain=1):\n'
        '    if gain > 0:\n'
        '        return value * gain\n'
        '    return value\n')
    original = copy.deepcopy((packet, graph))
    result = build_connected_input(graph, packet, tmp_path)
    assert result == build_connected_input(graph, packet, tmp_path)
    assert (packet, graph) == original
    bodies = result["context"]["function_bodies"]
    assert len([b for b in bodies if b["path"] == "pkg/kernel.py"]) == 1
    links = result["context"]["helper_calls"]
    call = next(l for l in links if l["call_site"]["expression"] == "step(x, gain=2)")
    assert call["argument_bindings"] == [
        {"parameter": "value", "expression": "x", "origin": "caller"},
        {"parameter": "gain", "expression": "2", "origin": "caller"}]
    assert call["call_site"]["branch"] and call["return_sites"][0]["branch"]
    assert call["caller_operation_ids"] and call["caller_result_object_ids"]
    assert call["status"] == "static_candidate_not_runtime_dispatch"
    default = next(l for l in links if l["call_site"]["expression"] == "step(x)")
    assert default["argument_bindings"][1]["origin"] == "callee_default"
    assert all(l["callee_body_id"] in {b["id"] for b in bodies} for l in links)
    assert len(links) == len({l["id"] for l in links})
    assert all(set(p["helper_call_ids"]) <= {l["id"] for l in links} for p in result["evidence_packets"])


@pytest.mark.parametrize("statement,expression", [
    ("from . import kernel as k", "k.advance(x)"),
    ("import pkg.kernel as k", "k.advance(x)"),
    ("import pkg.kernel", "pkg.kernel.advance(x)"),
])
def test_helper_module_aliases(tmp_path, statement, expression):
    packet, graph = helper_case(tmp_path,
        statement + '\ndef calculate(x):\n    return ' + expression + '\n',
        'def advance(value):\n    return value * 2\n')
    result = build_connected_input(graph, packet, tmp_path)
    assert any(b["path"] == "pkg/kernel.py" for b in result["context"]["function_bodies"])


@pytest.mark.parametrize("adapter,kernel", [
    ('from .kernel import advance\ndef calculate(x, advance):\n    return advance(x)\n',
     'def advance(x):\n    return x * 2\n'),
    ('from .kernel import advance\nadvance = replacement\ndef calculate(x):\n    return advance(x)\n',
     'def advance(x):\n    return x * 2\n'),
    ('from .kernel import advance\ndef calculate(x):\n    return advance(x)\n',
     'def advance(x):\n    return x * 2\nadvance = replacement\n'),
    ('from .kernel import advance\ndef calculate(x):\n    return advance(x)\n',
     '@decorator\ndef advance(x):\n    return x * 2\n'),
])
def test_helper_shadowing_and_decorators_do_not_invent_links(tmp_path, adapter, kernel):
    packet, graph = helper_case(tmp_path, adapter, kernel)
    result = build_connected_input(graph, packet, tmp_path)
    assert not any(b["path"] == "pkg/kernel.py" for b in result["context"]["function_bodies"])
    assert result["context"]["helper_gaps"]


def test_helper_recursion_deduplicates_bodies_and_nested_returns_are_not_borrowed(tmp_path):
    packet, graph = helper_case(tmp_path,
        'from .kernel import advance\ndef calculate(x):\n    return advance(x)\n',
        'def advance(x):\n'
        '    def unrelated():\n        return 999\n'
        '    if x > 0:\n        return advance(x - 1)\n'
        '    return x\n')
    result = build_connected_input(graph, packet, tmp_path)
    bodies = result["context"]["function_bodies"]
    assert len([b for b in bodies if b["path"] == "pkg/kernel.py"]) == 1
    links = result["context"]["helper_calls"]
    assert any(l["caller_body_id"] == l["callee_body_id"] for l in links)
    assert all(r["expression"] != "999" for l in links for r in l["return_sites"])


def test_star_arguments_preserve_source_without_fabricated_binding(tmp_path):
    packet, graph = helper_case(tmp_path,
        'from .kernel import advance\ndef calculate(args):\n    return advance(*args)\n',
        'def advance(x):\n    return x * 2\n')
    result = build_connected_input(graph, packet, tmp_path)
    links = result["context"]["helper_calls"]
    assert links and links[0]["binding_status"] == "star_arguments_not_expanded"
    assert links[0]["argument_bindings"] == []


def test_helper_depth_budget_is_explicit(tmp_path, monkeypatch):
    import scicontext.callee_context as module
    packet, graph = helper_case(tmp_path,
        'from .kernel import advance\ndef calculate(x):\n    return advance(x)\n',
        'def advance(x):\n    return x * 2\n')
    monkeypatch.setattr(module, "MAX_HELPER_DEPTH", 0)
    result = build_connected_input(graph, packet, tmp_path)
    assert not any(b["path"] == "pkg/kernel.py" for b in result["context"]["function_bodies"])
    assert any(g["reason"] == "helper_depth_limit" for g in result["context"]["helper_gaps"])


def test_new_helper_symlink_is_not_read(tmp_path):
    packet, graph = helper_case(tmp_path,
        'from .kernel import advance\ndef calculate(x):\n    return advance(x)\n',
        'def advance(x):\n    return x * 2\n')
    (tmp_path / "outside.txt").write_text('private_material = "must not read"')
    (tmp_path / "pkg/kernel.py").unlink()
    (tmp_path / "pkg/kernel.py").symlink_to(tmp_path / "outside.txt")
    result = build_connected_input(graph, packet, tmp_path)
    assert "private_material" not in json.dumps(result)
    assert not any(b["path"] == "pkg/kernel.py" for b in result["context"]["function_bodies"])
