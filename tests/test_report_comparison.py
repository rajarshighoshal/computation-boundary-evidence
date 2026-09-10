"""Synthetic reporting checks; no model, Docker or private-test execution."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
spec = importlib.util.spec_from_file_location("report_comparison", SCRIPTS / "report_comparison.py")
report = importlib.util.module_from_spec(spec)
spec.loader.exec_module(report)


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def schedule(root, tasks=("010", "011"), status="completed"):
    config = {"task_ids": list(tasks), "condition_order": {task: ["baseline", "science"] for task in tasks},
              "model": "synthetic", "reasoning_effort": "high", "codex_version": "test",
              "pier_version": "test", "total_seconds": 1800, "extraction_seconds": 360,
              "attempts": 1, "concurrency": 1}
    value = {"status": status, "config": config,
             "started_at": "2026-09-10T00:00:00Z", "finished_at": "2026-09-10T00:10:00Z",
             "schedule": [{"task_id": task, "condition": arm, "status": "completed" if status == "completed" else "not_run"}
                          for task in tasks for arm in report.ARMS]}
    dump(root / "schedule.json", value)
    (root / "jobs").mkdir(exist_ok=True)
    return value


def trial(root, task, arm, *, success=True, infrastructure=False, usage=True, graph=False):
    directory = root / "jobs" / f"{task}-{arm}"
    stage = {"name": "repair", "status": "completed", "duration_seconds": 300,
             "usage": {"input_tokens": 100, "cached_input_tokens": 20, "output_tokens": 30} if usage else None}
    record = {"task_id": task, "condition": arm, "model": "synthetic", "reasoning_effort": "high",
              "codex_version": "test", "config": {"total_seconds": 1800, "extraction_seconds": 360},
              "status": "infrastructure_failure" if infrastructure else "completed",
              "duration_seconds": None if infrastructure else 400,
              "extraction_status": "usable_graph" if graph else "unknown" if arm == "science" else "not_applicable",
              "stages": [] if infrastructure else [stage]}
    if not infrastructure:
        patch = directory / "artifacts/model.patch"
        patch.parent.mkdir(parents=True)
        patch.write_text("synthetic patch " + task + arm)
        record["patch_sha256"] = hashlib.sha256(patch.read_bytes()).hexdigest()
        dump(directory / "verifier/reward.json", {
            "reward": float(success), "private": {"passed": 3 if success else 2, "collected": 3, "return_code": 0 if success else 1},
            "public": {"passed": 1, "collected": 1, "return_code": 0}})
        dump(directory / "agent/setup.json", {"docker_memory_bytes": 4 * 1024**3, "docker_cpus": 4,
             "task_requested_memory_mb": 8192, "host_memory_below_task_request": True})
    if graph:
        graph_value = {"claims": [{"id": "c1"}], "quantities": [], "evidence": [], "observations": []}
        digest = hashlib.sha256(json.dumps(graph_value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        record.update({"graph_sha256": digest, "graph_coverage": {"lift_supported": 1}})
        record["stages"].insert(0, {**stage, "name": "extract", "duration_seconds": 100,
                                   "phases": [{"name": "interpret", "status": "completed", "duration_seconds": 70}]})
        dump(directory / "graph-bundle.json", {"graph": graph_value, "graph_sha256": digest,
                                               "analysis": {"code_grounding": [{"status": "source_matched"}], "alignments": []}})
    dump(directory / "run.json", record)
    return directory


def summarize(root):
    summary = root / "summary.json"
    subprocess.run([sys.executable, str(SCRIPTS / "recompute_results.py"), str(root / "jobs"), "--output", str(summary)], check=True)
    return summary


def generate(root, summary=None):
    summary = summary or summarize(root)
    output = root / "report.md"
    report.main(["--run-root", str(root), "--summary", str(summary), "--output", str(output)])
    return output.read_text()


def test_complete_comparison_includes_counts_resources_phases_and_provenance(tmp_path):
    schedule(tmp_path)
    for task in ("010", "011"):
        trial(tmp_path, task, "baseline", success=task == "010")
        trial(tmp_path, task, "science", graph=True)
    content = generate(tmp_path)
    assert "Recorded attempts: 4/4" in content
    assert "| both_success | 1 |" in content
    assert "| science_only | 1 |" in content
    assert "| baseline | 2 | 2 | 1 | 1 | 0 | 0 |" in content
    assert "| science | input_tokens | 400 | 2 | 0 |" in content
    assert "| interpret | completed | 70.00 |" in content
    assert "claims=1" in content and "source_matched=1" in content
    assert "| 010 | baseline | available | 4.00 | 8.00 | 4 | True |" in content
    assert "Patch hashes checked: 4; patches missing: 0" in content
    assert "The planned comparison is incomplete" not in content
    assert "010/baseline → 010/science → 011/baseline → 011/science" in content


def test_partial_schedule_retains_unrun_tasks_and_unknown_costs(tmp_path):
    value = schedule(tmp_path, tasks=("010", "011", "012"), status="runner_failure")
    value["schedule"][0]["status"] = "completed"
    value["schedule"][1]["status"] = "infrastructure_failure"
    dump(tmp_path / "schedule.json", value)
    trial(tmp_path, "010", "baseline", usage=False)
    trial(tmp_path, "010", "science", infrastructure=True)
    content = generate(tmp_path)
    assert "Recorded attempts: 2/6" in content
    assert "The planned comparison is incomplete" in content
    assert "| unknown | 1 |" in content
    assert "| neither_arm_recorded | 2 |" in content
    assert "| science | 3 | 1 | 0 | 0 | 1 | 2 |" in content
    assert "| baseline | input_tokens | unknown | 0 | 1 |" in content
    assert "| science | duration_seconds | unknown | 0 | 1 |" in content
    assert "| 012 | science | not_run | no receipt | unknown | unknown/unknown | unknown | unknown |" in content
    assert "| 010 | science | missing | unknown | unknown | unknown | unknown |" in content
    assert "graph artifact: missing" in content
    assert "claims=unknown" in content


def test_empty_schedule_has_no_fake_zero_measurements(tmp_path):
    schedule(tmp_path, tasks=("010",), status="runner_failure")
    content = generate(tmp_path)
    assert "Recorded attempts: 0/2" in content
    assert "| neither_arm_recorded | 1 |" in content
    assert "| baseline | input_tokens | unknown | 0 | 0 |" in content


def test_operator_stop_explains_preinference_interruption(tmp_path):
    schedule(tmp_path, tasks=("010",), status="interrupted")
    dump(tmp_path / "operator-stop-request.json", {
        "reason": "User requested medium effort for later initial checks",
        "active_at_signal": [{"task_id": "010", "condition": "science", "phase": "pulling_images"}],
    })
    content = generate(tmp_path)
    assert "Operator-requested stop: User requested medium effort" in content
    assert "010/science during pulling_images" in content
    assert "not a model repair failure" in content


def test_missing_graph_and_setup_are_explicit_not_fatal(tmp_path):
    schedule(tmp_path, tasks=("010",))
    trial(tmp_path, "010", "baseline")
    directory = trial(tmp_path, "010", "science")
    (directory / "agent/setup.json").write_text("not JSON")
    content = generate(tmp_path)
    assert "graph artifact: missing" in content
    assert "| 010 | science | unreadable | unknown | unknown | unknown | unknown |" in content


def test_changed_patch_fails_before_writing_report(tmp_path):
    schedule(tmp_path, tasks=("010",))
    directory = trial(tmp_path, "010", "baseline")
    trial(tmp_path, "010", "science")
    summary = summarize(tmp_path)
    (directory / "artifacts/model.patch").write_text("changed patch")
    with pytest.raises(ValueError, match="Candidate patch hash changed"):
        generate(tmp_path, summary)
    assert not (tmp_path / "report.md").exists()


def test_missing_patch_is_reported_without_claiming_hash_verification(tmp_path):
    schedule(tmp_path, tasks=("010",))
    directory = trial(tmp_path, "010", "baseline")
    trial(tmp_path, "010", "science")
    (directory / "artifacts/model.patch").unlink()
    content = generate(tmp_path)
    assert "Patch hashes checked: 1; patches missing: 1" in content


def test_changed_graph_is_not_used_for_coverage_counts(tmp_path):
    schedule(tmp_path, tasks=("010",))
    trial(tmp_path, "010", "baseline")
    directory = trial(tmp_path, "010", "science", graph=True)
    summary = summarize(tmp_path)
    bundle = report.read(directory / "graph-bundle.json")
    bundle["graph"]["claims"].append({"id": "c2"})
    dump(directory / "graph-bundle.json", bundle)
    with pytest.raises(ValueError, match="Graph hash changed"):
        generate(tmp_path, summary)


def test_summary_tampering_fails_independent_audit(tmp_path):
    schedule(tmp_path, tasks=("010",), status="runner_failure")
    trial(tmp_path, "010", "baseline")
    summary = summarize(tmp_path)
    value = report.read(summary)
    value["trials"][0]["duration_seconds"] = 0
    dump(summary, value)
    with pytest.raises(subprocess.CalledProcessError):
        generate(tmp_path, summary)
    assert not (tmp_path / "report.md").exists()


def test_unplanned_trial_cannot_be_silently_dropped(tmp_path):
    schedule(tmp_path, tasks=("010",))
    trial(tmp_path, "011", "baseline")
    with pytest.raises(ValueError, match="Unplanned"):
        generate(tmp_path)


def test_schedule_budget_cannot_misdescribe_run(tmp_path):
    value = schedule(tmp_path, tasks=("010",))
    value["config"]["total_seconds"] = 900
    dump(tmp_path / "schedule.json", value)
    trial(tmp_path, "010", "baseline")
    with pytest.raises(ValueError, match="Run budget differs"):
        generate(tmp_path)


def raw_usage(directory, name="repair", usages=None):
    usages = usages if usages is not None else [{"input_tokens": 100, "cached_input_tokens": 20,
                                               "output_tokens": 30, "reasoning_output_tokens": 12}]
    (directory / "agent").mkdir(exist_ok=True)
    (directory / "agent" / f"{name}.jsonl").write_text(
        "CLI diagnostic\n" + "\n".join(json.dumps({"type": "turn.completed", "usage": u}) for u in usages))


def test_raw_breakdown_subsets_and_trial_totals_do_not_double_count(tmp_path):
    schedule(tmp_path, tasks=("010",))
    directory = trial(tmp_path, "010", "science", graph=True)
    raw_usage(directory, "extract")
    raw_usage(directory)
    content = generate(tmp_path)
    assert "| 010 | science | extract | completed | 100 | 20 | 80 | 30 | 12 | 18 | 130 |" in content
    assert "| 010 | science | trial total | completed | 200 | 40 | 160 | 60 | 24 | 36 | 260 |" in content
    assert "| 010 | baseline | trial total | no receipt | unknown | unknown | unknown | unknown | unknown | unknown | unknown |" in content
    assert "| 010 | unknown | 130 | 130 | 260 | unknown |" in content


def test_treatment_stage_costs_compare_with_complete_baseline(tmp_path):
    schedule(tmp_path, tasks=("010",))
    baseline = trial(tmp_path, "010", "baseline")
    science = trial(tmp_path, "010", "science", graph=True)
    raw_usage(baseline)
    raw_usage(science, "extract")
    raw_usage(science, "repair")
    content = generate(tmp_path)
    assert "| 010 | 130 | 130 | 130 | 260 | +100.0% |" in content
    assert "| All planned tasks | 130 | 130 | 130 | 260 | +100.0% |" in content


def test_multiple_completed_turn_events_are_summed(tmp_path):
    directory = trial(tmp_path, "010", "baseline")
    raw_usage(directory, usages=[{"input_tokens": 50, "cached_input_tokens": 10,
                                 "output_tokens": 15, "reasoning_output_tokens": 6}] * 2)
    stage = report.read(directory / "run.json")["stages"][0]
    stage["usage"]["completed_turns"] = 2
    values = report.stage_token_breakdown(directory, stage)
    assert values["total_tokens"] == 130
    assert values["reasoning_output_tokens"] == 12


@pytest.mark.parametrize("baseline_input,extract_status,expected", [
    (0, "completed", "| 010 | 0 | 130 | 130 | 260 | unknown |"),
    (520, "completed", "| 010 | 520 | 130 | 130 | 260 | -50.0% |"),
    (520, "timeout", "| 010 | 520 | unknown | 130 | unknown | unknown |"),
])
def test_token_comparison_edge_cases(tmp_path, baseline_input, extract_status, expected):
    schedule(tmp_path, tasks=("010",))
    baseline = trial(tmp_path, "010", "baseline")
    science = trial(tmp_path, "010", "science", graph=True)
    baseline_record = report.read(baseline / "run.json")
    usage = {"input_tokens": baseline_input, "cached_input_tokens": 0,
             "output_tokens": 0, "reasoning_output_tokens": 0}
    baseline_record["stages"][0]["usage"] = usage
    dump(baseline / "run.json", baseline_record)
    raw_usage(baseline, usages=[usage])
    science_record = report.read(science / "run.json")
    science_record["stages"][0]["status"] = extract_status
    dump(science / "run.json", science_record)
    raw_usage(science, "extract")
    raw_usage(science, "repair")
    content = generate(tmp_path)
    assert expected in content
    assert expected.replace("| 010 |", "| All planned tasks |") in content


def test_missing_reasoning_and_failed_stage_preserve_unknowns(tmp_path):
    directory = trial(tmp_path, "010", "baseline")
    stage = report.read(directory / "run.json")["stages"][0]
    raw_usage(directory, usages=[stage["usage"]])
    values = report.stage_token_breakdown(directory, stage)
    assert values["total_tokens"] == 130
    assert values["reasoning_output_tokens"] is None
    assert values["nonreasoning_output_tokens"] is None
    stage["status"] = "timeout"
    assert all(v is None for v in report.stage_token_breakdown(directory, stage).values())


def test_partial_reasoning_coverage_is_not_summed(tmp_path):
    directory = trial(tmp_path, "010", "baseline")
    stage = report.read(directory / "run.json")["stages"][0]
    raw_usage(directory, usages=[{"input_tokens": 50, "cached_input_tokens": 10, "output_tokens": 15,
                                 "reasoning_output_tokens": 6},
                                {"input_tokens": 50, "cached_input_tokens": 10, "output_tokens": 15}])
    assert report.stage_token_breakdown(directory, stage)["reasoning_output_tokens"] is None


@pytest.mark.parametrize("field", report.TOKENS)
def test_raw_usage_mismatch_fails_before_report_write(tmp_path, field):
    schedule(tmp_path, tasks=("010",))
    directory = trial(tmp_path, "010", "baseline")
    usage = {"input_tokens": 100, "cached_input_tokens": 20, "output_tokens": 30, "reasoning_output_tokens": 12}
    usage[field] += 1
    raw_usage(directory, usages=[usage])
    with pytest.raises(ValueError, match="Raw token usage differs"):
        generate(tmp_path)
    assert not (tmp_path / "report.md").exists()


def test_missing_expected_science_stage_prevents_trial_total(tmp_path):
    schedule(tmp_path, tasks=("010",))
    directory = trial(tmp_path, "010", "science")
    raw_usage(directory)
    content = generate(tmp_path)
    assert "| 010 | science | repair | completed | 100 | 20 | 80 | 30 | 12 | 18 | 130 |" in content
    assert "| 010 | science | trial total | completed | unknown | unknown | unknown | unknown | unknown | unknown | unknown |" in content


def multicall(directory, *, revision=True):
    record = report.read(directory / "run.json")
    stage = record["stages"][0]
    calls = [{"name": name, "status": "completed", "usage": dict(stage["usage"])} for name in
             (["extract_draft", "extract_revision"] if revision else ["extract_draft"])]
    stage["model_calls"] = calls
    stage["usage"] = {field: value * len(calls) for field, value in stage["usage"].items()}
    for call in calls:
        raw_usage(directory, call["name"])
    dump(directory / "run.json", record)
    return stage


@pytest.mark.parametrize("revision", [False, True])
def test_multicall_extraction_and_trial_totals(tmp_path, revision):
    schedule(tmp_path, tasks=("010",))
    baseline = trial(tmp_path, "010", "baseline")
    science = trial(tmp_path, "010", "science", graph=True)
    raw_usage(baseline)
    raw_usage(science)
    stage = multicall(science, revision=revision)
    assert report.stage_token_breakdown(science, stage)["total_tokens"] == (260 if revision else 130)
    content = generate(tmp_path)
    assert "| 010 | science | extract_draft | completed | 100 | 20 | 80 | 30 | 12 | 18 | 130 |" in content
    if revision:
        assert "| 010 | science | extract_revision | completed | 100 | 20 | 80 | 30 | 12 | 18 | 130 |" in content
        assert "| 010 | science | extract total | completed | 200 | 40 | 160 | 60 | 24 | 36 | 260 |" in content
        assert "| 010 | 130 | 260 | 130 | 390 | +200.0% |" in content
        assert "| All planned tasks | 130 | 260 | 130 | 390 | +200.0% |" in content


@pytest.mark.parametrize("missing", ["usage", "log", "timeout"])
def test_multicall_missing_attempt_is_unknown(tmp_path, missing):
    directory = trial(tmp_path, "010", "science", graph=True)
    stage = multicall(directory)
    if missing == "usage":
        stage["model_calls"][1]["usage"] = None
    elif missing == "log":
        (directory / "agent/extract_revision.jsonl").unlink()
    else:
        stage["model_calls"][1]["status"] = "timeout"
    assert all(v is None for v in report.stage_token_breakdown(directory, stage).values())


@pytest.mark.parametrize("calls", [None, {}, [{"name": "extract_revision"}],
                                    [{"name": "extract_draft"}] * 2, [{"name": "../repair"}]])
def test_malformed_multicall_receipts_rejected(tmp_path, calls):
    with pytest.raises(ValueError, match="Malformed"):
        report.stage_token_breakdown(tmp_path, {"name": "extract", "model_calls": calls})


def test_multicall_aggregate_mismatch_detected(tmp_path):
    directory = trial(tmp_path, "010", "science", graph=True)
    stage = multicall(directory)
    stage["usage"]["input_tokens"] += 1
    with pytest.raises(ValueError, match="extraction aggregate"):
        report.stage_token_breakdown(directory, stage)


def test_empty_call_list_and_missing_reasoning_remain_unknown(tmp_path):
    directory = trial(tmp_path, "010", "science", graph=True)
    stage = multicall(directory)
    raw_usage(directory, "extract_revision", usages=[stage["model_calls"][1]["usage"]])
    values = report.stage_token_breakdown(directory, stage)
    assert values["total_tokens"] == 260
    assert values["reasoning_output_tokens"] is None
    stage["model_calls"] = []
    stage["usage"] = {field: 0 for field in report.TOKENS}
    assert all(v is None for v in report.stage_token_breakdown(directory, stage).values())
