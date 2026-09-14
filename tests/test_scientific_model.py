"""Code/model/guide contract tests; fixture interpretations are not model-quality results."""
import asyncio
import copy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scicontext.controller import TrialConfig, run_trial
from scicontext.io import write_json
from scicontext.object_context import enrichment_input, object_bundle, render_guide
from scicontext.packet import build_packet
from scicontext.pier_agent import ScientificCodex
from scicontext.scientific_model import reading_input, VERSION
from scicontext.scientific_objects import extract_objects
from scicontext.tool_cli import main as helper


@pytest.fixture
def case(tmp_path):
    (tmp_path / "model.py").write_text('def advance(previous, flux, duration):\n'
        '    """Flux is outward transport per unit time."""\n'
        '    loss = flux * duration\n    result = previous - loss\n'
        '    if result < 0:\n        raise ValueError("negative inventory")\n    return result\n')
    (tmp_path / "README.md").write_text("This model tracks stored material. Positive flux leaves the store.\n"
        "Duration uses the same time unit as flux.\n")
    packet = build_packet(tmp_path, multilingual=True)
    graph = extract_objects(tmp_path, packet)
    graph["task_id"] = "synthetic"
    view = reading_input(enrichment_input(graph, packet))
    computation = next(c for c in view["computations"] if "advance" in c["name"])
    flux = next(o for o in graph["objects"] if o["symbol"] == "flux")
    doc = next(s for s in view["sources"] if s["path"] == "README.md")
    def claim(text):
        return {"text": text, "source_ids": [doc["id"]]}
    response = {"schema_version": VERSION, "purpose": claim("Track stored material under outward transport."),
        "computations": [{"computation_id": computation["id"],
            "meaning": claim("Subtract the transported amount from the previous inventory."),
            "quantities": [{"object_id": flux["id"], "meaning": claim("Outward material transport rate.")}],
            "conventions": [claim("Positive flux leaves the store; duration and flux use matching time units.")],
            "assumptions": ["This reading does not establish whether negative inventory must always be rejected."]}]}
    return graph, view, response


def test_source_owned_structure_and_scientific_meaning_join_without_mutation(case):
    graph, view, response = case
    old = copy.deepcopy((graph, view, response))
    bundle = object_bundle(graph, response, view)
    assert (graph, view, response) == old
    assert bundle["assembly"]["usable"]
    model = bundle["graph"]["scientific_model"]
    assert model["computations"][0]["interpretation"] == response["computations"][0]
    assert bundle["graph"]["operations"] == graph["operations"]
    assert bundle["graph"]["links"] == graph["links"]
    ids = {e["id"] for e in model["entities"]}
    assert all(r["source"] in ids and r["target"] in ids for r in model["relations"])
    guide = render_guide(bundle["graph"])
    assert "outward transport" in guide and "matching time units" in guide
    assert "Code relationships:" in guide and "flux" in guide and "Mult" in guide
    assert "README.md:1" in guide and "Assumption:" in guide
    assert "Code predicate: result < 0" in guide
    assert "scientific-model.json" in guide
    assert len(guide) <= 9000
    assert "not mechanically established" in model["validation"]


def test_observation_does_not_become_requirement_or_failure_label(case):
    graph, view, response = case
    view["observations"] = [{"collapse": False, "unchanged_output": True, "build_exit": 1}]
    model = object_bundle(graph, response, view)["graph"]
    guide = render_guide(model)
    assert "containment violation" not in guide and "must change" not in guide
    assert model["scientific_model"]["observations"] == view["observations"]


@pytest.mark.parametrize("mutation,reason", [
    (lambda r: r["computations"][0].update(computation_id="fabricated"), "unknown_computation"),
    (lambda r: r["computations"][0]["meaning"].update(source_ids=["fabricated"]), "unknown_source_citation"),
    (lambda r: r["computations"][0]["quantities"][0].update(object_id="fabricated"), "quantity_outside_computation"),
    (lambda r: r["computations"][0].update(edges=[{"source": "x", "target": "y"}]), "invalid_computation_fields"),
    (lambda r: r["computations"][0].update(probes=["assert x"]), "invalid_computation_fields"),
])
def test_unanchored_or_structural_model_output_is_not_delivered(case, mutation, reason):
    graph, view, response = case
    mutation(response)
    bundle = object_bundle(graph, response, view)
    assert not bundle["assembly"]["usable"]
    assert bundle["handoff"] == ""
    assert bundle["assembly"]["enrichment"]["dropped"][0]["reason"] == reason


@pytest.mark.parametrize("response", [None, {"schema_version": VERSION, "purpose": {}, "computations": []},
                                      {"schema_version": "object-enrichment-1.0", "annotations": []}])
def test_failed_or_legacy_response_is_not_silent_code_only_v2_treatment(case, response):
    graph, view, _ = case
    bundle = object_bundle(graph, response, view)
    assert not bundle["assembly"]["usable"]
    assert bundle["assembly"]["status"] == "no_scientific_model"


def test_real_assembly_helper_uses_supplied_citations(case, tmp_path, capsys):
    graph, view, response = case
    for name, value in (("graph", graph), ("input", view), ("response", response)):
        write_json(tmp_path / f"{name}.json", value)
    helper(["assemble-objects", "--graph", str(tmp_path / "graph.json"), "--annotations", str(tmp_path / "response.json"),
            "--context-input", str(tmp_path / "input.json"), "--output", str(tmp_path / "bundle.json")])
    capsys.readouterr()
    result = json.loads((tmp_path / "bundle.json").read_text())
    assert result["assembly"]["usable"] and result["validation"]["valid"]
    assert "outward transport" in result["handoff"]


def test_real_collection_and_controller_deliver_science_once(case, tmp_path):
    graph, view, response = case
    bundle = object_bundle(graph, response, view)
    class Environment:
        def __init__(self): self.uploaded = {}
        async def download_dir(self, remote, local): local.mkdir(parents=True, exist_ok=True)
        async def download_file(self, remote, local): write_json(local, bundle)
        async def upload_file(self, local, remote): self.uploaded[remote] = local.read_text()
    env = Environment()
    driver = SimpleNamespace(extract_environment=env, environment=env, logs_dir=tmp_path / "logs",
        root="/app/task_synthetic", task_id="synthetic", _selected_remote="/bundle.json")
    driver.logs_dir.mkdir()
    handoff = asyncio.run(ScientificCodex.collect_graph(driver, 20))
    assert "/opt/scicontext/context/scientific-model.json" in env.uploaded
    assert json.loads(env.uploaded["/opt/scicontext/context/scientific-model.json"])["computations"]
    assert "outward transport" in handoff["guide_markdown"]
    assert "outward transport" not in handoff["handoff"]  # Pointer, not a second inline guide.
    class Trial:
        async def run_stage(self, name, prompt, seconds):
            if name == "repair": self.prompt = prompt
            return {"status": "completed"}
        async def collect_graph(self, seconds): return handoff
        async def finish_extraction(self): pass
        async def cleanup(self): pass
    trial = Trial()
    result = asyncio.run(run_trial(trial, TrialConfig(total_seconds=30, extraction_seconds=15),
        "synthetic", "science", "Repair the material calculation.", tmp_path / "trial"))
    assert result["status"] == "completed"
    assert trial.prompt.startswith("Repair the material calculation.")
    assert trial.prompt.count("Track stored material under outward transport.") == 1
    assert "README.md:1" in trial.prompt and "Code relationships:" in trial.prompt


def test_guide_keeps_conditions_and_assumptions_with_each_displayed_computation(case):
    graph, view, response = case
    c = response["computations"][0]
    c["meaning"]["text"] = "M" * 600
    c["conventions"] = [{"text": f"CONDITION {i}: " + "c" * 580, "source_ids": c["meaning"]["source_ids"]} for i in range(4)]
    c["assumptions"] = ["ASSUMPTION " + "a" * 220]
    guide = object_bundle(graph, response, view)["handoff"]
    assert all(f"CONDITION {i}" in guide for i in range(4)) and "ASSUMPTION" in guide


def test_same_names_in_different_scopes_do_not_share_quantity_identity(tmp_path):
    (tmp_path / "model.py").write_text("def a(x):\n    return x * 2\ndef b(x):\n    return x + 1\n")
    packet = build_packet(tmp_path, multilingual=True)
    graph = extract_objects(tmp_path, packet)
    view = reading_input(enrichment_input(graph, packet))
    scopes = [set(c["entity_ids"]) for c in view["computations"] if c["name"].endswith(("a@1", "b@3"))]
    assert len(scopes) == 2 and not scopes[0] & scopes[1]
    assert view == reading_input(enrichment_input(graph, packet))


def test_omitted_operands_remain_explicit_unknowns():
    graph = {"objects": [], "operations": [{"id": "op", "kind": "arithmetic", "source": {},
        "inputs": [{"role": "x", "object_id": "not_supplied"}], "output_ids": ["missing_output"]}], "links": [], "unsupported": [{"reason": "partial_parse"}]}
    view = reading_input(graph)
    operand = view["entities"][0]["inputs"][0]
    assert operand == {"role": "x", "object_id": None, "unresolved_object_id": "not_supplied"}
    assert view["entities"][0]["output_ids"] == []
    assert view["entities"][0]["unresolved_output_ids"] == ["missing_output"]
    assert view["coverage"]["unsupported"] == [{"reason": "partial_parse"}]


def test_long_valid_computation_is_not_silently_reduced_to_a_file_pointer(case):
    graph, view, response = case
    c = response["computations"][0]
    for i, identifier in enumerate(view["computations"][0]["entity_ids"][:8]):
        c["quantities"].append({"object_id": identifier, "meaning": {"text": "q" * 600, "source_ids": c["meaning"]["source_ids"]}})
    c["quantities"] = list({q["object_id"]: q for q in c["quantities"]}.values())[:8]
    c["conventions"] = [{"text": f"IMPORTANT {i}:" + "c" * 580, "source_ids": c["meaning"]["source_ids"]} for i in range(4)]
    c["assumptions"] = ["a" * 240] * 3
    bundle = object_bundle(graph, response, view)
    assert bundle["assembly"]["usable"]
    assert "Subtract the transported amount" in bundle["handoff"]
    assert all(f"IMPORTANT {i}" in bundle["handoff"] for i in range(4))
    assert "Code predicate: result < 0" in bundle["handoff"]


def test_codex_response_and_direct_prompt_keep_connected_envelope(case, tmp_path):
    graph, view, response = case
    class Driver:
        workspace = Path(__file__).resolve().parent.parent
        frozen_source = None
        extraction_model_seconds = None
        root = "/app/task_synthetic"
        logs_dir = tmp_path
        extract_environment = object()
        async def _run_codex(self, name, prompt, seconds):
            assert '"schema_version":"object-enrichment-2.0"' in prompt
            assert "scientific-context-input.json" in prompt
            write_json(tmp_path / "extract_draft-final.txt", response)
            return {"status": "completed"}
        async def _put(self, environment, name, text, destination): self.saved = json.loads(text)
    driver = Driver()
    result = asyncio.run(ScientificCodex._interpret_call(driver, "Repair stored material", 60))
    assert result["annotations_status"] == "received" and driver.saved == response


def test_shared_provider_preparation_builds_compact_reading_input(case, tmp_path, monkeypatch):
    graph, view, response = case
    # Exercise the real preparation method, mocking only container transfer and
    # the already separately tested analyzer subprocess.
    raw = {"objects": graph["objects"], "operations": graph["operations"], "links": graph["links"],
           "unsupported": [], "context": {"scientific_passages": view["sources"], "code_passages": []}}
    class Environment:
        async def download_file(self, remote, local): write_json(local, raw)
        async def upload_file(self, local, remote): self.uploaded = json.loads(local.read_text())
    class Process:
        async def wait(self): return 0
    async def process(*args, **kwargs):
        output = Path(args[args.index("--output") + 1])
        write_json(output / "receipt.json", {"analyses": [], "gaps": []})
        return Process()
    monkeypatch.setattr(asyncio, "create_subprocess_exec", process)
    env = Environment()
    driver = SimpleNamespace(logs_dir=tmp_path, extract_environment=env, root="/app/task_synthetic")
    asyncio.run(ScientificCodex._augment_source_analysis(driver))
    assert env.uploaded["schema_version"] == "scientific-reading-2.0"
    assert env.uploaded["computations"] and env.uploaded["sources"]
    assert (tmp_path / "source-analysis/evidence-input.json").is_file()


def test_missing_scientific_model_never_runs_a_silent_baseline(tmp_path):
    class Trial:
        requires_scientific_model = True
        calls = []
        async def run_stage(self, name, prompt, seconds):
            self.calls.append(name)
            return {"status": "completed"}
        async def collect_graph(self, seconds): return None
        async def finish_extraction(self): pass
        async def cleanup(self): pass
    trial = Trial()
    with pytest.raises(RuntimeError, match="No scientific model was delivered"):
        asyncio.run(run_trial(trial, TrialConfig(total_seconds=30, extraction_seconds=15),
            "synthetic", "science", "Repair", tmp_path / "trial"))
    assert trial.calls == ["extract"]


def test_distinct_conventions_remain_with_their_own_computation(case):
    graph, view, response = case
    second = copy.deepcopy(view["computations"][0])
    second["id"], second["name"] = "second_definition", "inward_convention"
    view["entities"].append({"id": "second_definition", "kind": "code_interface", "source_ids": second["source_ids"]})
    second["entity_ids"] = ["second_definition", *second["entity_ids"]]
    view["computations"].append(second)
    interpretation = copy.deepcopy(response["computations"][0])
    interpretation["computation_id"] = "second_definition"
    interpretation["conventions"][0]["text"] = "INWARD convention requires separate interpretation."
    response["computations"].append(interpretation)
    guide = object_bundle(graph, response, view)["handoff"]
    first, second_text = guide.split("## inward_convention")
    assert "Positive flux leaves" in first and "INWARD convention" not in first
    assert "INWARD convention" in second_text and "Positive flux leaves" not in second_text


def test_top_level_operations_are_not_invented_function_definitions():
    ops = [{"id": name, "kind": "arithmetic", "inputs": [], "output_ids": [],
            "source": {"path": "m.py", "scope": "<module>", "start_line": i}}
           for i, name in enumerate(("first", "second"), 1)]
    view = reading_input({"objects": [], "operations": ops, "links": []})
    assert [c["entity_ids"] for c in view["computations"]] == [["first"], ["second"]]


def test_analyzer_scope_disambiguates_overlapping_source_ranges():
    def node(identifier, kind, scope=None):
        return {"id": identifier, "kind": kind, "analyzer": "joern", "path": "m.cpp", "start_line": 1,
                "end_line": 1, "text": "x", "scope": scope,
                "properties": {"NAME": identifier, "FULL_NAME": identifier, "LINE_NUMBER_END": 5}}
    rows = [node("a", "METHOD", "a"), node("b", "METHOD", "b"),
            node("known", "IDENTIFIER", "b"), node("ambiguous", "IDENTIFIER")]
    view = reading_input({"context": {"analysis_sources": rows}})
    definitions = {c["id"]: c for c in view["computations"]}
    assert "known" in definitions["b"]["entity_ids"] and "known" not in definitions["a"]["entity_ids"]
    assert all("ambiguous" not in c["entity_ids"] for c in definitions.values())


def test_analyzer_generated_predicate_is_not_presented_as_literal_source(case):
    graph, view, response = case
    bundle = object_bundle(graph, response, view)
    model = bundle["graph"]["scientific_model"]
    c = model["computations"][0]
    model["entities"].extend([
        {"id": "control", "kind": "CONTROL_STRUCTURE", "source_ids": []},
        {"id": "generated", "kind": "CALL", "source_ids": ["generated"]}])
    model["sources"].append({"id": "generated", "kind": "analyzer", "path": "model.py",
                             "start_line": 3, "end_line": 3, "text": "iteratorNonEmptyOrException"})
    model["relations"].append({"id": "generated_edge", "source": "control", "target": "generated", "relation": "CONDITION"})
    c["entity_ids"].extend(["control", "generated"])
    c["relation_ids"].append("generated_edge")
    guide = render_guide(bundle["graph"])
    assert "iteratorNonEmptyOrException" not in guide
    assert "Code predicate: result < 0" in guide
    assert any(s["text"] == "iteratorNonEmptyOrException" for s in model["sources"])
