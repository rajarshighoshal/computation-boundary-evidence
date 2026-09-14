import gzip
import json

import pytest

from scicontext.execution_seed import read_execution_edges
from scicontext.packet import build_packet
from scicontext.scientific_graph import _scope_key, build_graph
from scicontext.scientific_objects import extract_objects


def write_prepared(root):
    """Minimal prepared extraction outputs: packet, objects graph, trace."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "model.py").write_text(
        'def advance(energy, flux, dt):\n'
        '    """Positive flux leaves the stored energy; dt is elapsed time."""\n'
        '    residual = energy - flux * dt\n'
        '    return residual\n')
    (root / "reproduce.py").write_text(
        'from model import advance\n'
        'def run():\n'
        '    return advance(3.0, 1.0, 0.5)\n')
    packet = build_packet(root)
    graph = extract_objects(root, packet)
    graph["dependence_signatures"] = [
        {"func": ["reproduce.py", "<module>", 1], "instances": 1, "arguments": {}},
        {"func": ["reproduce.py", "run", 2], "instances": 1, "arguments": {}},
        {"func": ["model.py", "advance", 1], "instances": 1, "arguments": {"energy": "dependent"}}]
    graph["objects"].append({
        "id": "cl_fixture", "kind": "constraint_locus", "path": "model.py", "scope": "advance",
        "properties": {"rule_id": "R4", "constraint_type": "distinctness", "status": "violated",
                       "predicate_source": "script_declared", "evidence": {"measures": {}},
                       "static_candidates": [{"path": "model.py", "line": 3}]},
        "source_span": {"start_line": 1, "end_line": 1},
        "symbol": "distinctness@advance", "source_entry_ids": []})
    store = root.parent / "store"
    store.mkdir(exist_ok=True)
    (store / "scientific-objects.json").write_text(json.dumps(graph))
    (store / "packet.json").write_text(json.dumps(packet))
    trace = store / "trace"
    trace.mkdir(exist_ok=True)
    with gzip.open(trace / "trace.jsonl.gz", "wt") as stream:
        for row in [{"pid": 1, "seq": 1, "file": "reproduce.py", "name": "<module>", "line": 1},
                    {"pid": 1, "seq": 2, "parent_seq": 1, "file": "reproduce.py", "name": "run", "line": 2},
                    {"pid": 1, "seq": 3, "parent_seq": 2, "file": "model.py", "name": "advance", "line": 1}]:
            stream.write(json.dumps(row) + "\n")
    return store / "scientific-objects.json", store / "packet.json", trace


def test_graph_connects_observed_workflow_to_findings_and_dependencies(tmp_path):
    graph_path, packet_path, trace = write_prepared(tmp_path / "task")
    result = build_graph(graph_path, packet_path, trace)
    nodes = {node["name"]: node for node in result["nodes"]}
    assert {"<module>", "run", "advance"} <= set(nodes)
    assert nodes["advance"]["findings"] and nodes["advance"]["findings"][0]["rule"] == "R4"
    assert nodes["advance"]["computation_id"]
    assert nodes["advance"]["source_ids"] and nodes["advance"]["entity_ids"]
    edges = {(item["from"], item["to"], item["relation"]) for item in result["edges"]}
    by_id = {node["id"]: node["name"] for node in result["nodes"]}
    assert (nodes["<module>"]["id"], nodes["run"]["id"], "calls") in edges
    assert (nodes["run"]["id"], nodes["advance"]["id"], "calls") in edges
    assert all(name for name in by_id.values())
    assert result["serialized_bytes"] < 8000
    assert result["summary"]["findings"] == 1


def test_graph_without_packet_or_trace_keeps_findings(tmp_path):
    graph_path, _, _ = write_prepared(tmp_path / "task")
    result = build_graph(graph_path)
    assert any(node["findings"] for node in result["nodes"])
    assert result["summary"]["findings"] == 1


def test_observed_relations_remain_visible_without_becoming_findings(tmp_path):
    from scicontext.science_tools import ScienceStore
    root = tmp_path / "task"
    graph_path, packet_path, trace = write_prepared(root)
    graph = json.loads(graph_path.read_text())
    locus = next(o for o in graph["objects"] if o["kind"] == "constraint_locus")
    locus["properties"].update(status="observed", predicate_source="execution_observation")
    locus["properties"]["evidence"]["pairs"] = [
        {"a": 2, "b": 3, "input_relation": "different", "output_relation": "identical"}]
    graph["dynamic"] = {"insensitive_pairs": [
        {"rule": "R1", "func": ["model.py", "advance", 1], "a": 3, "b": 4,
         "input_relation": "param_delta", "output_relation": "identical",
         "delta_param": {"name": "dt", "a": "1.0", "b": "2.0"}}]}
    graph_path.write_text(json.dumps(graph))
    result = build_graph(graph_path, packet_path, trace)
    node = next(n for n in result["nodes"] if n["name"] == "advance")
    assert node["findings"] == []
    assert {o["rule"] for o in node["observations"]} == {"R1", "R4"}
    assert all(o["status"] == "observed" and o["pairs"] for o in node["observations"])
    assert all(o["evidence_source"] == "execution_observation" for o in node["observations"])
    assert {o["type"] for o in node["observations"]} == {"parameter_response", "matching_outputs"}
    assert result["summary"]["findings"] == 0 and result["summary"]["observations"] == 2
    store = ScienceStore(root, graph_path.parent)
    store.prepare()
    shown = store.dispatch({"action": "inspect", "target": node["id"]})
    assert shown["observations"] == node["observations"]


def test_execution_edges_follow_parent_links(tmp_path):
    _, _, trace = write_prepared(tmp_path / "task")
    edges = read_execution_edges(trace)
    pairs = {(edge["caller"]["name"], edge["callee"]["name"]) for edge in edges}
    assert pairs == {("<module>", "run"), ("run", "advance")}


@pytest.mark.parametrize("raw, expected", [
    ("<module>.run_workflow@85", "run_workflow"),
    ("<module>.TerpsichoreRadialGrid@13.uniform@41", "TerpsichoreRadialGrid.uniform"),
    ("<module>.namespace_definition:openmc@518.Cell::set_rotation@48:1118", "openmc.Cell::set_rotation"),
    ("<module>.namespace_definition:alpha@1.Solver::step@5:10", "alpha.Solver::step"),
    ("<module>.namespace_definition:beta@9.Solver::step@5:10", "beta.Solver::step"),
    ("<module>.namespace_definition:openmc@518.namespace_definition:model@721", "model@721"),
    ("<module>.namespace_definition:openmc@212", "openmc@212"),
    ("<script>", "<module>"),
    (None, "<module>"),
])
def test_scope_key_normalizes_python_and_joern_scopes(raw, expected):
    assert _scope_key(raw) == expected


def test_graph_surfaces_runner_failure_instead_of_violation(tmp_path):
    graph_path, packet_path, trace = write_prepared(tmp_path / "task")
    graph = json.loads(graph_path.read_text())
    graph["objects"] = [item for item in graph["objects"] if item.get("kind") != "constraint_locus"]
    graph["dynamic"] = {"reproduction": {"status": "runner_failure", "classification": "runner_failure"}}
    graph_path.write_text(json.dumps(graph))
    result = build_graph(graph_path, packet_path, trace)
    assert result["reproduction"]["classification"] == "runner_failure"
    assert result["summary"]["findings"] == 0


def test_cut_calls_stay_as_boundary_references(tmp_path, monkeypatch):
    import scicontext.scientific_graph as module
    monkeypatch.setattr(module, "MAX_NODES", 3)  # Force actual cuts, not materialized callees.
    graph_path, packet_path, trace = write_prepared(tmp_path / "task")
    with gzip.open(trace / "trace.jsonl.gz", "at") as stream:
        for index in range(8):
            stream.write(json.dumps({"pid": 1, "seq": 10 + index, "parent_seq": 2,
                                     "file": f"helper{index}.py", "name": "helper",
                                     "line": 3 + index}) + "\n")
    result = build_graph(graph_path, packet_path, trace)
    run = next(node for node in result["nodes"] if node["name"] == "run")
    calls = [ref for ref in run["boundary"] if ref["relation"] == "calls"]
    assert len(calls) == 8, "cut calls must not be squeezed out by the boundary cap"


def test_single_call_workflow_chain_is_not_crowded_out_by_hot_helpers(tmp_path):
    graph_path, packet_path, trace = write_prepared(tmp_path / "task")
    graph = json.loads(graph_path.read_text())
    graph["objects"] = [o for o in graph["objects"] if o.get("kind") != "constraint_locus"]
    graph["dependence_signatures"] = [
        {"func": ["helpers.py", f"hot_{i}", i+1], "instances": 64, "arguments": {}}
        for i in range(25)]
    graph_path.write_text(json.dumps(graph))
    with gzip.open(trace / "trace.jsonl.gz", "wt") as stream:
        rows = [
            {"seq": 1, "file": "reproduce.py", "name": "<module>", "line": 1},
            {"seq": 2, "parent_seq": 1, "file": "bridge.py", "name": "run_workflow", "line": 4},
            {"seq": 3, "parent_seq": 2, "file": "model.py", "name": "advance", "line": 1}]
        rows += [{"seq": i+4, "parent_seq": 3, "file": "helpers.py", "name": f"hot_{i}", "line": i+1}
                 for i in range(25)]
        for row in rows:
            stream.write(json.dumps(row) + "\n")
    result = build_graph(graph_path, packet_path, trace)
    nodes = {n["name"]: n for n in result["nodes"]}
    assert {"<module>", "run_workflow", "advance"} <= set(nodes)
    assert nodes["advance"]["source_ids"]
    assert nodes["run_workflow"]["line"] == 4 and not nodes["run_workflow"]["source_ids"]
    pairs = {(e["from"], e["to"]) for e in result["edges"] if e["relation"] == "calls"}
    assert (nodes["<module>"]["id"], nodes["run_workflow"]["id"]) in pairs
    assert (nodes["run_workflow"]["id"], nodes["advance"]["id"]) in pairs
    assert len(result["nodes"]) == 20


def test_workflow_reporting_helpers_do_not_fill_the_initial_graph(tmp_path):
    graph_path, packet_path, trace = write_prepared(tmp_path / "task")
    graph = json.loads(graph_path.read_text())
    graph["objects"] = [o for o in graph["objects"] if o.get("kind") != "constraint_locus"]
    graph_path.write_text(json.dumps(graph))
    with gzip.open(trace / "trace.jsonl.gz", "at") as stream:
        for i in range(25):
            stream.write(json.dumps({"pid": 1, "seq": 10+i, "parent_seq": 2,
                                     "file": "reproduce.py", "name": f"metric_{i}", "line": 100+i}) + "\n")
    result = build_graph(graph_path, packet_path, trace)
    assert any(n["name"] == "advance" and n["source_ids"] for n in result["nodes"])
