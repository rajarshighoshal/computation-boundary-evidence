"""No-model checks of the scientific reader's input, contract and repair handoff."""
import asyncio
import copy
import json
from pathlib import Path

import pytest

from scicontext.cli import main
from scicontext.controller import TrialConfig, run_trial
from scicontext.extraction import run_extraction
from scicontext.object_context import enrichment_input, enrich_objects, object_bundle, render_objects
from scicontext.packet import build_packet
from scicontext.scientific_objects import extract_objects
from scicontext.tool_cli import main as helper_main


@pytest.fixture
def scientific_case(tmp_path):
    (tmp_path / "model.py").write_text(
        "import numpy as np\n"
        "def displacement(K, F):\n"
        "    return np.linalg.solve(K, F)\n")
    (tmp_path / "README.md").write_text(
        "The stiffness matrix K maps displacement to applied load F.\n"
        "This model assumes fixed boundary conditions and a nonsingular stiffness matrix.\n")
    packet = build_packet(tmp_path)
    graph = extract_objects(tmp_path, packet)
    graph["task_id"] = "fixture"
    matrix = next(o for o in graph["objects"] if o["symbol"] == "K")
    response = {"schema_version": "object-enrichment-1.0", "annotations": [{
        "object_id": matrix["id"], "meaning": "Stiffness operator mapping displacement to applied load (README.md:1).",
        "conventions": ["Matrix and load use the same displacement basis."],
        "assumptions": ["Fixed boundary conditions and nonsingular stiffness (README.md:2)."]}]}
    return tmp_path, packet, graph, response


def test_scientific_input_includes_source_material_and_real_code_relations(scientific_case):
    _, packet, graph, _ = scientific_case
    payload = enrichment_input(graph, packet)
    assert set(payload) == {"objects", "operations", "links", "unsupported", "context", "selection"}
    assert "stiffness matrix" in json.dumps(payload["context"]["scientific_passages"])
    assert "np.linalg.solve" in json.dumps(payload["context"]["code_passages"])
    assert any(op["kind"] == "linear_solve" for op in payload["operations"])
    assert payload["links"] == graph["links"]
    assert payload["selection"]["truncated"] is False


def test_enrichment_adds_meaning_without_overwriting_any_structural_fact(scientific_case):
    _, _, graph, response = scientific_case
    original = copy.deepcopy(graph)
    enriched = enrich_objects(graph, response)
    assert graph == original
    for old, new in zip(graph["objects"], enriched["objects"]):
        assert {k: v for k, v in new.items() if k != "interpretation"} == old
    assert enriched["operations"] == graph["operations"]
    assert enriched["links"] == graph["links"]
    assert enriched["unsupported"] == graph["unsupported"]
    assert enriched["enrichment"]["applied_object_ids"] == [response["annotations"][0]["object_id"]]
    text = render_objects(enriched)
    assert "Stiffness operator" in text and "Fixed boundary conditions" in text
    assert "coefficient_operator" in text and "not mandatory repair rules" in text
    assert "--returned_as-->" in text and "model.py:3-3" in text


@pytest.mark.parametrize("field,value", [("dimensions", {"length": 1}), ("links", []),
                                        ("probes", []), ("status", "verified"), ("formula", "K=F")])
def test_model_cannot_write_structure_units_probes_or_verified_status(scientific_case, field, value):
    _, _, graph, response = scientific_case
    response["annotations"][0][field] = value
    enriched = enrich_objects(graph, response)
    assert enriched["enrichment"]["applied_object_ids"] == []
    assert enriched["enrichment"]["dropped"][0]["reason"] == "invalid_annotation_fields"
    assert enriched["objects"] == graph["objects"]


def test_unanchored_and_duplicate_outputs_are_dropped_without_a_retry(scientific_case):
    _, _, graph, response = scientific_case
    response["annotations"] += [{"object_id": "invented", "meaning": "unanchored"},
                                copy.deepcopy(response["annotations"][0])]
    result = enrich_objects(graph, response)
    assert len(result["enrichment"]["applied_object_ids"]) == 1
    assert [d["reason"] for d in result["enrichment"]["dropped"]] == ["unanchored_object_id", "duplicate_object_id"]


@pytest.mark.parametrize("response", [None, [], {"schema_version": "wrong", "annotations": []},
                                     {"schema_version": "object-enrichment-1.0", "annotations": [], "patch": "bad"}])
def test_bad_envelope_does_not_mutate_the_derived_graph(scientific_case, response):
    _, _, graph, _ = scientific_case
    result = enrich_objects(graph, response)
    assert result["objects"] == graph["objects"]
    assert result["enrichment"]["dropped"] == [{"reason": "invalid_enrichment_envelope"}]


def test_offline_command_produces_context_and_enriched_artifacts(scientific_case, capsys):
    root, _, graph, response = scientific_case
    annotation = root / "interpretation.json"
    annotation.write_text(json.dumps(response))
    main(["scientific-objects", "--root", str(root), "--output", str(root / "objects.json"),
          "--llm-input", str(root / "input.json"), "--interpretations", str(annotation),
          "--markdown", str(root / "model.md")])
    capsys.readouterr()
    assert "Stiffness operator" in (root / "model.md").read_text()
    assert json.loads((root / "input.json").read_text())["context"]["scientific_passages"]
    output = json.loads((root / "objects.json").read_text())
    assert output["enrichment"]["applied_object_ids"]
    assert output["coverage"]["per_file"]


def test_code_first_interpretation_reaches_normal_repair_without_probe_loop(scientific_case):
    root, packet, graph, response = scientific_case
    class Driver:
        extraction_mode = "scientific_objects"
        async def prepare(self, seconds):
            self.payload = enrichment_input(graph, packet)
            return {"status": "ready"}
        async def interpret(self, instruction, seconds):
            # Deterministic model double: this verifies wiring, not discovery quality.
            assert self.payload["objects"]
            assert "stiffness" in json.dumps(self.payload["context"])
            self.response = response
            return {"status": "completed", "usage": {"input_tokens": 10, "cached_input_tokens": 0,
                                                     "output_tokens": 5, "reasoning_output_tokens": 1}}
        async def assemble(self, seconds):
            self.bundle = object_bundle(graph, self.response, self.payload["context"])
            return {**self.bundle["assembly"], "probes": []}
        async def probe(self, *args):
            raise AssertionError("Probe generation is not scientific-object enrichment")
        async def revise(self, *args):
            raise AssertionError("No automatic second model call in this method")
        async def run_stage(self, name, instruction, seconds):
            if name == "extract":
                return await run_extraction(self, instruction, seconds)
            self.repair_prompt = instruction
            return {"status": "completed", "usage": {"input_tokens": 20, "output_tokens": 5}}
        async def collect_graph(self, seconds):
            return self.bundle
        async def finish_extraction(self):
            pass
        async def cleanup(self):
            pass
    driver = Driver()
    result = asyncio.run(run_trial(driver, TrialConfig(total_seconds=30, extraction_seconds=20),
                                  "fixture", "science", "Repair this scientific model", root / "trial"))
    assert result["status"] == "completed"
    extraction = result["stages"][0]
    assert len(extraction["model_calls"]) == 1 and "probe_rounds" not in extraction
    assert extraction["selected_model_call"] == "extract_draft"
    assert extraction["usable_checkpoint"] is True
    assert "Stiffness operator" in driver.repair_prompt
    assert "Fixed boundary conditions" in driver.repair_prompt
    assert "not mandatory repair rules" in driver.repair_prompt
    assert "Rerun applicable supplied public probes" not in driver.repair_prompt
    assert driver.bundle["context"]["scientific_passages"]


def test_custom_science_without_library_rules_remains_annotatable(tmp_path):
    (tmp_path / "model.py").write_text(
        'def inventory(previous, flux, duration):\n'
        '    """Flux is outward transport; duration is the elapsed time."""\n'
        '    return previous - flux * duration\n')
    (tmp_path / "README.md").write_text("The inventory decreases by outward transport over elapsed time.\n")
    packet = build_packet(tmp_path)
    graph = extract_objects(tmp_path, packet)
    assert graph["coverage"]["recognized_scientific_operations"] == 0
    assert graph["coverage"]["code_only_objects"] == len(graph["objects"]) > 0
    assert {op["properties"]["operator"] for op in graph["operations"]} == {"Sub", "Mult"}
    flux = next(o for o in graph["objects"] if o["symbol"] == "flux")
    response = {"schema_version": "object-enrichment-1.0", "annotations": [{
        "object_id": flux["id"], "meaning": "Outward transport rate, as defined in inventory's docstring.",
        "assumptions": ["The supplied transport convention applies to this inventory."]}]}
    combined = enrich_objects(graph, response)
    assert combined["enrichment"]["applied_object_ids"] == [flux["id"]]
    assert "Outward transport rate" in render_objects(combined)
    assert "Flux is outward transport" in json.dumps(enrichment_input(graph, packet)["context"])


def test_real_packet_and_assembly_helpers_preserve_scientific_context(scientific_case, tmp_path, capsys):
    root, _, _, response = scientific_case
    context = root / "context"
    context.mkdir()
    (context / "task_statement.md").write_text("Repair the scientific displacement calculation.\n")
    scratch = root / "artifacts"
    scratch.mkdir()
    helper_main(["packet", "--root", str(root), "--context-root", str(context), "--task-id", "demo",
        "--output", str(scratch / "packet.json"), "--catalog", str(scratch / "catalog.md"),
        "--objects-output", str(scratch / "objects.json"), "--enrichment-input", str(scratch / "input.json")])
    annotation = scratch / "annotation.json"
    annotation.write_text(json.dumps(response))
    helper_main(["assemble-objects", "--graph", str(scratch / "objects.json"),
        "--annotations", str(annotation), "--context-input", str(scratch / "input.json"),
        "--output", str(scratch / "bundle.json")])
    capsys.readouterr()
    bundle = json.loads((scratch / "bundle.json").read_text())
    assert bundle["graph"]["task_id"] == "demo"
    assert bundle["assembly"]["interpretation_status"] == "enriched"
    assert "Stiffness operator" in bundle["handoff"]
    assert "Repair the scientific displacement" in json.dumps(bundle["context"])


def _large_graph(interfaces=5, literals=400):
    objects, operations, links = [], [], []
    for i in range(interfaces):
        objects.append({"id": f"so_iface_{i}", "kind": "code_interface", "symbol": f"f{i}",
                        "scope": "module", "path": "model.py", "source_entry_ids": [f"e_iface_{i}"],
                        "properties": {}, "roles": []})
    for i in range(literals):
        objects.append({"id": f"so_lit_{i}", "kind": "literal", "symbol": None,
                        "scope": "module", "path": "model.py", "source_entry_ids": [f"e_lit_{i}"],
                        "properties": {"shape": [1]}, "roles": []})
    for i in range(interfaces):
        operations.append({"id": f"sop_call_{i}", "kind": "uninterpreted_call",
                           "source_entry_id": f"e_lit_{i}",
                           "inputs": [{"role": "receiver", "object_id": f"so_lit_{i}"}],
                           "output_ids": [f"so_iface_{i}"],
                           "properties": {"retrieved_targets": [{"object_id": f"so_iface_{i}"}]}})
        links.append({"source": f"so_lit_{i}", "target": f"sop_call_{i}", "relation": "input:receiver"})
        links.append({"source": f"sop_call_{i}", "target": f"so_iface_{i}", "relation": "produces"})
    for i in range(interfaces, literals):
        operations.append({"id": f"sop_call_{i}", "kind": "uninterpreted_call",
                           "source_entry_id": f"e_lit_{i}", "inputs": [],
                           "output_ids": [f"so_lit_{i}"], "properties": {}})
        links.append({"source": f"sop_call_{i}", "target": f"so_lit_{i}", "relation": "produces"})
    graph = {"objects": objects, "operations": operations, "links": links,
             "unsupported": [{"source_entry_id": f"e_lit_{i}", "path": "model.py", "reason": "x"}
                             for i in range(literals + interfaces)]}
    packet = {"documents": [{"text": "public scientific doc"}], "entries": [
        {"id": f"e_iface_{i}", "kind": "signature", "path": "model.py", "sha256": "a",
         "start_line": 1, "end_line": 1, "scope": "module", "text": "def f", "language": "python",
         "native": {}} for i in range(interfaces)] + [
        {"id": f"e_lit_{i}", "kind": "assignment", "path": "model.py", "sha256": "b",
         "start_line": 2, "end_line": 2, "scope": "module", "text": f"x{i}=1", "language": "python",
         "native": {}} for i in range(literals)]}
    return graph, packet


def test_enrichment_input_selects_workflow_relevant_objects_first():
    graph, packet = _large_graph()
    payload = enrichment_input(graph, packet)
    selection = payload["selection"]
    assert selection["truncated"] is True
    assert selection["kept_objects"] <= 300
    assert selection["kept_unsupported"] <= 200
    kept_ids = {o["id"] for o in payload["objects"]}
    assert {f"so_iface_{i}" for i in range(5)} <= kept_ids
    assert all(f"so_lit_{i}" in kept_ids for i in range(5))  # dataflow neighbors kept
    assert {o["id"] for o in payload["objects"][:5]} == {f"so_iface_{i}" for i in range(5)}
    endpoint_ids = kept_ids | {op["id"] for op in payload["operations"]}
    assert all(link["source"] in endpoint_ids and link["target"] in endpoint_ids
               for link in payload["links"])
    assert payload["context"]["scientific_passages"] == [{"text": "public scientific doc"}]
    assert any(entry["id"].startswith("e_iface_") for entry in payload["context"]["code_passages"])


def test_enrichment_input_size_cap_drops_lowest_priority():
    objects = [{"id": f"so_{i}", "kind": "literal", "symbol": None, "scope": "m",
                "path": "m.py", "source_entry_ids": [f"e_{i}"],
                "properties": {"shape": [1]}, "roles": []} for i in range(60)]
    entries = [{"id": f"e_{i}", "kind": "assignment", "path": "m.py", "sha256": "c",
                "start_line": 1, "end_line": 1, "scope": "m", "text": "y" * 60_000,
                "language": "python", "native": {}} for i in range(60)]
    graph = {"objects": objects, "operations": [], "links": [], "unsupported": []}
    payload = enrichment_input(graph, {"documents": [], "entries": entries})
    selection = payload["selection"]
    size = len(json.dumps(payload, ensure_ascii=False).encode())
    assert selection["truncated"] is True
    assert 25 <= selection["kept_objects"] < 60
    # Either inside the byte budget or pinned at the hard object floor.
    assert size <= 1_500_000 or selection["kept_objects"] == 25
    # Measured on the receipt-bearing payload; tiny self-reference drift is fine.
    assert abs(selection["serialized_bytes"] - size) <= 64


def test_enrichment_input_prioritizes_interfaces_even_without_retrieved_targets():
    objects = [{"id": "so_iface", "kind": "code_interface", "symbol": "step", "scope": "module",
                "path": "model.py", "source_entry_ids": ["e_iface"], "properties": {}, "roles": []},
               *[{"id": f"so_lit_{i}", "kind": "literal", "symbol": None, "scope": "module",
                  "path": "model.py", "source_entry_ids": [f"e_{i}"],
                  "properties": {"shape": [1]}, "roles": []} for i in range(400)]]
    graph = {"objects": objects, "operations": [], "links": [], "unsupported": []}
    packet = {"documents": [], "entries": []}
    payload = enrichment_input(graph, packet)
    kept = payload["objects"]
    assert kept[0]["id"] == "so_iface"
    assert payload["selection"]["kept_objects"] <= 300


def test_enrichment_prompt_directs_early_scratch_write():
    prompt = (Path(__file__).resolve().parent.parent / "prompts/enrich_objects.md").read_text()
    assert "{scratch}/extract_draft-annotations.json" in prompt
    assert "even if the turn later times out" in prompt
    assert "Annotate the most task-relevant" in prompt
