import json

import pytest
from jsonschema import Draft202012Validator

from scicontext.science_tools import ScienceStore, tool_definition


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
    parameters = tool_definition()["function"]["parameters"]
    Draft202012Validator.check_schema(parameters)
    assert not list(Draft202012Validator(parameters).iter_errors({"action": "find", "query": "energy"}))


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


def prepared_graph_store(tmp_path, unseen=False):
    """Store with prepared extraction outputs; no model calls anywhere."""
    import gzip
    from scicontext.packet import build_packet
    from scicontext.scientific_objects import extract_objects
    root = tmp_path / "graph-task"
    root.mkdir()
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
    rows = [{"pid": 1, "seq": 1, "file": "reproduce.py", "name": "<module>", "line": 1},
            {"pid": 1, "seq": 2, "parent_seq": 1, "file": "reproduce.py", "name": "run", "line": 2},
            {"pid": 1, "seq": 3, "parent_seq": 2, "file": "model.py", "name": "advance", "line": 1}]
    if unseen:
        (root / "unseen.py").write_text("def mystery(value):\n    return value * 2\n")
        graph["dependence_signatures"].append(
            {"func": ["unseen.py", "mystery", 1], "instances": 3, "arguments": {}})
        rows.append({"pid": 1, "seq": 4, "parent_seq": 2, "file": "unseen.py", "name": "mystery", "line": 1})
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
    detail = store.inspect(node["id"])
    assert detail["sources"] == []
    assert detail["evidence"]["sources"], "on-demand compilation must register real citations"
    assert any("value * 2" in source["text"] for source in detail["evidence"]["sources"])
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
