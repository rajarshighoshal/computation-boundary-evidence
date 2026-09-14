import json

from scicontext import object_context, source_backends
from scicontext.io import write_json


def test_query_regions_do_not_treat_available_files_as_roots():
    inventory = {"path": "whole.py", "start_line": 1, "end_line": 10000}
    assert source_backends.source_regions({"context": {"analysis_sources": [inventory]}}) == []
    region = {"path": "model.py", "start_line": 10, "end_line": 19}
    payload = {"context": {"analysis_sources": [inventory], "analysis_regions": [region, region,
        {"path": "private/test.py", "start_line": 1, "end_line": 8},
        {"path": "bad.py", "start_line": True, "end_line": 2}]}}
    assert source_backends.source_regions(payload) == [region]


def test_retrieved_regions_reach_interpreter_input():
    region = {"path": "model.py", "start_line": 8, "end_line": 20}
    graph = {"objects": [], "operations": [], "links": [], "unsupported": []}
    packet = {"entries": [], "documents": [], "coverage": {
        "task_local_retrieval": {"references": [region]}}}
    result = object_context.enrichment_input(graph, packet)
    assert source_backends.source_regions(result) == [region]


def test_selected_export_preserves_blocks_conditions_and_operand_roles(tmp_path):
    vertices = [
        {"id": "1", "label": "METHOD", "properties": {"FILENAME": "m.py", "FULL_NAME": "advance"}},
        {"id": "2", "label": "BLOCK", "properties": {"LINE_NUMBER": 2}},
        {"id": "3", "label": "CALL", "properties": {"CODE": "x - y", "LINE_NUMBER": 3}},
        {"id": "4", "label": "IDENTIFIER", "properties": {
            "CODE": "y", "ARGUMENT_INDEX": -1, "ARGUMENT_NAME": "normalization"}},
    ]
    edges = [{"outV": s, "inV": t, "label": kind, "properties": props} for s, t, kind, props in [
        ("1", "2", "AST", {}), ("2", "3", "AST", {}),
        ("3", "4", "ARGUMENT", {}), ("2", "3", "FALSE_BODY", {}),
        ("2", "3", "CDG", {"VARIABLE": "flag"})]]
    path = tmp_path / "selected.json"
    write_json(path, {"vertices": vertices, "edges": edges, "selection": {"methods": [
        {"id": "1", "name": "advance", "start_line": 1, "end_line": 5,
         "node_ids": ["1", "2", "3", "4"]}]}})
    graph = source_backends.read_joern(path, tmp_path, "PYTHONSRC")
    assert len(graph["nodes"]) == 4 and len(graph["links"]) == 5
    assert all(n["scope"] == "advance" for n in graph["nodes"])
    assert graph["nodes"][-1]["properties"]["ARGUMENT_NAME"] == "normalization"
    assert graph["links"][-1]["properties"] == {"VARIABLE": "flag"}
    assert graph["selection"]["methods"][0]["node_ids"][-1] == "joern:PYTHONSRC:4"


def analysis(code="x-y"):
    nodes = [{"id": "a", "kind": "CALL", "path": "m.py", "line": 3,
              "properties": {"CODE": code}},
             {"id": "b", "kind": "METHOD_PARAMETER_IN", "properties": {"NAME": "external_x"}}]
    return {"analyses": [{"backend": "joern", "language": "PYTHONSRC", "nodes": nodes,
        "links": [{"source": "b", "target": "a", "role": "REACHING_DEF", "properties": {"VARIABLE": "x"}}],
        "selection": {"methods": [{"id": "m", "node_ids": ["a"]}]}}], "gaps": []}


def test_attachment_retains_boundary_nodes_and_structured_edge_properties():
    payload = source_backends.attach_source_analysis({"context": {}}, analysis())
    rows = payload["context"]["analysis_sources"]
    lookup = {r["id"]: r for r in rows}
    edge = next(r for r in rows if r["kind"] == "edge")
    assert edge["source"] in lookup and edge["target"] in lookup
    assert edge["properties"] == {"VARIABLE": "x"}
    assert lookup["sa_b"]["path"] == "analysis://joern/boundary"
    assert payload["source_analysis_summary"]["joern_nodes"] == 2


def test_full_evidence_is_not_pruned_by_model_transport_budget(monkeypatch):
    monkeypatch.setattr(object_context, "ENRICHMENT_MAX_BYTES", 10000)
    payload = source_backends.attach_source_analysis({"context": {}}, analysis("x" * 12000))
    assert len(payload["context"]["analysis_sources"]) == 3
    assert payload["source_analysis_summary"]["omitted_methods"] == []
    assert "model transport check follows abstraction" in payload["source_analysis_summary"]["storage_scope"]



def test_attachment_does_not_repeat_code_or_assign_source_lines_to_edges():
    result = source_backends.attach_source_analysis({"context": {}}, analysis("preserve_operand_identity(x)"))
    rows = result["context"]["analysis_sources"]
    call = next(r for r in rows if r["kind"] == "CALL")
    assert call["text"] == "preserve_operand_identity(x)"
    assert "CODE" not in call["properties"]
    edge = next(r for r in rows if r["kind"] == "edge")
    assert not {"path", "start_line", "end_line", "text"} & edge.keys()


def test_old_selection_size_is_labelled_as_pre_analysis():
    result = source_backends.attach_source_analysis({"context": {}, "selection": {"serialized_bytes": 50}}, analysis())
    assert result["selection"] == {"serialized_bytes": 50, "serialized_bytes_scope": "before_source_analysis"}


def test_ambiguous_dispatch_is_a_set_not_hundreds_of_apparent_calls():
    raw = analysis()
    graph = raw["analyses"][0]
    graph["nodes"].extend({"id": f"candidate_{i}", "kind": "METHOD", "properties": {"NAME": "read"}}
                          for i in range(20))
    graph["links"].extend({"source": "a", "target": f"candidate_{i}", "role": "CALL"}
                          for i in range(20))
    result = source_backends.attach_source_analysis({"context": {}}, raw)
    rows = result["context"]["analysis_sources"]
    call = next(r for r in rows if r["id"] == "sa_a")
    assert call["dispatch"]["status"] == "unresolved_alternatives"
    assert call["dispatch"]["boundary_candidate_count"] == 20
    assert not any(r["id"].startswith("sa_candidate_") for r in rows)
    assert len(raw["analyses"][0]["links"]) == 21  # Full evidence is unchanged.
    assert any(r.get("relation") == "REACHING_DEF" for r in rows)


def test_single_target_interface_and_selected_callee_are_not_compressed_away():
    raw = analysis()
    graph = raw["analyses"][0]
    graph["nodes"].append({"id": "target", "kind": "METHOD", "properties": {"NAME": "scale"}})
    graph["links"].append({"source": "a", "target": "target", "role": "CALL"})
    rows = source_backends.attach_source_analysis({"context": {}}, raw)["context"]["analysis_sources"]
    assert any(r.get("target") == "sa_target" for r in rows)
    assert all("dispatch" not in r for r in rows)
    graph["selection"]["methods"].append({"id": "target", "node_ids": ["target"]})
    for i in range(3):
        graph["nodes"].append({"id": str(i), "kind": "METHOD", "properties": {"NAME": "other"}})
        graph["links"].append({"source": "a", "target": str(i), "role": "CALL"})
    rows = source_backends.attach_source_analysis({"context": {}}, raw)["context"]["analysis_sources"]
    assert any(r.get("target") == "sa_target" for r in rows)
    assert next(r for r in rows if r["id"] == "sa_a")["dispatch"]["boundary_candidate_count"] == 3


def test_no_task_regions_never_starts_full_graph_export(tmp_path, monkeypatch):
    (tmp_path / "m.py").write_text("x = 1\n")
    monkeypatch.setattr(source_backends.shutil, "which", lambda name: __file__)
    monkeypatch.setattr(source_backends, "installed_frontends", lambda: {"PYTHONSRC"})
    def forbidden(*args):
        raise AssertionError("analyzer should not run without a task region")
    monkeypatch.setattr(source_backends, "joern_graph", forbidden)
    result = source_backends.analyze_sources(tmp_path, tmp_path / "out")
    assert result["analyses"] == []
    assert result["gaps"] == [{"backend": "joern", "language": "PYTHONSRC", "reason": "no_task_regions"}]


def test_cli_passes_recovered_regions_to_analyzer(tmp_path, monkeypatch):
    request = tmp_path / "input.json"
    region = {"path": "m.py", "start_line": 2, "end_line": 4}
    write_json(request, {"context": {"analysis_regions": [region]}})
    calls = []
    monkeypatch.setattr(source_backends, "analyze_sources", lambda *args: calls.append(args))
    source_backends.main(["--root", str(tmp_path), "--output", str(tmp_path / "out"), "--input", str(request)])
    assert calls == [(tmp_path, tmp_path / "out", [region])]
