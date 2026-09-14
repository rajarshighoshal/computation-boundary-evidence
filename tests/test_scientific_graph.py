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


def test_cut_calls_stay_as_boundary_references(tmp_path):
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
