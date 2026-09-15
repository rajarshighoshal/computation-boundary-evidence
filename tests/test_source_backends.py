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


def test_distill_joern_contracts_extracts_external_calls_signatures_and_conditions():
    vertices = [
        {"id": "1", "label": "METHOD", "properties": {"NAME": "spawn_workers", "FULL_NAME": "openmc::spawn_workers",
                                                      "SIGNATURE": "int(int)", "TYPE_FULL_NAME": "int", "LINE_NUMBER": 10}},
        {"id": "2", "label": "METHOD_PARAMETER_IN", "properties": {"NAME": "n_threads", "TYPE_FULL_NAME": "int", "ORDER": "1"}},
        {"id": "3", "label": "CALL", "properties": {"NAME": "<operator>.assignment", "CODE": "threads = malloc(n_threads)"}},
        {"id": "4", "label": "CALL", "properties": {"NAME": "pthread_create",
                                                     "METHOD_FULL_NAME": "pthread_create:int(pthread_t*,void*,void*(*)(void*),void*)",
                                                     "CODE": "pthread_create(&threads[i], NULL, worker, (void*)i)",
                                                     "LINE_NUMBER": 12, "DISPATCH_TYPE": "STATIC_DISPATCH"}},
        {"id": "5", "label": "METHOD", "properties": {"NAME": "pthread_create", "FULL_NAME": "pthread_create",
                                                      "IS_EXTERNAL": "true",
                                                      "SIGNATURE": "int(pthread_t*, const pthread_attr_t*, void*(*)(void*), void*)"}},
        {"id": "6", "label": "CONTROL_STRUCTURE", "properties": {"CONTROL_STRUCTURE_TYPE": "IF", "CODE": "if (rc != 0)", "LINE_NUMBER": 13}},
        {"id": "7", "label": "CALL", "properties": {"NAME": "<operator>.notEquals", "CODE": "rc != 0"}},
        {"id": "8", "label": "RETURN", "properties": {"CODE": "return -1;", "LINE_NUMBER": 14}},
        {"id": "9", "label": "LITERAL", "properties": {"CODE": "-1", "TYPE_FULL_NAME": "int"}},
        {"id": "10", "label": "RETURN", "properties": {"CODE": "return 0;", "LINE_NUMBER": 16}},
    ]
    edges = [
        {"outV": "1", "inV": "2", "label": "AST"},
        {"outV": "1", "inV": "3", "label": "AST"},
        {"outV": "1", "inV": "4", "label": "AST"},
        {"outV": "4", "inV": "5", "label": "CALL"},
        {"outV": "1", "inV": "6", "label": "AST"},
        {"outV": "6", "inV": "7", "label": "CONDITION"},
        {"outV": "6", "inV": "8", "label": "AST"},
        {"outV": "8", "inV": "9", "label": "AST"},
        {"outV": "1", "inV": "10", "label": "AST"},
    ]
    nodes = {v["id"]: {"id": v["id"], "kind": v["label"], "properties": v["properties"], "line": v["properties"].get("LINE_NUMBER")} for v in vertices}
    links = [{"source": e["outV"], "target": e["inV"], "role": e["label"]} for e in edges]
    selection = {"methods": [{"id": "1", "name": "openmc::spawn_workers", "node_ids": ["1", "2", "3", "4", "6", "7", "8", "9", "10"], "start_line": 10, "end_line": 16}]}
    contracts = source_backends.distill_joern_contracts(nodes, links, selection, "NEWC")
    assert len(contracts) == 1
    c = contracts[0]
    assert c["name"] == "spawn_workers"
    assert c["scope"] == "openmc::spawn_workers"
    assert c["return_type"] == "int"
    assert c["parameters"] == [{"name": "n_threads", "type": "int", "order": "1"}]

    # Operator calls like <operator>.assignment and <operator>.notEquals are filtered out
    assert all(not call["callee"].startswith("<operator>") for call in c["calls"])
    # External calls include pthread_create with clean arguments
    ext_calls = c["external_calls"]
    assert len(ext_calls) == 1
    pthread = ext_calls[0]
    assert pthread["callee"] == "pthread_create"
    assert pthread["signature"] == "int(pthread_t*, const pthread_attr_t*, void*(*)(void*), void*)"
    assert pthread["arguments"] == ["&threads[i]", "NULL", "worker", "(void*)i"]
    assert pthread["external"] is True

    # Governing conditions: if (rc != 0) governing return -1;
    conds = c["governing_conditions"]
    assert len(conds) == 1
    assert conds[0]["type"] == "IF"
    assert conds[0]["condition"] == "rc != 0"
    assert "return -1;" in conds[0]["governs"]

    # Return expressions
    returns = c["return_expressions"]
    assert len(returns) == 2
    assert returns[0]["expression"] == "-1"
    assert returns[1]["expression"] == "0"

    # Boundary types
    assert "int" in c["boundary_types"]
    assert "openmc" in c["boundary_types"] or "pthread_t" in c["boundary_types"] or "int" in c["boundary_types"]


def test_read_joern_and_attachment_yield_interface_contracts(tmp_path):
    vertices = [
        {"id": "1", "label": "METHOD", "properties": {"NAME": "advance", "FULL_NAME": "advance"}},
        {"id": "2", "label": "CONTROL_STRUCTURE", "properties": {"CONTROL_STRUCTURE_TYPE": "IF"}},
        {"id": "3", "label": "CALL", "properties": {"NAME": "<operator>.logicalNot", "CODE": "!flag"}},
        {"id": "4", "label": "CALL", "properties": {"NAME": "compute", "CODE": "compute(flux, dt)",
                                                     "ARGUMENT_NAME": "normalization"}},
    ]
    edges = [
        {"outV": "1", "inV": "2", "label": "AST"},
        {"outV": "2", "inV": "3", "label": "AST"},
        {"outV": "2", "inV": "3", "label": "CONDITION"},
        {"outV": "2", "inV": "4", "label": "AST"},
        {"outV": "1", "inV": "3", "label": "REACHING_DEF", "properties": {"VARIABLE": "flag"}},
    ]
    path = tmp_path / "cpg.json"
    write_json(path, {"vertices": vertices, "edges": edges,
                      "selection": {"methods": [{"id": "1", "name": "advance", "start_line": 1, "end_line": 5,
                                                 "node_ids": ["1", "2", "3", "4"]}]}})
    graph = source_backends.read_joern(path, tmp_path, "PYTHONSRC")
    assert "interface_contracts" in graph
    assert len(graph["interface_contracts"]) == 1
    c = graph["interface_contracts"][0]
    assert c["name"] == "advance"
    assert c["governing_conditions"][0]["condition"] == "!flag"
    assert c["external_calls"][0]["callee"] == "compute"

    # Now verify attachment puts contracts into summary and payload
    payload = source_backends.attach_source_analysis({"context": {}}, {"analyses": [graph], "gaps": []})
    summary = payload["source_analysis_summary"]
    assert "interface_contracts" in summary
    assert len(summary["interface_contracts"]) == 1
    assert summary["interface_contracts"][0]["name"] == "advance"
    assert "interface_contracts" in payload


def test_distill_native_contracts_for_fortran_and_matlab():
    entries = [
        {"kind": "signature", "path": "model.f90", "start_line": 8, "symbol": "advance",
         "text": "function advance(initial, flow, dt) result(updated)", "scope": "<module>.advance",
         "native": {"function_name": "advance", "return_type": "real"}},
        {"kind": "parameter", "path": "model.f90", "start_line": 9, "symbol": "initial",
         "function_scope": "<module>.advance", "scope": "<module>.advance.initial",
         "native": {"declaration_text": "real, intent(in) :: initial"}},
        {"kind": "call", "path": "model.f90", "start_line": 11, "text": "scale(flow, dt)",
         "function_scope": "<module>.advance", "scope": "<module>.advance",
         "native_expression": {"kind": "call", "callee": "scale", "arguments": [{"text": "flow"}, {"text": "dt"}]}},
        {"kind": "return", "path": "model.f90", "start_line": 12, "text": "updated",
         "function_scope": "<module>.advance", "scope": "<module>.advance",
         "native_expression": {"text": "updated"}},
    ]
    contracts = source_backends.distill_native_contracts(entries, "fortran")
    assert len(contracts) == 1
    c = contracts[0]
    assert c["name"] == "advance"
    assert c["return_type"] == "real"
    assert c["parameters"] == [{"name": "initial", "type": "real, intent(in)", "order": 1}]
    assert c["calls"][0]["callee"] == "scale"
    assert c["calls"][0]["arguments"] == ["flow", "dt"]
    assert c["return_expressions"][0]["expression"] == "updated"
