"""Before/after summaries preserve unknowns and do not invent scientific scores."""
import copy
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import compare_scientific_reading as comparison


def fixture(tmp_path, monkeypatch):
    roots = [tmp_path / "before", tmp_path / "after"]
    records = {}
    for root, source, tokens in zip(roots, ["reproduce.py", "source/model.f90"], [100, 80]):
        trial = root / "jobs/trial"
        trial.mkdir(parents=True)
        (trial / "graph-bundle.json").write_text(json.dumps({"graph": {"objects": [{
            "id": "object", "kind": "code_interface", "path": source, "scope": "scope", "source_span": {"start_line": 1},
            "interpretation": {"meaning": "Fixture interpretation, not scientific truth."}}]}}))
        records[root] = {"task_ids": ["fixture"], "schedule": {"config": {"model": "fixture", "extraction_model_seconds": 360},
            "implementation_revision": root.name, "selection_sha256": "same", "prompt_sha256": {"prompts/enrich_objects.md": "same"}},
            "token_totals": {"total_tokens": tokens}, "records": [{"task_id": "fixture", "trial_path": "jobs/trial",
            "stage_status": "completed", "interpretation_status": "enriched", "seconds": 5, "tokens": {"total_tokens": tokens}}]}
    monkeypatch.setattr(comparison, "report", lambda root: copy.deepcopy(records[root]))
    return roots, records


def test_comparison_reports_scope_and_cost_not_scientific_accuracy(tmp_path, monkeypatch):
    roots, _ = fixture(tmp_path, monkeypatch)
    result = comparison.compare(*roots)
    row = result["rows"][0]
    assert row["before"]["annotated_repository_objects"] == 0
    assert row["after"]["annotated_repository_objects"] == 1
    assert row["token_change_fraction"] == pytest.approx(-.2)
    assert "scientific_accuracy" not in row
    assert row["after"]["annotations"][0]["interpretation"]["meaning"].startswith("Fixture")


@pytest.mark.parametrize("mismatch", ["budget", "selection", "prompt"])
def test_protocol_mismatch_is_rejected(tmp_path, monkeypatch, mismatch):
    roots, records = fixture(tmp_path, monkeypatch)
    schedule = records[roots[1]]["schedule"]
    if mismatch == "budget":
        schedule["config"]["extraction_model_seconds"] = 720
    elif mismatch == "selection":
        schedule["selection_sha256"] = "different"
    else:
        schedule["prompt_sha256"]["prompts/enrich_objects.md"] = "different"
    with pytest.raises(ValueError):
        comparison.compare(*roots)


def test_missing_after_cost_stays_unknown(tmp_path, monkeypatch):
    roots, records = fixture(tmp_path, monkeypatch)
    records[roots[1]]["records"][0]["tokens"]["total_tokens"] = None
    records[roots[1]]["token_totals"]["total_tokens"] = None
    result = comparison.compare(*roots)
    assert result["rows"][0]["token_change_fraction"] is None
    assert result["total_token_change_fraction"] is None
