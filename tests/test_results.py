"""Synthetic evidence only; these tests never execute a model or verifier."""

from __future__ import annotations

import importlib.util
import csv
import json
import subprocess
import sys
from pathlib import Path

import pytest

from scicontext.results import AnalysisError, summarize_runs, write_summary


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/recompute_results.py"
spec = importlib.util.spec_from_file_location("independent_recompute", SCRIPT)
independent = importlib.util.module_from_spec(spec)
spec.loader.exec_module(independent)


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def trial(root, task="010", condition="baseline", *, name=None, run_id=None, success=True, reward_value=None, **changes):
    directory = root / (name or f"{task}-{condition}")
    record = {
        "schema_version": "1.0", "task_id": task, "condition": condition,
        "model": "gpt-6-astra", "reasoning_effort": "high", "codex_version": "0.153.4",
        "config": {"total_seconds": 1800, "extraction_seconds": 0 if condition == "baseline" else 360},
        "started_at": "2026-09-10T00:00:00Z", "finished_at": "2026-09-10T00:10:00Z",
        "duration_seconds": 600, "status": "completed", "patch_sha256": "0123",
        "stages": [{"name": "repair", "status": "completed", "duration_seconds": 600, "usage": {"input_tokens": 100, "cached_input_tokens": 40, "output_tokens": 20}}],
    }
    if run_id is not None:
        record["run_id"] = run_id
    record.update(changes)
    dump(directory / "run.json", record)
    if success is not None:
        reward = {
            "reward": reward_value if reward_value is not None else float(success),
            "public": {"passed": 4, "collected": 4, "return_code": 0},
            "private": {"passed": 2 if success else 1, "collected": 2, "failed": 0 if success else 1, "return_code": 0 if success else 1},
        }
        dump(directory / "verifier/reward.json", reward)
    return directory


def junit(directory, *, first="passed", second="passed", ids=True):
    def case(name, status):
        attribute = f'nodeid="tests/test_science.py::{name}"' if ids else f'classname="tests.test_science" name="{name}"'
        element = {"passed": "", "failed": "<failure/>", "error": "<error/>", "skipped": "<skipped/>"}[status]
        return f"<testcase {attribute}>{element}</testcase>"
    path = directory / "verifier/junit.xml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"<testsuites><testsuite>{case('test_a', first)}{case('test_b', second)}</testsuite></testsuites>", encoding="utf-8")


def original_tests(directory, first="failed", second="passed", prefix="tests/test_science.py"):
    dump(directory / "baseline-tests.json", {"tests": [{"id": f"{prefix}::test_a", "status": first}, {"id": f"{prefix}::test_b", "status": second}]})


def assert_independent(root):
    summary = summarize_runs(root)
    assert json.dumps(summary, sort_keys=True) == json.dumps(independent.recompute(root), sort_keys=True)
    return summary


def test_retry_wait_and_work_time_are_preserved_separately(tmp_path):
    trial(tmp_path, duration_seconds=662, work_seconds=600, provider_retry_wait_seconds=62,
          time_budget_basis="work_time_excluding_provider_retry_backoff")
    result = assert_independent(tmp_path)
    row = result["trials"][0]
    assert (row["duration_seconds"], row["work_seconds"], row["provider_retry_wait_seconds"]) == (662, 600, 62)
    output = tmp_path / "summary"
    write_summary(tmp_path, output)
    with (output / "trials.csv").open() as stream:
        exported = next(csv.DictReader(stream))
    assert exported["work_seconds"] == "600"
    assert exported["provider_retry_wait_seconds"] == "62"


def test_pairs_with_different_wait_budget_policies_are_not_comparable(tmp_path):
    trial(tmp_path)
    trial(tmp_path, condition="science", time_budget_basis="work_time_excluding_provider_retry_backoff")
    with pytest.raises(AnalysisError, match="time_budget_basis"):
        summarize_runs(tmp_path)
    with pytest.raises(ValueError, match="time_budget_basis"):
        independent.recompute(tmp_path)


def test_explicit_development_exposure_is_not_reported_as_untouched(tmp_path):
    trial(tmp_path, task="091", development_exposed=True)
    trial(tmp_path, task="091", condition="science", development_exposed=True)
    summary = assert_independent(tmp_path)
    assert all(row["development_exposed"] for row in summary["trials"])
    assert summary["pairs"][0]["development_exposed"] is True
    assert "091" in summary["exposure"]["development_tasks"]
    assert summary["metrics"]["untouched"]["conditions"]["baseline"]["attempts"] == 0


def test_new_split_exposure_is_explicit_not_hardcoded(tmp_path):
    trial(tmp_path, task="001", exposure_policy="explicit_split_v1", development_exposed=True,
          prior_private_test_exposure=True, evaluation_partition="development")
    trial(tmp_path, task="002", exposure_policy="explicit_split_v1", development_exposed=False,
          prior_private_test_exposure=False, evaluation_partition="locked_evaluation")
    result = assert_independent(tmp_path)
    assert result["exposure"] == {"development_tasks": ["001"], "prior_private_test_exposure": ["001"]}
    assert [r["development_exposed"] for r in result["trials"]] == [True, False]


def test_official_reward_and_exact_private_success_are_separate(tmp_path):
    trial(tmp_path, success=False, reward_value=1.0)
    trial(tmp_path, condition="science", success=True, reward_value=0.75)
    summary = assert_independent(tmp_path)
    rows = summary["trials"]
    assert rows[0]["official_reward"] == 1.0
    assert rows[0]["exact_private_success"] is False
    assert rows[1]["official_reward"] == 0.75
    assert rows[1]["exact_private_success"] is True
    assert summary["pairs"][0]["outcome"] == "science_only"
    assert summary["metrics"]["all"]["observed_paired_success_delta_percentage_points"] == 100
    assert rows[0]["matched_test_outcomes"] is None


def test_missing_and_infrastructure_attempts_remain_visible(tmp_path):
    trial(tmp_path, success=True)
    trial(tmp_path, condition="science", success=None, status="infrastructure_error", stages=[])
    trial(tmp_path, task="011", success=False)
    summary = assert_independent(tmp_path)
    assert len(summary["trials"]) == 3
    assert [pair["outcome"] for pair in summary["pairs"]] == ["unknown", "missing_science"]
    science = summary["metrics"]["all"]["conditions"]["science"]
    assert science["attempts"] == 1
    assert science["exact_private_unknown"] == science["official_reward_missing"] == 1
    assert science["run_status_counts"] == {"infrastructure_error": 1}
    assert summary["trials"][1]["usage"]["input_tokens"] is None


def test_invalid_reward_is_preserved_as_unknown_with_receipt_hash(tmp_path):
    directory = trial(tmp_path)
    (directory / "verifier/reward.json").write_text("not-json", encoding="utf-8")
    row = assert_independent(tmp_path)["trials"][0]
    assert row["official_reward"] is row["exact_private_success"] is None
    assert "invalid_reward_artifact" in row["diagnostics"]
    assert len(row["artifact_sha256"]["verifier/reward.json"]) == 64


def test_invalid_trial_cannot_silently_disappear(tmp_path):
    dump(tmp_path / "bad/run.json", {"condition": "science"})
    with pytest.raises(AnalysisError, match="Invalid run"):
        summarize_runs(tmp_path)
    with pytest.raises(ValueError, match="Invalid run"):
        independent.recompute(tmp_path)


@pytest.mark.parametrize("private", [
    {"passed": 0, "collected": 0, "return_code": 0},
    {"passed": 1, "collected": 2},
    {"passed": 3, "collected": 2, "return_code": 0},
    {"passed": True, "collected": 2, "return_code": 0},
    {"passed": 2, "collected": 2, "return_code": False},
])
def test_missing_invalid_or_zero_private_counts_are_unknown(tmp_path, private):
    directory = trial(tmp_path)
    dump(directory / "verifier/reward.json", {"reward": 1.0, "private": private})
    assert assert_independent(tmp_path)["trials"][0]["exact_private_success"] is None


@pytest.mark.parametrize("skip_source", ["junit", "reward"])
def test_skips_cannot_be_exact_success(tmp_path, skip_source):
    directory = trial(tmp_path)
    if skip_source == "junit":
        junit(directory, second="skipped")
    else:
        path = directory / "verifier/reward.json"
        value = json.loads(path.read_text())
        value["private"]["skipped"] = 1
        dump(path, value)
    assert assert_independent(tmp_path)["trials"][0]["exact_private_success"] is False


def test_malformed_private_junit_prevents_false_success(tmp_path):
    directory = trial(tmp_path)
    (directory / "verifier/junit.xml").write_text("<broken", encoding="utf-8")
    result = assert_independent(tmp_path)["trials"][0]
    assert result["exact_private_success"] is None
    assert "invalid_candidate_test_data" in result["diagnostics"]


def test_junit_suite_skip_or_count_metadata_prevents_false_success(tmp_path):
    directory = trial(tmp_path)
    junit(directory)
    path = directory / "verifier/junit.xml"
    raw = path.read_text()
    path.write_text(raw.replace("<testsuite>", '<testsuite skipped="1">'))
    row = assert_independent(tmp_path)["trials"][0]
    assert row["exact_private_success"] is None
    assert "candidate_suite_status_mismatch" in row["diagnostics"]
    path.write_text(raw.replace("<testsuite>", '<testsuite tests="3">'))
    row = assert_independent(tmp_path)["trials"][0]
    assert row["exact_private_success"] is None
    assert "candidate_suite_count_mismatch" in row["diagnostics"]


def test_fail2pass_pass2pass_require_matching_identities(tmp_path):
    directory = trial(tmp_path)
    junit(directory)
    original_tests(directory)
    outcomes = assert_independent(tmp_path)["trials"][0]["matched_test_outcomes"]
    assert outcomes == {"fail2pass": {"passed": 1, "total": 1, "rate": 1.0}, "pass2pass": {"passed": 1, "total": 1, "rate": 1.0}}
    original_tests(directory, prefix="some_other_path")
    result = assert_independent(tmp_path)["trials"][0]
    assert result["matched_test_outcomes"] is None
    assert "unmatched_test_ids" in result["diagnostics"]


def test_matching_classname_id_and_failing_candidate(tmp_path):
    directory = trial(tmp_path, success=False)
    junit(directory, first="failed", ids=False)
    original_tests(directory, prefix="tests.test_science")
    outcomes = assert_independent(tmp_path)["trials"][0]["matched_test_outcomes"]
    assert outcomes["fail2pass"] == {"passed": 0, "total": 1, "rate": 0.0}
    assert outcomes["pass2pass"]["rate"] == 1.0


def test_skipped_original_or_disagreeing_count_disables_matched_metrics(tmp_path):
    directory = trial(tmp_path)
    junit(directory)
    original_tests(directory, first="skipped")
    assert assert_independent(tmp_path)["trials"][0]["matched_test_outcomes"] is None
    original_tests(directory)
    junit(directory, second="skipped")
    result = assert_independent(tmp_path)["trials"][0]
    assert result["matched_test_outcomes"] is None
    assert "candidate_test_count_mismatch" in result["diagnostics"]


@pytest.mark.parametrize("change", [
    {"model": "different-model"}, {"reasoning_effort": "low"}, {"codex_version": "old"},
    {"selection_sha256": "different"}, {"config": {"total_seconds": 2000, "extraction_seconds": 360}},
    {"config": {"total_seconds": 1800, "extraction_seconds": 360, "extra_tokens": 10}},
])
def test_incomparable_pairs_are_rejected(tmp_path, change):
    trial(tmp_path)
    trial(tmp_path, condition="science", **change)
    with pytest.raises(AnalysisError, match="Incomparable"):
        summarize_runs(tmp_path)
    with pytest.raises(ValueError, match="Incomparable"):
        independent.recompute(tmp_path)


def test_duplicate_attempts_rejected_without_explicit_run_identity(tmp_path):
    trial(tmp_path)
    trial(tmp_path, name="retry", success=False)
    with pytest.raises(AnalysisError, match="Ambiguous duplicate"):
        summarize_runs(tmp_path)
    with pytest.raises(ValueError, match="Ambiguous"):
        independent.recompute(tmp_path)


def test_explicit_repetitions_are_preserved_and_never_best_selected(tmp_path):
    trial(tmp_path, name="baseline-a", run_id="a", success=False)
    trial(tmp_path, name="baseline-b", run_id="b", success=True)
    trial(tmp_path, name="science-a", run_id="a", condition="science", success=True)
    summary = assert_independent(tmp_path)
    assert len(summary["trials"]) == 3
    assert [pair["outcome"] for pair in summary["pairs"]] == ["science_only", "missing_science"]


def test_development_exposure_and_token_accounting(tmp_path):
    trial(tmp_path, task="002")
    trial(tmp_path, task="077")
    trial(tmp_path, task="078", condition="science", stages=[
        {"name": "extract", "usage": {"input_tokens": 100, "cached_input_tokens": 30, "output_tokens": 20}},
        {"name": "repair", "usage": {"input_tokens": 200, "cached_input_tokens": 50, "output_tokens": 40}},
    ])
    summary = assert_independent(tmp_path)
    assert [row["development_exposed"] for row in summary["trials"]] == [True, True, False]
    assert [row["prior_private_test_exposure"] for row in summary["trials"]] == [True, False, False]
    assert summary["trials"][-1]["usage"] == {"input_tokens": 300, "cached_input_tokens": 80, "output_tokens": 60}
    assert summary["metrics"]["untouched"]["conditions"]["baseline"]["attempts"] == 0
    resources = summary["metrics"]["all"]["conditions"]["science"]["resources"]
    assert resources["input_tokens"] == {"observed_trials": 1, "missing_trials": 0, "observed_total": 300, "observed_mean": 300.0}


def test_serialization_and_independent_cli_detect_tampered_summary_and_raw_artifacts(tmp_path):
    run_root, output = tmp_path / "runs", tmp_path / "analysis"
    directory = trial(run_root)
    expected = write_summary(run_root, output)
    command = [sys.executable, str(SCRIPT), str(run_root), "--verify", str(output / "summary.json")]
    assert subprocess.run(command, capture_output=True).returncode == 0
    assert (output / "trials.csv").read_text().splitlines()[0].startswith("trial_path,task_id")
    expected["metrics"]["all"]["conditions"]["baseline"]["exact_private_successes"] = 999
    dump(output / "summary.json", expected)
    assert subprocess.run(command, capture_output=True).returncode == 1
    write_summary(run_root, output)
    dump(directory / "verifier/reward.json", {"reward": 0.0})
    assert subprocess.run(command, capture_output=True).returncode == 1


def test_empty_root_is_an_explicit_zero_observation_report(tmp_path):
    summary = assert_independent(tmp_path)
    assert summary["trials"] == summary["pairs"] == []
    assert summary["metrics"]["all"]["observed_paired_success_delta_percentage_points"] is None


def test_extraction_failures_and_unknowns_survive_summary(tmp_path):
    trial(tmp_path, task="010")
    trial(tmp_path, task="010", condition="science", extraction_status="no_valid_graph", graph_coverage=None)
    trial(tmp_path, task="011", condition="science", extraction_status="timeout")
    trial(tmp_path, task="012", condition="science")
    coverage = {"claims": 4, "dimension_resolved": 2, "scale_resolved": 0, "unresolved": {"unsupported_language": 1}}
    trial(tmp_path, task="013", condition="science", extraction_status="usable_graph", graph_sha256="a" * 64, graph_coverage=coverage)
    summary = assert_independent(tmp_path)
    rows = {(row["task_id"], row["condition"]): row for row in summary["trials"]}
    assert rows["010", "baseline"]["extraction_status"] == "not_applicable"
    assert rows["010", "science"]["graph_coverage"] is None
    assert rows["012", "science"]["extraction_status"] == "unknown"
    assert rows["012", "science"]["graph_coverage"] is None
    assert rows["013", "science"]["graph_coverage"] == coverage
    assert "shape_resolved" not in rows["013", "science"]["graph_coverage"]
    assert rows["013", "science"]["graph_sha256"] == "a" * 64
    conditions = summary["metrics"]["all"]["conditions"]
    assert conditions["baseline"]["extraction_status_counts"] == {"not_applicable": 1}
    assert conditions["science"]["extraction_status_counts"] == {"no_valid_graph": 1, "timeout": 1, "unknown": 1, "usable_graph": 1}


def test_empty_and_absent_graph_coverage_are_distinct(tmp_path):
    trial(tmp_path, task="010", condition="science", graph_coverage={})
    trial(tmp_path, task="011", condition="science")
    trial(tmp_path, task="012", condition="science", graph_coverage={"claims": 0})
    rows = assert_independent(tmp_path)["trials"]
    assert [row["graph_coverage"] for row in rows] == [{}, None, {"claims": 0}]


def test_over_budget_observations_do_not_imply_missing_values_are_zero(tmp_path):
    trial(tmp_path, task="010", over_budget_seconds=0)
    trial(tmp_path, task="011", over_budget_seconds=1.75)
    trial(tmp_path, task="012")
    summary = assert_independent(tmp_path)
    assert [row["over_budget_seconds"] for row in summary["trials"]] == [0, 1.75, None]
    stats = summary["metrics"]["all"]["conditions"]["baseline"]["resources"]["over_budget_seconds"]
    assert stats == {"observed_trials": 2, "missing_trials": 1, "observed_total": 1.75, "observed_mean": 0.875}


@pytest.mark.parametrize("changes,diagnostic,field", [
    ({"extraction_status": []}, "invalid_extraction_status", "extraction_status"),
    ({"extraction_status": " "}, "invalid_extraction_status", "extraction_status"),
    ({"graph_coverage": []}, "invalid_graph_coverage", "graph_coverage"),
    ({"over_budget_seconds": -1}, "invalid_over_budget_seconds", "over_budget_seconds"),
    ({"over_budget_seconds": True}, "invalid_over_budget_seconds", "over_budget_seconds"),
    ({"over_budget_seconds": float("nan")}, "invalid_over_budget_seconds", "over_budget_seconds"),
])
def test_invalid_extraction_metadata_is_explicitly_unknown(tmp_path, changes, diagnostic, field):
    trial(tmp_path, condition="science", **changes)
    row = assert_independent(tmp_path)["trials"][0]
    assert diagnostic in row["diagnostics"]
    assert row[field] == ("unknown" if field == "extraction_status" else None)


def test_baseline_never_counts_as_an_extraction_attempt(tmp_path):
    trial(tmp_path, extraction_status="usable_graph")
    summary = assert_independent(tmp_path)
    assert summary["trials"][0]["extraction_status"] == "not_applicable"
    assert "unexpected_baseline_extraction_status" in summary["trials"][0]["diagnostics"]
    assert summary["metrics"]["all"]["conditions"]["baseline"]["extraction_status_counts"] == {"not_applicable": 1}


@pytest.mark.parametrize("field", ["implementation_revision", "uv_lock_sha256", "prompt_sha256"])
def test_changed_implementation_dependency_or_prompt_provenance_rejects_pair(tmp_path, field):
    trial(tmp_path, **{field: "a" * 64})
    trial(tmp_path, condition="science", **{field: "b" * 64})
    with pytest.raises(AnalysisError, match="Incomparable"):
        summarize_runs(tmp_path)
    with pytest.raises(ValueError, match="Incomparable"):
        independent.recompute(tmp_path)


def test_new_provenance_and_nested_coverage_round_trip_csv_and_audit(tmp_path):
    root, output = tmp_path / "runs", tmp_path / "summary"
    provenance = {"implementation_revision": "c" * 40, "uv_lock_sha256": "d" * 64,
                  "prompt_sha256": {"extract": "e" * 64, "repair": "f" * 64}}
    coverage = {"claims": 3, "alignment": {"match": 1, "unknown": 2}}
    trial(root, **provenance)
    trial(root, condition="science", extraction_status="usable_graph", graph_coverage=coverage, graph_sha256="1" * 64, over_budget_seconds=0.1, **provenance)
    summary = write_summary(root, output)
    assert summary == independent.recompute(root)
    assert {key: summary["trials"][1]["provenance"][key] for key in provenance} == provenance
    with (output / "trials.csv").open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert rows[0]["graph_coverage"] == ""
    assert json.loads(rows[1]["graph_coverage"]) == coverage
    assert json.loads(rows[1]["prompt_sha256"]) == provenance["prompt_sha256"]
    assert rows[1]["implementation_revision"] == provenance["implementation_revision"]
    assert rows[1]["over_budget_seconds"] == "0.1"
    command = [sys.executable, str(SCRIPT), str(root), "--verify", str(output / "summary.json")]
    assert subprocess.run(command, capture_output=True).returncode == 0
    summary["trials"][1]["graph_coverage"]["claims"] = 99
    dump(output / "summary.json", summary)
    assert subprocess.run(command, capture_output=True).returncode == 1


@pytest.mark.parametrize("reserved", ["agent", "artifacts", "extraction_environment", "verifier"])
def test_agent_owned_run_filenames_are_not_trial_receipts(tmp_path, reserved):
    directory = trial(tmp_path, name="jobs/batch-01/task-010/baseline")
    trial(tmp_path, name="jobs/batch-01/task-010/science", condition="science")
    baseline = assert_independent(tmp_path)
    fake = directory / reserved / "extract-scratch/nested/run.json"
    fake.parent.mkdir(parents=True, exist_ok=True)
    fake.write_text("malformed untrusted probe content", encoding="utf-8")
    # Also exclude an artifact tree alongside jobs rather than only under trials.
    dump(tmp_path / reserved / "other/run.json", {"condition": "science"})
    summary = assert_independent(tmp_path)
    assert summary == baseline
    assert len(summary["trials"]) == 2
    assert summary["pairs"][0]["outcome"] == "both_success"


def test_invalid_receipt_in_nested_job_still_fails_closed(tmp_path):
    dump(tmp_path / "jobs/batch-01/task-010/science/run.json", {"condition": "science"})
    with pytest.raises(AnalysisError, match="Invalid run"):
        summarize_runs(tmp_path)
    with pytest.raises(ValueError, match="Invalid run"):
        independent.recompute(tmp_path)
