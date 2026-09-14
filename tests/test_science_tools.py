import hashlib
import json

import pytest
from jsonschema import Draft202012Validator

from scicontext.science_tools import ScienceStore, tool_definitions


@pytest.fixture
def store(tmp_path):
    root = tmp_path / "task"
    root.mkdir()
    (root / "model.py").write_text('raise RuntimeError("never import me")\n'
        'def advance(energy, flux, dt, active):\n'
        '    """Positive flux leaves the stored energy; dt is elapsed time."""\n'
        '    if active:\n        energy = energy - flux * dt\n    return energy\n')
    (root / "paper.md").write_text("The calculation advances stored energy under outward flux. Energy is conserved.\n")
    result = ScienceStore(root, tmp_path / "artifacts")
    result.prepare()
    return result


def model_from(result, docs):
    source = docs["source"]["id"]
    claim = {"text": "Advance stored energy using the outward transport and elapsed time.", "source_ids": [source]}
    c = next(c for c in result["computations"] if "advance" in c["name"])
    return {"purpose": claim, "expected_change": claim, "preserve": [claim],
        "computations": [{"computation_id": c["id"], "meaning": claim, "quantities": [],
            "conventions": [claim], "assumptions": ["The source shows implementation behaviour; its correctness remains to be checked."]}]}


def test_find_inspect_record_is_nonexecuting_and_connected(store):
    found = store.find("stored energy")
    assert found["matches"]
    result = store.inspect("model.py#advance")
    assert any("flux * dt" in s["text"] for s in result["sources"])
    assert result["relationships"] and result["templates"]
    docs = store.inspect("paper.md")
    recorded = store.record_model(model_from(result, docs))
    assert recorded["status"] == "recorded"
    assert (store.store / "scientific-model.json").is_file()
    assert "stored energy" in (store.store / "scientific-model.md").read_text()


def test_tool_schema_references_are_resolvable():
    tools = {tool["function"]["name"]: tool["function"]["parameters"] for tool in tool_definitions()}
    assert set(tools) == {"science_find", "science_inspect", "science_note"}
    for parameters in tools.values():
        Draft202012Validator.check_schema(parameters)
        assert "$defs" not in parameters and "action" not in parameters["properties"]
    assert not list(Draft202012Validator(tools["science_find"]).iter_errors({"query": "energy"}))
    assert "model" not in tools["science_note"]["properties"]


@pytest.mark.parametrize("target", ["../secret.py", "/etc/passwd", "private/test.py"])
def test_tool_rejects_nonpublic_paths(store, target):
    with pytest.raises((ValueError, OSError)):
        store.inspect(target)


def test_symlink_escape_rejected(store, tmp_path):
    (tmp_path / "outside.py").write_text("secret=1")
    (store.root / "escape.py").symlink_to(tmp_path / "outside.py")
    with pytest.raises(ValueError):
        store.inspect("escape.py")


def test_empty_and_unanchored_models_do_not_unlock(store):
    with pytest.raises(ValueError):
        store.record_model({})
    result, docs = store.inspect("model.py#advance"), store.inspect("paper.md")
    model = model_from(result, docs)
    model["purpose"] = {"text": "invented", "source_ids": ["not_seen"]}
    with pytest.raises(ValueError, match="inspected"):
        store.record_model(model)
    assert not store.state["model_recorded"]


def test_failed_second_record_is_not_success_from_previous_record(store):
    model = model_from(store.inspect("model.py#advance"), store.inspect("paper.md"))
    store.record_model(model)
    before = (store.store / "scientific-model.json").read_bytes()
    model["computations"][0]["computation_id"] = "fake"
    with pytest.raises(ValueError):
        store.record_model(model)
    assert (store.store / "scientific-model.json").read_bytes() == before


def test_inspections_do_not_evict_previous_citations_and_changed_ids_fail(store):
    result = store.inspect("model.py#advance")
    docs = store.inspect("paper.md")
    assert store.record_model(model_from(result, docs))["status"] == "recorded"
    identifier = result["quantities_and_expressions"][0]["id"]
    path = store.root / "model.py"
    path.write_text(path.read_text().replace("flux * dt", "flux * dt * 2"))
    with pytest.raises(ValueError, match="Source changed"):
        store.inspect(identifier)


def test_source_paging_does_not_skip_or_duplicate_lines(store):
    (store.root / "long.py").write_text("\n".join(f"value_{i} = {i}" for i in range(140)))
    pages, offset = [], 0
    while True:
        result = store.inspect("long.py", "source", offset)
        pages.append(result["source"]["quote"])
        offset = result["next_offset"]
        if offset is None:
            break
    assert "".join(pages).splitlines() == [f"value_{i} = {i}" for i in range(140)]


@pytest.mark.parametrize("name,code", [
    ("m.cpp", "double energy(double e,double flux,double dt) {return e-flux*dt;}\n"),
    ("m.f90", "function energy(e,flux,dt) result(out)\nreal::e,flux,dt,out\nout=e-flux*dt\nend function\n"),
    ("m.m", "function out = energy(e,flux,dt)\nout = e-flux*dt;\nend\n"),
    ("m.pyx", "cdef double energy(double e,double flux,double dt):\n    return e-flux*dt\n"),
])
def test_native_inspection_retains_calculations(store, name, code):
    (store.root / name).write_text(code)
    result = store.inspect(name)
    assert result["quantities_and_expressions"]
    assert "flux" in json.dumps(result)


def test_discovery_does_not_require_a_language_frontend(store):
    (store.root / "model.jl").write_text("energy(e, flux, dt) = e - flux * dt\n")
    store.prepare()
    assert any(m["target"].startswith("model.jl:") for m in store.find("energy")["matches"])
    result = store.inspect("model.jl", "source")
    assert result["source"]["source_kind"] == "code"
    assert "e - flux * dt" in result["source"]["quote"]
    structure = store.inspect("model.jl")
    assert not structure["analysis_backends"]
    assert "source_only_language" in json.dumps(structure["coverage"])


def test_expand_later_expression_id_shows_that_expression(store):
    (store.root / "many.py").write_text("def f(x):\n" + "".join(f"    y{i}=x+{i}\n" for i in range(20)) + "    return y19\n")
    first = store.inspect("many.py#f")
    second = store.inspect("many.py#f", offset=first["next_offset"])
    target = next(e["id"] for e in second["quantities_and_expressions"] if e.get("kind") == "source_computation")
    expanded = store.inspect(target)
    assert target in {e["id"] for e in expanded["quantities_and_expressions"]}


def test_document_paging_preserves_long_documents_and_lines(store):
    content = "x" * 25000 + "\n" + "\n".join(f"line {i}" for i in range(150))
    (store.root / "long.md").write_text(content)
    pieces, offset = [], 0
    while True:
        result = store.inspect("long.md", offset=offset)
        assert len(result["source"]["quote"]) <= 8000
        pieces.append(result["source"]["quote"])
        offset = result["next_offset"]
        if offset is None:
            break
    assert "".join(pieces) == content


def test_changed_code_cannot_be_recorded_from_stale_inspection(store):
    model = model_from(store.inspect("model.py#advance"), store.inspect("paper.md"))
    path = store.root / "model.py"
    path.write_text(path.read_text().replace("flux * dt", "flux * dt * 2"))
    with pytest.raises(ValueError, match="not recorded"):
        store.record_model(model)
    assert not store.state["model_recorded"]


def test_broken_python_remains_readable(store):
    (store.root / "broken.py").write_text("def broken(:\n")
    result = store.inspect("broken.py", "source")
    assert "def broken(" in result["source"]["quote"]
    assert result["source"]["source_kind"] == "code"
    assert store.inspect("broken.py")["computations"]


def test_wrong_qualified_owner_is_not_resolved_by_leaf_name(store):
    (store.root / "m.py").write_text("class Actual:\n    def solve(self,x):\n        return x*2\n")
    assert store.inspect("m.py#Nonexistent.solve")["status"] == "ambiguous_target"
    assert store.inspect("m.py#Actual.solve")["status"] == "ok"


def test_large_embedded_literal_template_is_expandable_not_dumped(store):
    (store.root / "m.py").write_text("import numpy as np\ndef f():\n    return np.array(" + repr(list(range(10000))) + ")\n")
    result = store.inspect("m.py#f")
    assert any(t.get("structure_not_inlined") for t in result["templates"])
    assert len(json.dumps(result)) < 30000


def prepared_graph_store(tmp_path, unseen=False, unseen_path="unseen.py", source_code=None):
    """Store with prepared extraction outputs; no model calls anywhere."""
    import gzip
    from scicontext.packet import build_packet
    from scicontext.scientific_objects import extract_objects
    root = tmp_path / "graph-task"
    root.mkdir()
    (root / "model.py").write_text(source_code or
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
    statement = "# Task statement\nRepair the advance computation.\n"
    (tmp_path / "task_statement.md").write_text(statement)
    packet["documents"].append({
        "id": "doc_context_fixture", "path": "@context/task_statement.md",
        "sha256": hashlib.sha256(statement.encode()).hexdigest(),
        "start_line": 1, "end_line": 2, "quote": statement})
    rows = [{"pid": 1, "seq": 1, "file": "reproduce.py", "name": "<module>", "line": 1},
            {"pid": 1, "seq": 2, "parent_seq": 1, "file": "reproduce.py", "name": "run", "line": 2},
            {"pid": 1, "seq": 3, "parent_seq": 2, "file": "model.py", "name": "advance", "line": 1}]
    if unseen:
        if unseen_path.endswith(".cpp"):
            (root / unseen_path).write_text("double mystery(double value) {\n    return value * 2;\n}\n")
        else:
            (root / unseen_path).write_text("def mystery(value):\n    return value * 2\n")
        graph["dependence_signatures"].append(
            {"func": [unseen_path, "mystery", 1], "instances": 3, "arguments": {}})
        rows.append({"pid": 1, "seq": 4, "parent_seq": 2, "file": unseen_path, "name": "mystery", "line": 1})
    artifacts = tmp_path / "graph-artifacts"
    artifacts.mkdir()
    (artifacts / "scientific-objects.json").write_text(json.dumps(graph))
    (artifacts / "packet.json").write_text(json.dumps(packet))
    trace = artifacts / "trace"
    trace.mkdir()
    with gzip.open(trace / "trace.jsonl.gz", "wt") as stream:
        for row in rows:
            stream.write(json.dumps(row) + "\n")
    result = ScienceStore(root, artifacts)
    result.prepare()
    return result


def test_prepared_operation_shows_its_guard_even_outside_the_source_page(tmp_path):
    store = prepared_graph_store(tmp_path, source_code=(
        'def advance(energy, flux, dt, active=True):\n'
        '    if active:\n'
        '        energy = energy - flux * dt\n'
        '    else:\n'
        '        energy = energy + flux * dt\n'
        '    return energy\n'))
    packet = json.loads((store.store / "packet.json").read_text())
    body = next(e for e in packet["entries"] if e.get("kind") == "assignment" and "energy - flux" in e.get("text", ""))
    other = next(e for e in packet["entries"] if e.get("kind") == "assignment" and "energy + flux" in e.get("text", ""))
    predicate = next(e for e in packet["entries"] if e.get("condition_for") == "if@2")
    node = next(n for n in store.state["scientific_graph"]["nodes"] if n["name"] == "advance")
    # Reproduce the failure: the operation survived selection, its guard did not.
    node["source_ids"] = [body["id"], other["id"]]
    store.save()
    result = store.inspect(node["id"])
    assert any("active" in condition for condition in result["conditions"])
    shown = {s["id"]: s for s in result["sources"]}
    assert shown[body["id"]]["guards"][0]["branch"] == "if@2:body"
    assert shown[other["id"]]["guards"][0]["branch"] == "if@2:else"
    for source in shown.values():
        guard = source["guards"][0]
        assert guard["id"] == predicate["id"] and guard["text"] == "active"
        assert guard["id"] in store.state["visible_sources"]


def test_unresolved_guard_remains_explicit_instead_of_disappearing():
    context = {"sources": {"e": {"id": "e", "path": "m.cpp", "text": "x += 1;"}},
               "documents": {}, "entities": {"e": {"condition_refs": [
                   {"branch": "if_statement@20:consequence", "predicate_id": None}]}}}
    shown = ScienceStore._source_excerpt(context, "e")
    assert shown["guards"] == [{"branch": "if_statement@20:consequence", "id": None, "text": None}]


def test_prepared_graph_is_queryable_and_citable(tmp_path):
    store = prepared_graph_store(tmp_path)
    prepared = store.prepare()
    assert prepared["scientific_graph"]["nodes"] >= 3
    overview = store.inspect("#graph")
    node = next(item for item in overview["nodes"] if item["name"] == "advance")
    assert node["findings"] == ["R4"]
    found = store.find("advance")
    assert any(match["target"] == node["id"] and match["kind"] == "scientific_node"
               for match in found["matches"])
    detail = store.inspect(node["id"])
    assert detail["computation_id"] and detail["sources"]
    assert all(source["text"] for source in detail["sources"])
    assert {source["id"] for source in detail["sources"]} <= set(store.state["visible_sources"])
    assert any(edge["relation"] == "calls" for edge in detail["dependencies"])
    source = store.inspect(node["id"], view="source")
    assert any("flux * dt" in piece["text"] for piece in source["source"])
    assert {piece["id"] for piece in source["source"]} <= set(store.state["visible_sources"])
    claim = {"text": "Advance subtracts outward flux over elapsed time.", "source_ids": [detail["sources"][0]["id"]]}
    model = {"purpose": claim, "expected_change": claim, "preserve": [claim],
             "computations": [{"computation_id": detail["computation_id"], "meaning": claim,
                               "quantities": [], "conventions": [], "assumptions": ["Fixture."]}]}
    assert store.record_model(model)["status"] == "recorded"


def test_record_rejects_sources_not_shown_by_inspection(tmp_path):
    store = prepared_graph_store(tmp_path)
    node = next(item for item in store.inspect("#graph")["nodes"] if item["name"] == "advance")
    detail = store.inspect(node["id"])
    full = next(item for item in store.state["scientific_graph"]["nodes"] if item["id"] == node["id"])
    shown = {source["id"] for source in detail["sources"]}
    unseen = [identifier for identifier in full["source_ids"] if identifier not in shown]
    assert unseen, "a paged node must keep later sources unregistered until inspected"
    claim = {"text": "Unseen content.", "source_ids": [unseen[0]]}
    model = {"purpose": claim, "expected_change": claim, "preserve": [claim],
             "computations": [{"computation_id": detail["computation_id"], "meaning": claim,
                               "quantities": [], "conventions": [], "assumptions": ["Fixture."]}]}
    with pytest.raises(ValueError, match="Cite source IDs"):
        store.record_model(model)


def test_graph_node_without_parsed_region_compiles_evidence_on_demand(tmp_path):
    store = prepared_graph_store(tmp_path, unseen=True)
    node = next(item for item in store.inspect("#graph")["nodes"] if item["name"] == "mystery")
    detail = store.inspect(node["id"], view="source")
    assert detail["sources"] == []
    assert detail["evidence"]["sources"], "on-demand compilation must register real citations"
    assert any("value * 2" in source["text"] for source in detail["evidence"]["sources"])
    assert any("value * 2" in source["text"] for source in detail["source"])
    expanded = next(item for item in store.state["scientific_graph"]["nodes"] if item["id"] == node["id"])
    assert expanded.get("expanded") and expanded["source_ids"], "compiled evidence must persist on the node"


def test_edited_prepared_source_cannot_be_cited(tmp_path):
    store = prepared_graph_store(tmp_path)
    node = next(item for item in store.inspect("#graph")["nodes"] if item["name"] == "advance")
    detail = store.inspect(node["id"])
    source_id = detail["sources"][0]["id"]
    (store.root / "model.py").write_text('def advance(energy, flux, dt):\n    return energy\n')
    claim = {"text": "Advance subtracts outward flux over elapsed time.", "source_ids": [source_id]}
    model = {"purpose": claim, "expected_change": claim, "preserve": [claim],
             "computations": [{"computation_id": detail["computation_id"], "meaning": claim,
                               "quantities": [], "conventions": [], "assumptions": ["Fixture."]}]}
    with pytest.raises(ValueError, match="not current"):
        store.record_model(model)


def test_context_documents_are_verified_next_to_the_store(tmp_path):
    store = prepared_graph_store(tmp_path)
    store._visible([], ["doc_context_fixture"])
    node = next(item for item in store.inspect("#graph")["nodes"] if item["name"] == "advance")
    detail = store.inspect(node["id"])
    claim = {"text": "Task statement context.", "source_ids": ["doc_context_fixture"]}
    model = {"purpose": claim, "expected_change": claim, "preserve": [claim],
             "computations": [{"computation_id": detail["computation_id"], "meaning": claim,
                               "quantities": [], "conventions": [], "assumptions": ["Fixture."]}]}
    assert store.record_model(model)["status"] == "recorded"


def test_cpp_node_inspection_requests_analysis_and_expands(tmp_path):
    store = prepared_graph_store(tmp_path, unseen=True, unseen_path="unseen.cpp")
    node = next(item for item in store.inspect("#graph")["nodes"] if item["name"] == "mystery")
    detail = store.inspect(node["id"])
    assert detail.get("backend_request"), "C++ node inspection must request host analysis"
    assert detail["evidence"]["sources"], "on-demand compilation must register citations"
    expanded = next(item for item in store.state["scientific_graph"]["nodes"] if item["id"] == node["id"])
    assert expanded.get("expanded") and expanded["source_ids"]


def test_cpp_node_applies_analysis_on_the_return_call(tmp_path):
    import json as jsonlib
    store = prepared_graph_store(tmp_path, unseen=True, unseen_path="unseen.cpp")
    node = next(item for item in store.inspect("#graph")["nodes"] if item["name"] == "mystery")
    first = store.inspect(node["id"])
    assert first.get("backend_request") and first.get("evidence")
    # The runner returns with the analyzer result on the second call; it must
    # still be applied even though call one already persisted source_ids.
    analysis = {"analyses": [{"backend": "joern", "language": "cpp", "nodes": [], "links": [],
                              "selection": {"methods": []}}], "gaps": [], "source_hashes": {}}
    second = store.inspect(node["id"], analysis=analysis)
    assert second.get("analysis_backends") == ["joern"]
    assert second.get("evidence"), "the detailed response must not be skipped once sources exist"
    persisted = next(item for item in store.state["scientific_graph"]["nodes"] if item["id"] == node["id"])
    assert persisted.get("analysis_backends") == ["joern"]
    assert jsonlib.dumps(second)


def test_source_view_resolves_the_symbol_span(tmp_path):
    root = tmp_path / "long-task"
    root.mkdir()
    lines = [f"# filler {index}\n" for index in range(120)]
    lines += ["def late_symbol(value):\n", "    return value + 1\n"]
    (root / "long.py").write_text("".join(lines))
    store = ScienceStore(root, tmp_path / "long-store")
    store.prepare()
    result = store.inspect("long.py#late_symbol", view="source")
    text = result["source"]["quote"]
    assert "def late_symbol" in text and "return value + 1" in text
    assert "filler 1" not in text


def test_oversize_data_file_head_is_readable(tmp_path):
    from scicontext import evidence
    root = tmp_path / "big-task"
    root.mkdir()
    (root / "data.cube").write_text("# header line\n" + "x" * (evidence.MAX_FILE_BYTES + 100))
    store = ScienceStore(root, tmp_path / "big-store")
    store.prepare()
    result = store.inspect("data.cube")
    assert result["status"] == "ok" and result["truncated"] is True
    assert "header line" in json.dumps(result)


def test_self_check_verifies_queries_and_leaves_no_model(tmp_path):
    store = prepared_graph_store(tmp_path)
    store.prepare()
    result = store.check()
    assert result["status"] == "ok"
    assert result["steps"]["graph"]["nodes"] >= 3
    assert result["steps"]["inspect"]["registered_matches_shown"]
    assert result["steps"]["record"]["status"] == "recorded"
    assert result["steps"]["unseen_citation"]["status"] == "refused"
    restored = ScienceStore(store.root, store.store)
    assert not restored.state.get("model_recorded"), "self-check must restore the store"
    assert not (store.store / "scientific-model.json").exists()
    assert not store.state.get("model_recorded"), "the in-memory state must also be restored"


@pytest.mark.parametrize("artifact", [None, "model-1.json", "scientific-model.json", "scientific-model.md"])
def test_self_check_refuses_existing_model_without_mutating_store(tmp_path, artifact):
    store = prepared_graph_store(tmp_path)
    if artifact:
        (store.store / artifact).write_text("existing model, preserve exactly")
    else:
        store.state["model_recorded"] = True
        store.save()
    before = {p.relative_to(store.store).as_posix(): p.read_bytes() for p in store.store.rglob("*") if p.is_file()}
    with pytest.raises(ValueError, match="existing.*model|model.*exist"):
        store.check()
    after = {p.relative_to(store.store).as_posix(): p.read_bytes() for p in store.store.rglob("*") if p.is_file()}
    assert after == before


def test_prepared_hash_uses_full_file_not_inspection_prefix(tmp_path, monkeypatch):
    from scicontext import evidence
    store = prepared_graph_store(tmp_path)
    node = next(n for n in store.inspect("#graph")["nodes"] if n["name"] == "advance")
    detail = store.inspect(node["id"])
    claim = {"text": "Stored energy update.", "source_ids": [detail["sources"][0]["id"]]}
    model = {"purpose": claim, "expected_change": claim, "preserve": [claim], "computations": [
        {"computation_id": detail["computation_id"], "meaning": claim, "quantities": [],
         "conventions": [], "assumptions": []}]}
    monkeypatch.setattr(evidence, "MAX_FILE_BYTES", 32)
    assert store._read_window("model.py")[2]
    assert store.record_model(model)["status"] == "recorded"
    with (store.root / "model.py").open("a") as stream:
        stream.write("\n# changed beyond the inspection prefix\n")
    with pytest.raises(ValueError, match="not current"):
        store.record_model(model)


def test_edited_node_refreshes_shifted_symbol_and_records_current_sources(tmp_path, monkeypatch):
    from scicontext import evidence
    store = prepared_graph_store(tmp_path)
    node = next(n for n in store.inspect("#graph")["nodes"] if n["name"] == "advance")
    old = store.inspect(node["id"])
    old_ids = {s["id"] for s in old["sources"]}
    unchanged = store.inspect("reproduce.py", view="source")["source"]["id"]
    file = store.root / "model.py"
    file.write_text("\n\n\n" + file.read_text().replace("flux * dt", "flux * dt * 2"))
    current = store.inspect(node["id"], view="source")
    assert current["refreshed"] and current["line"] > old["line"]
    assert any("flux * dt * 2" in s["text"] for s in current["source"])
    assert not old_ids & {s["id"] for s in current["sources"]}
    assert current["dependencies"] == old["dependencies"]
    assert current["dependencies_version"] == "preparation_snapshot_not_reexecuted"
    assert not current["observations"] and current["preparation_evidence"]
    claim = {"text": "Updated energy transport.", "source_ids": [current["sources"][0]["id"], unchanged]}
    model = {"purpose": claim, "expected_change": claim, "preserve": [claim], "computations": [
        {"computation_id": current["computation_id"], "meaning": claim, "quantities": [],
         "conventions": [], "assumptions": []}]}
    assert store.record_model(model)["status"] == "recorded"
    model["purpose"] = {"text": "Old version.", "source_ids": list(old_ids)}
    with pytest.raises(ValueError, match="not current"):
        store.record_model(model)
    monkeypatch.setattr(evidence, "extract_evidence", lambda *a, **kw: pytest.fail("unchanged file recompiled"))
    again = store.inspect(node["id"])
    assert again["computation_id"] == current["computation_id"]
    assert not again.get("refreshed")


def test_deleted_symbol_never_retargets_old_line(tmp_path):
    store = prepared_graph_store(tmp_path)
    node = next(n for n in store.inspect("#graph")["nodes"] if n["name"] == "advance")
    store.inspect(node["id"])
    (store.root / "model.py").write_text("def replacement(value):\n    return value + 1\n")
    result = store.inspect(node["id"])
    assert result["status"] in {"missing_target", "ambiguous_target", "unresolved_target"}
    assert not result["sources"]
    assert result["refresh_target"] == "model.py#advance"


def test_cpp_node_refreshes_after_inserted_lines(tmp_path):
    store = prepared_graph_store(tmp_path, unseen=True, unseen_path="unseen.cpp")
    node = next(n for n in store.inspect("#graph")["nodes"] if n["name"] == "mystery")
    first = store.inspect(node["id"])
    file = store.root / "unseen.cpp"
    file.write_text("\n\n" + file.read_text().replace("value * 2", "value * 3"))
    second = store.inspect(node["id"], view="source")
    assert second.get("refreshed")
    assert second["line"] > first["line"]
    assert any("value * 3" in s["text"] for s in second["source"])


def test_flat_note_resolves_internal_ids_and_records_after_edit(tmp_path):
    store = prepared_graph_store(tmp_path)
    node = next(n for n in store.inspect("#graph")["nodes"] if n["name"] == "advance")
    detail = store.inspect(node["id"])
    request = {"target": detail["note_target"], "meaning": "Energy is updated by outward flux over time.",
               "expected_change": "Apply the requested transport update.", "preserve": ["Keep the sign convention."],
               "source_ids": detail["note_source_ids"]}
    assert store.dispatch({"action": "record_note", **request})["status"] == "recorded"
    saved = json.loads((store.store / "scientific-model.json").read_text())
    item = saved["computations"][0]["interpretation"]
    assert item["computation_id"] == detail["computation_id"]
    assert item["assumptions"] == item["conventions"] == item["quantities"] == []
    file = store.root / "model.py"
    file.write_text("\n\n" + file.read_text().replace("flux * dt", "flux * dt * 3"))
    with pytest.raises(ValueError):
        store.record_note(request)
    refreshed = store.inspect(node["id"])
    request["source_ids"] = refreshed["note_source_ids"]
    assert store.record_note(request)["status"] == "recorded"
    assert (store.store / "model-1.json").is_file(), "previous notes remain archived"


def test_flat_note_refuses_graph_id_as_a_source_citation(tmp_path):
    store = prepared_graph_store(tmp_path)
    node = next(n for n in store.inspect("#graph")["nodes"] if n["name"] == "advance")
    detail = store.inspect(node["id"])
    request = {"target": detail["note_target"], "meaning": "Energy update.", "expected_change": "Fix update.",
               "preserve": ["Sign convention."], "source_ids": [node["id"]]}
    with pytest.raises(ValueError, match="Cite source IDs"):
        store.record_note(request)


@pytest.mark.parametrize("path,code", [
    ("mystery.f90", "function mystery(value) result(out)\nreal :: value, out\nout = value * 2\nend function\n"),
    ("mystery.m", "function out = mystery(value)\nout = value * 2;\nend\n"),
    ("mystery.pyx", "def mystery(value):\n    return value * 2\n"),
])
def test_native_node_refresh_uses_current_symbol_not_old_line(tmp_path, path, code):
    store = prepared_graph_store(tmp_path, unseen=True, unseen_path=path)
    file = store.root / path
    file.write_text(code)
    node = next(n for n in store.inspect("#graph")["nodes"] if n["name"] == "mystery")
    first = store.inspect(node["id"])
    assert first.get("evidence", {}).get("sources")
    file.write_text("\n\n" + code.replace("value * 2", "value * 3"))
    second = store.inspect(node["id"], view="source")
    assert second.get("refreshed"), second
    assert any("value * 3" in s["text"] for s in second["source"])


def test_refresh_of_one_file_preserves_other_prepared_file_citations(tmp_path):
    store = prepared_graph_store(tmp_path)
    nodes = store.inspect("#graph")["nodes"]
    caller = next(n for n in nodes if n["name"] == "run")
    before = store.inspect(caller["id"])
    (store.root / "model.py").write_text("def advance(*args):\n    return 0\n")
    after = store.inspect(caller["id"])
    assert after["note_source_ids"] == before["note_source_ids"]
    assert after["computation_id"] == before["computation_id"]
    assert store.record_note({"target": after["note_target"], "meaning": "Run the public workflow.",
            "expected_change": "Keep the workflow callable.", "preserve": ["Public inputs."],
            "source_ids": after["note_source_ids"]})["status"] == "recorded"


def test_deleted_top_level_function_does_not_refresh_to_same_named_method(tmp_path):
    store = prepared_graph_store(tmp_path)
    node = next(n for n in store.inspect("#graph")["nodes"] if n["name"] == "advance")
    store.inspect(node["id"])
    (store.root / "model.py").write_text("class Other:\n    def advance(self, energy, flux, dt):\n        return energy + 99\n")
    result = store.inspect(node["id"])
    assert result["status"] == "ambiguous_target"
    assert result["targets"] == result["sources"] == []
    assert not result.get("refreshed")


def test_first_expansion_supplies_usable_note_fields(tmp_path):
    store = prepared_graph_store(tmp_path, unseen=True)
    node = next(n for n in store.inspect("#graph")["nodes"] if n["name"] == "mystery")
    result = store.inspect(node["id"])
    assert result["note_target"] and result["note_source_ids"]
    assert set(result["note_source_ids"]) <= set(store.state["visible_sources"])
    assert store.record_note({"target": result["note_target"], "source_ids": result["note_source_ids"],
            "meaning": "Double the supplied value.", "expected_change": "Repair the reported behaviour.",
            "preserve": ["The scalar return type."]})["status"] == "recorded"
