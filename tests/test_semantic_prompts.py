"""The actual draft/revision templates match the standard runtime interface."""
from pathlib import Path

import pytest


@pytest.mark.parametrize("name", ["extract.md", "extract_revision.md"])
def test_semantic_templates_format_without_losing_revision_feedback(name):
    path = Path(__file__).resolve().parents[1] / "prompts" / name
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
