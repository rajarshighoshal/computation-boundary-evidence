"""The actual draft/revision templates match the standard runtime interface."""
from pathlib import Path

import pytest


PROMPTS = Path(__file__).resolve().parents[1] / "prompts"


@pytest.mark.parametrize("name", ["extract.md", "extract_revision.md"])
def test_semantic_templates_format_without_losing_revision_feedback(name):
    path = PROMPTS / name
    feedback = '{"binding_error":"unresolved synthetic entity", "probe_status":"failed"}'
    text = path.read_text().format(root="/app/task_synthetic", scratch="/opt/scicontext/scratch",
        runtime="/opt/scicontext/runtime", seconds=40, explore_until="00:00:20 UTC",
        save_by="00:00:30 UTC", finish_by="00:00:35 UTC", instruction="Read the public definition",
        feedback=feedback)
    for field in ("entity_id", "scientific_object", "applicability", "alternative_interpretation", "discriminating_observation"):
        assert field in text
    assert "Read the public definition" in text
    if name == "extract_revision.md":
        assert feedback in text
        assert "only correction pass" in text and "ORIGINAL potentially buggy code" in text
    else:
        assert "Do NOT execute probes" in text


@pytest.mark.parametrize("name", ["extract.md", "extract_revision.md"])
def test_probe_first_contract_keeps_scientific_expectation_honest(name):
    text = (PROMPTS / name).read_text()
    for requirement in ("expected relationship", "applicability", "discriminating control",
                        "diagnostic", "unresolved", "probes: []", "inspected",
                        "input convention", "reimplemented equation", "citation-only"):
        assert requirement in text
    assert "Do NOT execute probes" in text
    assert "complete index" in text
    assert "minimum useful" in text


def test_first_draft_targets_one_probe_without_waiting_for_revision():
    text = (PROMPTS / "extract.md").read_text()
    assert "Your first deliverable is one supported scientific claim linked to an executable public probe" in text
    assert "Do not defer the useful deliverable" in text
    assert "one is enough" in text
    assert "Call the inspected repository code" in text
    assert "latest stopping points, not a schedule to fill" in text
    assert "You may also INCLUDE" not in text


def test_revised_probe_execution_is_possible_but_not_presumed():
    text = (PROMPTS / "extract_revision.md").read_text()
    assert "code will attempt accepted new/changed probes after your" in text
    assert "if execution time remains" in text
    assert "record whether they ran" in text
    assert "Old results remain observations of the old" in text
    assert "do not claim it has run or will run" not in text
