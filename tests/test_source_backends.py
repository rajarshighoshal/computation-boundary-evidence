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


def joern_graph():
    """One caller, its calls, and the method definitions the CPG resolved them to."""
    nodes = {
        "1": {"id": "1", "kind": "METHOD", "path": "spawn.cpp",
              "properties": {"NAME": "spawn_workers", "SIGNATURE": "int(int)", "TYPE_FULL_NAME": "int"}},
        "2": {"id": "2", "kind": "CALL", "path": "spawn.cpp",
              "properties": {"NAME": "pthread_create", "CODE": "pthread_create(&t, NULL, worker, NULL)"}},
        "3": {"id": "3", "kind": "CALL", "path": "spawn.cpp", "properties": {"NAME": "helper", "CODE": "helper(n)"}},
        "4": {"id": "4", "kind": "METHOD", "path": "spawn.cpp", "properties": {"NAME": "helper", "SIGNATURE": "int(int)"}},
        "5": {"id": "5", "kind": "CALL", "path": "spawn.cpp", "properties": {"NAME": "scale", "CODE": "scale(n)"}},
        "6": {"id": "6", "kind": "METHOD", "path": "lib/scale.cpp", "properties": {"NAME": "scale", "SIGNATURE": "int(int)"}},
        "7": {"id": "7", "kind": "CALL", "path": "spawn.cpp", "properties": {"NAME": "MPI_Init", "CODE": "MPI_Init(&argc, &argv)"}},
    }
    links = [{"source": "1", "target": call, "role": "AST"} for call in ("2", "3", "5", "7")] + [
        {"source": "3", "target": "4", "role": "CALL"}, {"source": "5", "target": "6", "role": "CALL"}]
    selection = {"methods": [{"id": "1", "name": "spawn_workers", "node_ids": ["1", "2", "3", "5", "7"]}]}
    return nodes, links, selection


def test_joern_contracts_classify_calls_from_the_caller_file_declarations(tmp_path):
    (tmp_path / "spawn.cpp").write_text('#include <pthread.h>\n#include "local_util.h"\n'
                                        "int spawn_workers(int n) {\n    return helper(n);\n}\n")
    contracts = source_backends.distill_joern_contracts(*joern_graph(), "NEWC", root=tmp_path)
    calls = {call["callee"]: call for call in contracts[0]["calls"]}

    # An include that names the callee is layer 2 provider naming, not a guess.
    assert calls["pthread_create"]["boundary"] == {
        "kind": "external", "provider": "pthread.h", "assume": "correct_interface",
        "repair_scope": "caller_file", "basis": "layer2_include:pthread.h"}
    # No include names MPI_Init, so only the disclosed prefix heuristic applies.
    assert calls["MPI_Init"]["boundary"]["kind"] == "external"
    assert calls["MPI_Init"]["boundary"]["provider"] == "mpi.h"
    assert calls["MPI_Init"]["boundary"]["basis"] == "prefix_heuristic:mpi.h"

    # Layer 1 wins over declarations: resolved definitions are internal either way.
    assert calls["helper"]["boundary"]["kind"] == "internal"
    assert calls["helper"]["boundary"]["repair_scope"] == "caller_file"
    assert calls["helper"]["boundary"]["basis"] == "layer1_resolved_in_repo"
    assert calls["scale"]["boundary"]["kind"] == "internal"
    assert calls["scale"]["boundary"]["repair_scope"] == "repo"

    assert calls["helper"]["external"] is False and calls["scale"]["external"] is False
    assert {call["callee"] for call in contracts[0]["external_calls"]} == {"pthread_create", "MPI_Init"}


def test_joern_external_flag_keeps_layer_two_provider_naming(tmp_path):
    (tmp_path / "spawn.cpp").write_text("#include <pthread.h>\n")
    nodes, links, selection = joern_graph()
    nodes["8"] = {"id": "8", "kind": "METHOD", "properties": {"NAME": "pthread_create", "IS_EXTERNAL": True}}
    links.append({"source": "2", "target": "8", "role": "CALL"})
    contracts = source_backends.distill_joern_contracts(nodes, links, selection, "NEWC", root=tmp_path)
    boundary = next(call for call in contracts[0]["calls"] if call["callee"] == "pthread_create")["boundary"]
    assert boundary["kind"] == "external" and boundary["provider"] == "pthread.h"
    assert boundary["basis"] == "layer1_is_external+layer2_include:pthread.h"


def test_python_imports_name_the_provider_of_an_unresolved_call(tmp_path):
    (tmp_path / "solver.py").write_text("import numpy as np\nimport os\n\n"
                                        "def solve(a, b):\n    return np.linalg.solve(a, b)\n")
    nodes = {
        "1": {"id": "1", "kind": "METHOD", "path": "solver.py", "properties": {"NAME": "solve"}},
        "2": {"id": "2", "kind": "CALL", "path": "solver.py",
              "properties": {"NAME": "numpy.linalg.solve", "CODE": "np.linalg.solve(a, b)"}},
    }
    links = [{"source": "1", "target": "2", "role": "AST"}]
    selection = {"methods": [{"id": "1", "name": "solve", "node_ids": ["1", "2"]}]}
    contracts = source_backends.distill_joern_contracts(nodes, links, selection, "PYTHONSRC", root=tmp_path)
    boundary = contracts[0]["calls"][0]["boundary"]
    assert boundary["kind"] == "external" and boundary["provider"] == "numpy"
    assert boundary["basis"] == "layer2_import:numpy"


def test_cython_cimports_name_the_provider_of_an_unresolved_call(tmp_path):
    (tmp_path / "solver.pyx").write_text("cimport numpy as np\nfrom libc.stdlib cimport malloc\n")
    entries = [
        {"kind": "signature", "path": "solver.pyx", "start_line": 3, "symbol": "solve", "text": "def solve(n):",
         "scope": "<module>.solve", "function_scope": "<module>.solve", "native": {"function_name": "solve"}},
        {"kind": "call", "path": "solver.pyx", "start_line": 4, "text": "np.zeros(n)", "scope": "<module>.solve",
         "function_scope": "<module>.solve", "native_expression": {"kind": "call", "callee": "np.zeros"}},
        {"kind": "call", "path": "solver.pyx", "start_line": 5, "text": "malloc(n)", "scope": "<module>.solve",
         "function_scope": "<module>.solve", "native_expression": {"kind": "call", "callee": "malloc"}},
    ]
    calls = {call["callee"]: call["boundary"] for call in
             source_backends.distill_native_contracts(entries, "cython", tmp_path)[0]["calls"]}
    assert calls["np.zeros"]["kind"] == "external" and calls["np.zeros"]["provider"] == "numpy"
    assert calls["np.zeros"]["basis"] == "layer2_import:numpy"
    assert calls["malloc"]["kind"] == "external" and calls["malloc"]["provider"] == "libc.stdlib"


def fortran_solver_entries():
    return [
        {"kind": "signature", "path": "solver.f90", "start_line": 1, "symbol": "solve",
         "text": "subroutine solve(n)", "scope": "<module>.solve", "function_scope": "<module>.solve",
         "scope_chain": ["<module>", "<module>.subroutine:solve@0"], "native": {"function_name": "solve"}},
        {"kind": "call", "path": "solver.f90", "start_line": 5, "text": "scale(n)", "scope": "<module>.solve",
         "function_scope": "<module>.solve", "native_expression": {"kind": "call", "callee": "scale"}},
        {"kind": "call", "path": "solver.f90", "start_line": 6, "text": "c_loc(n)", "scope": "<module>.solve",
         "function_scope": "<module>.solve", "native_expression": {"kind": "call", "callee": "c_loc"}},
    ]


def test_fortran_use_declarations_name_a_provider_only_outside_the_scanned_universe(tmp_path):
    (tmp_path / "solver.f90").write_text("subroutine solve(n)\n    use, intrinsic :: iso_c_binding\n"
                                         "    use mymod\n    call scale(n)\nend subroutine\n")
    contracts = source_backends.distill_native_contracts(fortran_solver_entries(), "fortran", tmp_path)
    calls = {call["callee"]: call["boundary"] for call in contracts[0]["calls"]}
    assert calls["c_loc"]["kind"] == "external" and calls["c_loc"]["provider"] == "iso_c_binding"
    assert calls["c_loc"]["basis"] == "layer2_use:iso_c_binding(intrinsic)"
    assert calls["scale"]["kind"] == "external" and calls["scale"]["provider"] == "mymod"
    assert calls["scale"]["basis"] == "layer2_use:mymod(only_unscanned_module)"

    # With `mymod` inside the scanned universe no declaration explains `scale`.
    entries = fortran_solver_entries() + [
        {"kind": "signature", "path": "mymod.f90", "start_line": 2, "symbol": "other", "text": "subroutine other()",
         "scope": "<module>.other", "function_scope": "<module>.other",
         "scope_chain": ["<module>", "<module>.module:mymod@0", "<module>.module:mymod@0.subroutine:other@20"],
         "native": {"function_name": "other"}}]
    calls = {call["callee"]: call["boundary"] for call in
             source_backends.distill_native_contracts(entries, "fortran", tmp_path)[0]["calls"]}
    assert calls["scale"] == {"kind": "unknown_external", "provider": None, "assume": None,
                              "repair_scope": "repo", "basis": "layer3_scanned_module:mymod"}
    assert calls["c_loc"]["provider"] == "iso_c_binding"


def test_fortran_calls_resolve_case_insensitively_and_locally(tmp_path):
    (tmp_path / "solver.f90").write_text("subroutine solve(n)\n    call SCALE(n)\nend subroutine\n")
    entries = [
        {"kind": "signature", "path": "solver.f90", "start_line": 1, "symbol": "solve",
         "text": "subroutine solve(n)", "scope": "<module>.solve", "function_scope": "<module>.solve",
         "scope_chain": ["<module>", "<module>.subroutine:solve@0"], "native": {"function_name": "solve"}},
        {"kind": "call", "path": "solver.f90", "start_line": 2, "text": "call SCALE(n)", "scope": "<module>.solve",
         "function_scope": "<module>.solve", "native_expression": {"kind": "call", "callee": "SCALE"}},
        {"kind": "signature", "path": "solver.f90", "start_line": 9, "symbol": "scale", "text": "subroutine scale(n)",
         "scope": "<module>.scale", "function_scope": "<module>.scale",
         "scope_chain": ["<module>", "<module>.subroutine:scale@40"], "native": {"function_name": "scale"}},
    ]
    contracts = source_backends.distill_native_contracts(entries, "fortran", tmp_path)
    boundary = next(call["boundary"] for call in contracts[0]["calls"] if call["callee"] == "SCALE")
    assert boundary["kind"] == "internal" and boundary["repair_scope"] == "caller_file"
    assert boundary["basis"] == "layer1_scanned_definition"


def test_caller_declarations_that_do_not_name_the_callee_stay_unknown(tmp_path):
    (tmp_path / "opaque.cpp").write_text("#include <vector>\n#include <string>\n")
    entries = [
        {"kind": "signature", "path": "opaque.cpp", "start_line": 3, "symbol": "run", "text": "int run(int n)",
         "scope": "<module>.run", "function_scope": "<module>.run", "native": {"function_name": "run"}},
        {"kind": "call", "path": "opaque.cpp", "start_line": 4, "text": "mystery(n)", "scope": "<module>.run",
         "function_scope": "<module>.run", "native_expression": {"kind": "call", "callee": "mystery"}},
    ]
    contract = source_backends.distill_native_contracts(entries, "cpp", tmp_path)[0]
    assert contract["calls"][0]["boundary"] == {
        "kind": "unknown_external", "provider": None, "assume": None,
        "repair_scope": "repo", "basis": "layer3_no_declaration_match"}
    assert contract["calls"][0]["external"] is True
    assert contract["external_calls"] == contract["calls"]

    # Without the caller's own file there is nothing to read, and that is recorded.
    unavailable = source_backends.distill_native_contracts(entries, "cpp")[0]["calls"][0]["boundary"]
    assert unavailable["kind"] == "unknown_external" and unavailable["basis"] == "layer3_no_caller_source"


def test_matlab_import_statements_are_not_a_declaration_layer(tmp_path):
    (tmp_path / "model.m").write_text("function out = run(n)\n    import mypkg.*\n    out = mystery(n);\nend\n")
    entries = [
        {"kind": "signature", "path": "model.m", "start_line": 1, "symbol": "run", "text": "function out = run(n)",
         "scope": "<module>.run", "function_scope": "<module>.run", "native": {"function_name": "run"}},
        {"kind": "call", "path": "model.m", "start_line": 3, "text": "mystery(n)", "scope": "<module>.run",
         "function_scope": "<module>.run", "native_expression": {"kind": "call", "callee": "mystery"}},
    ]
    boundary = source_backends.distill_native_contracts(entries, "matlab", tmp_path)[0]["calls"][0]["boundary"]
    assert boundary["kind"] == "unknown_external" and boundary["provider"] is None
    assert boundary["basis"] == "layer3_no_declaration"


def test_long_declarations_are_capped_in_the_boundary_record(tmp_path):
    header = "deeppath/" * 12 + "widget_util.h"
    (tmp_path / "sparse.cpp").write_text(f"#include <{header}>\n")
    entries = [
        {"kind": "signature", "path": "sparse.cpp", "start_line": 3, "symbol": "run", "text": "int run(void)",
         "scope": "<module>.run", "function_scope": "<module>.run", "native": {"function_name": "run"}},
        {"kind": "call", "path": "sparse.cpp", "start_line": 4, "text": "widget_util_malloc(n)",
         "scope": "<module>.run", "function_scope": "<module>.run",
         "native_expression": {"kind": "call", "callee": "widget_util_malloc"}},
    ]
    boundary = source_backends.distill_native_contracts(entries, "cpp", tmp_path)[0]["calls"][0]["boundary"]
    assert set(boundary) == {"kind", "provider", "assume", "repair_scope", "basis"}
    assert boundary["kind"] == "external"
    assert boundary["provider"].endswith(" ... [truncated]") and len(boundary["provider"]) <= 96
    assert boundary["basis"].startswith("layer2_include:") and len(boundary["basis"]) <= 136
