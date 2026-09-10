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
    assert set(payload) == {"objects", "operations", "links", "unsupported", "context"}
    assert "stiffness matrix" in json.dumps(payload["context"]["scientific_passages"])
    assert "np.linalg.solve" in json.dumps(payload["context"]["code_passages"])
    assert any(op["kind"] == "linear_solve" for op in payload["operations"])
    assert payload["links"] == graph["links"]


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
        async def assemble(self, outcomes, seconds):
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
    assert len(extraction["model_calls"]) == 1 and extraction["probe_rounds"] == []
    assert extraction["revision"]["reason"] == "not_part_of_scientific_object_enrichment"
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
