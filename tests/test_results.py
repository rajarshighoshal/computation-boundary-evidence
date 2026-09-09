"""Synthetic evidence only; these tests never execute a model or verifier."""

from __future__ import annotations

import importlib.util
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
