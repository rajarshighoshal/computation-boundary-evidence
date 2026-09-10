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


def test_completed_workflow_does_not_hide_extraction_timeout(tmp_path):
    trial = fixture(tmp_path, graph=False)
    run = report.read(trial / "run.json")
    run["extraction_status"] = "no_valid_graph"
    run["stages"][0]["status"] = "timeout"
    run["stages"][0]["phases"] = [{"name": "extract_draft", "status": "timeout",
                                  "allowance_seconds": 135, "duration_seconds": 125}]
    dump(trial / "run.json", run)
    dump(tmp_path / "summary/summary.json", report.recompute(tmp_path / "jobs"))
    data = report.collect(tmp_path)
    content = report.render(data)
    assert "| 009 | completed | timeout | no_valid_graph | False |" in content
    assert "| extract_draft | timeout | 135.00 | 125.00 |" in content


def test_multicall_totals_and_leaf_rows(tmp_path):
    trial = fixture(tmp_path)
    run = report.read(trial / "run.json")
    stage = run["stages"][0]
    stage["model_calls"] = [{"name": name, "status": "completed", "usage": dict(stage["usage"])}
                            for name in ("extract_draft", "extract_revision")]
    stage["usage"] = {field: value * 2 for field, value in stage["usage"].items()}
    stage["selected_model_call"] = "extract_draft"
    dump(trial / "agent/extract_draft-final.txt", {"schema_version": "annotations-1.0", "probes": [{}]})
    for call in stage["model_calls"]:
        dump(trial / "agent" / f"{call['name']}.jsonl", {
            "type": "turn.completed", "usage": {**call["usage"], "reasoning_output_tokens": 5}})
        dump(trial / "agent" / f"{call['name']}-sessions/session.jsonl", {
            "type": "session_meta", "payload": {"source": "exec", "id": call["name"]}})
    dump(trial / "run.json", run)
    dump(tmp_path / "summary/summary.json", report.recompute(tmp_path / "jobs"))
    result = report.collect(tmp_path)
    row = result["records"][0]
    assert row["tokens"]["total_tokens"] == 240
    assert row["selected_model_call"] == "extract_draft"
    assert row["declared_probes"] == 1
    assert [m["id"] for m in row["session_metadata"]] == ["extract_draft", "extract_revision"]
    content = report.render(result)
    assert "| 009 | 200 | 80 | 40 | 10 | 240 |" in content
    assert "| 009 | extract_draft | completed | 100 | 40 | 20 | 5 | 120 |" in content
    assert "| 009 | extract_revision | completed | 100 | 40 | 20 | 5 | 120 |" in content


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


def probe(version, *, status="passed", exit_code=0):
    source = f"print({version})\n"
    spec = {"id": "p1", "fingerprint": f"interpretation-{version}", "source": source}
    receipt = {"id": "p1", "fingerprint": spec["fingerprint"],
               "script_sha256": hashlib.sha256(source.encode()).hexdigest(),
               "status": status, "exit_code": exit_code,
               "artifact": f"probe-results/round-{version}/p1/receipt.json"}
    return spec, receipt


def round_fixture(root, *, changed=True, final_receipt=True):
    trial = fixture(root)
    run = report.read(trial / "run.json")
    first, first_result = probe(1)
    final, final_result = probe(2) if changed else (first, first_result)
    run["stages"][0]["probe_rounds"] = [{"phase": "probes", "specs": [first], "results": [first_result]}]
    if changed and final_receipt:
        run["stages"][0]["probe_rounds"].append({"phase": "revision_probes", "specs": [final], "results": [final_result]})
    run["stages"][0]["probe_delivery"] = {"accepted_ids": ["p1"],
        "executed_ids": ["p1"] if final_receipt else [], "status": "executed" if final_receipt else "partly_or_not_executed"}
    bundle = report.read(trial / "graph-bundle.json")
    bundle["probes"] = [final]
    bundle["analysis"]["probe_results"] = [final_result] if final_receipt else [first_result]
    dump(trial / "run.json", run)
    dump(trial / "graph-bundle.json", bundle)
    dump(root / "summary/summary.json", report.recompute(root / "jobs"))
    return trial


@pytest.mark.parametrize("changed", [False, True])
def test_probe_rounds_report_final_selection_and_preserve_history(tmp_path, changed):
    trial = round_fixture(tmp_path, changed=changed)
    assert not (trial / "agent/extract-scratch/probe-results.json").exists()
    result = report.collect(tmp_path)
    row = result["records"][0]
    assert row["probe_receipt_status"] == "available"
    assert len(row["probe_rounds"]) == (2 if changed else 1)
    assert row["selected_probe_results"] == [probe(2 if changed else 1)[1]]
    assert row["probe_results"] == row["selected_probe_results"]
    assert row["unmatched_supplied_probe_results"] == []
    content = report.render(result)
    assert 'Task 009 final-selected probe results: {"passed": 1}.' in content
    assert "may include superseded interpretations" in content
    if changed:
        assert "| 2 | revision_probes | p1 |" in content


def test_stale_same_id_does_not_count_as_final_execution(tmp_path):
    round_fixture(tmp_path, final_receipt=False)
    result = report.collect(tmp_path)
    row = result["records"][0]
    assert row["selected_probe_results"] == []
    assert row["unmatched_supplied_probe_results"] == [probe(1)[1]]
    assert row["probe_rounds"][0]["results"] == [probe(1)[1]]
    content = report.render(result)
    assert "Task 009 final-selected probe results: no matching execution receipts." in content
    assert "Final probes without a completed execution receipt: p1." in content


def test_matching_fingerprint_but_changed_source_is_not_execution(tmp_path):
    trial = round_fixture(tmp_path)
    bundle = report.read(trial / "graph-bundle.json")
    bundle["probes"][0]["source"] = "print('different')\n"
    dump(trial / "graph-bundle.json", bundle)
    assert report.collect(tmp_path)["records"][0]["selected_probe_results"] == []


@pytest.mark.parametrize("missing", [False, True])
def test_no_probe_known_zero_vs_missing_unknown(tmp_path, missing):
    trial = fixture(tmp_path)
    run = report.read(trial / "run.json")
    run["stages"][0]["probe_rounds"] = []
    if missing:
        run["stages"][0]["status"] = "timeout"
    else:
        bundle = report.read(trial / "graph-bundle.json")
        bundle["probes"] = []
        bundle["analysis"]["probe_results"] = []
        dump(trial / "graph-bundle.json", bundle)
    dump(trial / "run.json", run)
    dump(tmp_path / "summary/summary.json", report.recompute(tmp_path / "jobs"))
    result = report.collect(tmp_path)
    row = result["records"][0]
    assert row["selected_probe_results"] == (None if missing else [])
    assert row["probe_receipt_status"] == ("missing" if missing else "available")
    assert f"Task 009 final-selected probe results: {'unknown' if missing else 'none accepted'}." in report.render(result)


def test_probe_timeout_is_preserved_without_claiming_completed_execution(tmp_path):
    trial = round_fixture(tmp_path, changed=False)
    spec, receipt = probe(1, status="timeout", exit_code=None)
    run = report.read(trial / "run.json")
    run["stages"][0]["probe_rounds"][0]["results"] = [receipt]
    bundle = report.read(trial / "graph-bundle.json")
    bundle["analysis"]["probe_results"] = [receipt]
    dump(trial / "run.json", run)
    dump(trial / "graph-bundle.json", bundle)
    dump(tmp_path / "summary/summary.json", report.recompute(tmp_path / "jobs"))
    content = report.render(report.collect(tmp_path))
    assert 'final-selected probe results: {"timeout": 1}.' in content
    assert "Final probes without a completed execution receipt: p1." in content


def test_report_extractor_dispatches_round_aware_artifacts(tmp_path):
    import report_extractor
    round_fixture(tmp_path)
    report_extractor.main(["--run-root", str(tmp_path), "--json-output", str(tmp_path / "out.json"),
                           "--markdown-output", str(tmp_path / "out.md")])
    assert json.loads((tmp_path / "out.json").read_text())["records"][0]["probe_receipt_status"] == "available"
    assert "final-selected probe results" in (tmp_path / "out.md").read_text()


@pytest.mark.parametrize("present", [False, True])
def test_legacy_probe_paths_do_not_gain_round_fields(tmp_path, present):
    trial = fixture(tmp_path)
    if present:
        dump(trial / "agent/extract-scratch/probe-results.json", {"results": [probe(1)[1]]})
    row = report.collect(tmp_path)["records"][0]
    assert "probe_rounds" not in row
    assert row["probe_results"] == ([probe(1)[1]] if present else None)
    assert row["probe_receipt_status"] == ("available" if present else "missing")
