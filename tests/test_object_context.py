"""One-format public-evidence and CLI checks; model interpretations are fixtures."""
import copy
import json
from pathlib import Path

from scicontext.cli import main
from scicontext.object_context import enrichment_input, object_bundle, render_guide
from scicontext.packet import build_packet
from scicontext.scientific_model import reading_input, VERSION
from scicontext.scientific_objects import extract_objects


def fixture(root):
    (root / "model.py").write_text('def advance(q, flux, dt):\n    return q - flux * dt\n')
    (root / "README.md").write_text("Positive flux leaves the inventory. Duration and flux use matching time units.")
    packet = build_packet(root, multilingual=True)
    graph = extract_objects(root, packet)
    view = reading_input(enrichment_input(graph, packet))
    computation = next(c for c in view["computations"] if "advance" in c["name"])
    citation = next(s["id"] for s in view["sources"] if s["path"] == "README.md")
    claim = {"text": "Subtract transported material from inventory.", "source_ids": [citation]}
    response = {"schema_version": VERSION, "purpose": claim, "computations": [
        {"computation_id": computation["id"], "meaning": claim, "quantities": [], "conventions": [], "assumptions": []}]}
    return packet, graph, view, response


def test_raw_evidence_is_preserved_before_abstraction(tmp_path):
    packet, graph, _, _ = fixture(tmp_path)
    original = copy.deepcopy((packet, graph))
    payload = enrichment_input(graph, packet)
    assert payload["context"]["code_passages"] == packet["entries"]
    assert payload["objects"] == graph["objects"] and payload["links"] == graph["links"]
    assert (packet, graph) == original


def test_custom_science_without_library_rules_remains_annotatable(tmp_path):
    _, graph, view, response = fixture(tmp_path)
    assert graph["coverage"]["recognized_scientific_operations"] == 0
    bundle = object_bundle(graph, response, view)
    assert bundle["assembly"]["usable"]
    assert "Subtract transported material" in bundle["handoff"]
    assert bundle["graph"]["scientific_model"]["templates"]


def test_offline_command_produces_context_and_enriched_artifacts(tmp_path, capsys):
    _, _, _, response = fixture(tmp_path)
    interpretation = tmp_path / "response.json"
    interpretation.write_text(json.dumps(response))
    main(["scientific-objects", "--root", str(tmp_path), "--output", str(tmp_path / "objects.json"),
          "--llm-input", str(tmp_path / "input.json"), "--interpretations", str(interpretation),
          "--markdown", str(tmp_path / "model.md")])
    capsys.readouterr()
    assert "Subtract transported material" in (tmp_path / "model.md").read_text()
    assert json.loads((tmp_path / "input.json").read_text())["templates"]


def test_no_legacy_fallback_or_code_only_science(tmp_path):
    _, graph, view, _ = fixture(tmp_path)
    response = {"schema_version": "object-enrichment-1.0", "annotations": []}
    assert not object_bundle(graph, response, view)["assembly"]["usable"]
    assert render_guide(graph) == ""


def test_enrichment_prompt_is_short_direct_and_formattable():
    prompt = (Path(__file__).resolve().parents[1] / "prompts/scientific_repair.md").read_text()
    assert len(prompt.split()) < 220
    assert '"#graph"' in prompt
    assert "record_model unlocks" in prompt
    assert prompt.format(instruction="Repair the stored-material calculation.")
