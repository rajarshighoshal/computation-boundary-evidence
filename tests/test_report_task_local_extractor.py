"""Synthetic extraction-only reporting checks; no models or hidden tests run."""
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location("report_task_local_extractor", SCRIPTS / "report_task_local_extractor.py")
report = importlib.util.module_from_spec(spec)
spec.loader.exec_module(report)


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


def fixture(root, *, graph=True, completed=True, reasoning=True):
    dump(root / "schedule.json", {"kind": "extraction_verification", "status": "completed" if completed else "interrupted",
         "config": {"task_ids": ["009", "091"]},
         "schedule": [{"task_id": task, "condition": "science", "status": "completed" if completed else "pending"}
                      for task in ("009", "091")]})
    trial = root / "jobs/task-009-science/trial"
    usage = {"input_tokens": 100, "cached_input_tokens": 40, "output_tokens": 20}
    run = {"task_id": "009", "condition": "science", "extraction_only": True,
           "model": "synthetic", "reasoning_effort": "medium", "codex_version": "test", "config": {"total_seconds": 360},
           "status": "completed" if completed else "timeout", "extraction_status": "usable_graph",
           "duration_seconds": 10, "stages": [{"name": "extract", "status": "completed" if completed else "timeout",
                                               "usage": usage, "phases": [{"name": "interpret", "status": "completed"}]}]}
    if graph:
        graph_value = {"claims": [{"id": "c1"}]}
        digest = hashlib.sha256(json.dumps(graph_value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        run["graph_sha256"] = digest
        dump(trial / "graph-bundle.json", {"graph": graph_value, "graph_sha256": digest,
             "validation": {"valid": True}, "assembly": {"usable": True, "accepted_claim_ids": ["c1"],
             "code_bindings": [{"status": "source_matched"}], "relations": [{"claim_id": "c1"}],
             "dependency_links": [{"status": "unknown"}]}, "analysis": {
             "code_grounding": [{"status": "source_matched"}], "alignments": [{"status": "unknown"}],
             "coverage": {"lift_unknown": 1}}})
    dump(trial / "run.json", run)
    dump(trial / "agent/extract-final.txt", {"schema_version": "annotations-1.0", "claims": []})
    raw_usage = {**usage, **({"reasoning_output_tokens": 5} if reasoning else {})}
    dump(trial / "agent/extract.jsonl", {"type": "turn.completed", "usage": raw_usage})
    dump(root / "summary/summary.json", report.recompute(root / "jobs"))
    return trial


def test_complete_and_unrun_tasks_with_audited_usage(tmp_path):
    fixture(tmp_path)
    result = report.collect(tmp_path)
    row, unrun = result["records"]
    assert result["summary_audit"] == "verified"
    assert row["usable_graph"] is True
    assert row["accepted_claims"] == row["matched_quantity_bindings"] == row["unknown_alignments"] == 1
    assert row["tokens"]["total_tokens"] == 120
    assert row["tokens"]["reasoning_output_tokens"] == 5
    assert row["assembly"]["dependency_links"] == [{"status": "unknown"}]
    assert unrun["status"] == "no receipt" and unrun["accepted_claims"] is None
    report.main(["--run-root", str(tmp_path), "--json-output", str(tmp_path / "out.json"),
                 "--markdown-output", str(tmp_path / "out.md")])
    assert "| 009 | 100 | 40 | 20 | 5 | 120 |" in (tmp_path / "out.md").read_text()


@pytest.mark.parametrize("graph,completed", [(False, True), (True, False), (False, False)])
def test_missing_graph_or_incomplete_stage_has_unknown_quality(tmp_path, graph, completed):
    fixture(tmp_path, graph=graph, completed=completed)
    row = report.collect(tmp_path)["records"][0]
    assert row["usable_graph"] is None
    assert row["accepted_claims"] is row["source_matched_implementations"] is None
    if not completed:
        assert all(value is None for value in row["tokens"].values())


def test_unknown_reasoning_is_not_zero(tmp_path):
    fixture(tmp_path, reasoning=False)
    row = report.collect(tmp_path)["records"][0]
    assert row["tokens"]["reasoning_output_tokens"] is None
    assert row["tokens"]["total_tokens"] == 120


def test_graph_hash_mismatch_is_rejected(tmp_path):
    trial = fixture(tmp_path)
    bundle = report.read(trial / "graph-bundle.json")
    bundle["graph"]["claims"].append({"id": "tampered"})
    dump(trial / "graph-bundle.json", bundle)
    with pytest.raises(ValueError, match="Graph hash mismatch"):
        report.collect(tmp_path)


def test_changed_summary_is_rejected(tmp_path):
    fixture(tmp_path)
    dump(tmp_path / "summary/summary.json", {})
    with pytest.raises(ValueError, match="Summary does not match"):
        report.collect(tmp_path)


@pytest.mark.parametrize("artifact", ["verifier/reward.json", "agent/repair.jsonl"])
def test_repair_or_hidden_test_artifacts_are_rejected_before_audit(tmp_path, artifact):
    trial = fixture(tmp_path)
    dump(trial / artifact, {})
    with pytest.raises(ValueError, match="repairs or hidden tests"):
        report.collect(tmp_path)
