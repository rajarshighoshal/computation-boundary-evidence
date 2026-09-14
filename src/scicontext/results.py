"""Recompute paired evaluation results from preserved trial artifacts.

No retry is selected or discarded. ``run_id`` explicitly separates repetitions;
without it each task may have exactly one attempt in each condition. Test scores,
official rewards, and exact private success are deliberately separate quantities.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


DEVELOPMENT_TASKS = {"002", "077"}
PRIVATE_EXPOSURE_TASKS = {"002"}
STATUSES = {"passed", "failed", "error", "skipped"}
TOKEN_FIELDS = ("input_tokens", "cached_input_tokens", "output_tokens")
ARTIFACTS = ("run.json", "verifier/reward.json", "verifier/junit.xml", "baseline-tests.json")
PROVENANCE_FIELDS = (
    "selection_sha256", "dataset_revision", "benchmark_revision", "environment_image",
    "verifier_image", "runner_version", "implementation_revision", "uv_lock_sha256", "prompt_sha256",
)
OWNED_ARTIFACT_SUBTREES = {"agent", "artifacts", "extraction_environment", "verifier"}


class AnalysisError(ValueError):
    """Artifacts cannot support an unambiguous, comparable analysis."""


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected an object in {path}")
    return value


def _count(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _task_id(value: Any) -> str:
    result = str(value)
    return result.zfill(3) if result.isdigit() else result


def _junit(path: Path) -> tuple[dict[str, str] | None, str | None]:
    if not path.exists():
        return None, "missing_candidate_test_data"
    try:
        document = ET.parse(path)
        tests: dict[str, str] = {}
        for case in document.iter("testcase"):
            properties = {p.get("name"): p.get("value") for p in case.findall("properties/property")}
            identity = case.get("nodeid") or properties.get("nodeid") or properties.get("pytest_nodeid")
            if not identity and case.get("classname") and case.get("name"):
                identity = f"{case.get('classname')}::{case.get('name')}"
            if not identity or identity in tests:
                return None, "ambiguous_candidate_test_ids"
            tests[identity] = (
                "error" if case.find("error") is not None else
                "failed" if case.find("failure") is not None else
                "skipped" if case.find("skipped") is not None else "passed"
            )
        for suite in document.iter():
            if suite.tag not in {"testsuite", "testsuites"}:
                continue
            cases = list(suite.iter("testcase"))
            for counter, tag in (("skipped", "skipped"), ("disabled", "skipped"), ("failures", "failure"), ("errors", "error")):
                if counter in suite.attrib:
                    reported = int(suite.attrib[counter])
                    if reported < 0 or reported > sum(case.find(tag) is not None for case in cases):
                        return None, "candidate_suite_status_mismatch"
            if "tests" in suite.attrib and int(suite.attrib["tests"]) != len(cases):
                return None, "candidate_suite_count_mismatch"
        return (tests, None) if tests else (None, "empty_candidate_test_data")
    except (ET.ParseError, OSError, ValueError):
        return None, "invalid_candidate_test_data"


def _test_metrics(
    trial: Path, candidate: dict[str, str] | None, private: dict[str, Any] | None,
    candidate_error: str | None,
) -> tuple[dict[str, Any] | None, str | None]:
    baseline_path = trial / "baseline-tests.json"
    if not baseline_path.exists():
        return None, "missing_baseline_test_data"
    if candidate is None:
        return None, candidate_error
    try:
        items = _read_json(baseline_path)["tests"]
        baseline: dict[str, str] = {}
        if not isinstance(items, list):
            raise ValueError("tests must be an array")
        for item in items:
            identity, status = item["id"], item["status"]
            if not isinstance(identity, str) or not identity or identity in baseline or status not in STATUSES:
                raise ValueError("invalid or duplicate test")
            baseline[identity] = status
    except (KeyError, TypeError, ValueError, OSError):
        return None, "invalid_baseline_test_data"
    if not baseline or baseline.keys() != candidate.keys():
        return None, "unmatched_test_ids"
    if "skipped" in baseline.values():
        return None, "skipped_baseline_tests"
    if private is None or private.get("collected") != len(candidate):
        return None, "candidate_test_count_mismatch"
    if private.get("passed") != sum(s == "passed" for s in candidate.values()):
        return None, "candidate_test_count_mismatch"
    result = {}
    for name, initial in (("fail2pass", {"failed", "error"}), ("pass2pass", {"passed"})):
        ids = [identity for identity, status in baseline.items() if status in initial]
        passed = sum(candidate[identity] == "passed" for identity in ids)
        result[name] = {"passed": passed, "total": len(ids), "rate": passed / len(ids) if ids else None}
    return result, None


def _private_success(
    private: dict[str, Any] | None, candidate: dict[str, str] | None,
    junit_present: bool, candidate_error: str | None,
) -> bool | None:
    if private is None or not _count(private.get("collected")) or not private["collected"]:
        return None
    if not _count(private.get("passed")) or private["passed"] > private["collected"]:
        return None
    for name in ("failed", "errors", "error", "skipped"):
        if name in private and not _count(private[name]):
            return None
    if not isinstance(private.get("return_code"), int) or isinstance(private["return_code"], bool):
        return None
    if private["return_code"] != 0 or private["passed"] != private["collected"]:
        return False
    if any(private.get(name, 0) for name in ("failed", "errors", "error", "skipped")):
        return False
    if junit_present:
        if candidate_error or candidate is None:
            return None
        if len(candidate) != private["collected"]:
            return None
        if any(status != "passed" for status in candidate.values()):
            return False
    return True


def _trial_row(root: Path, path: Path) -> dict[str, Any]:
    trial = path.parent
    try:
        run = _read_json(path)
        for key in ("task_id", "condition", "model", "reasoning_effort", "codex_version", "config", "status"):
            if key not in run:
                raise ValueError(f"missing {key}")
        if run["condition"] not in {"baseline", "science"}:
            raise ValueError("unknown condition")
        if not str(run["task_id"]) or run["task_id"] is None:
            raise ValueError("empty task identity")
        if any(not isinstance(run[key], str) or not run[key] for key in ("model", "reasoning_effort", "codex_version", "status")):
            raise ValueError("invalid model/version/status")
        if not isinstance(run["config"], dict) or not _number(run["config"].get("total_seconds")):
            raise ValueError("invalid total budget")
        if run["config"]["total_seconds"] <= 0:
            raise ValueError("invalid total budget")
        if run.get("run_id") is not None and (not isinstance(run["run_id"], str) or not run["run_id"]):
            raise ValueError("run_id must be a nonempty string")
    except (OSError, ValueError, TypeError) as exc:
        raise AnalysisError(f"Invalid run record {path}: {exc}") from exc

    diagnostics: list[str] = []
    reward_path = trial / "verifier/reward.json"
    reward = None
    if reward_path.exists():
        try:
            reward = _read_json(reward_path)
        except (ValueError, OSError):
            diagnostics.append("invalid_reward_artifact")
    else:
        diagnostics.append("missing_reward_artifact")
    official = reward.get("reward") if reward else None
    if official is not None and not _number(official):
        diagnostics.append("invalid_official_reward")
        official = None
    private = reward.get("private") if reward and isinstance(reward.get("private"), dict) else None
    public = reward.get("public") if reward and isinstance(reward.get("public"), dict) else None
    candidate, candidate_error = _junit(trial / "verifier/junit.xml")
    if candidate_error:
        diagnostics.append(candidate_error)
    matched, matching_error = _test_metrics(trial, candidate, private, candidate_error)
    if matching_error:
        diagnostics.append(matching_error)
    stages = run.get("stages", [])
    if not isinstance(stages, list) or any(not isinstance(stage, dict) for stage in stages):
        diagnostics.append("invalid_stage_data")
        stages = []
    usage: dict[str, int | None] = {}
    for field in TOKEN_FIELDS:
        values = [stage.get("usage", {}).get(field) if isinstance(stage.get("usage"), dict) else None for stage in stages]
        usage[field] = sum(values) if values and all(_count(v) for v in values) else None
    if any(value is None for value in usage.values()):
        diagnostics.append("incomplete_token_usage")
    extraction_status = run.get("extraction_status")
    if run["condition"] == "baseline":
        if extraction_status not in (None, "not_applicable"):
            diagnostics.append("unexpected_baseline_extraction_status")
        extraction_status = "not_applicable"
    elif not isinstance(extraction_status, str) or not extraction_status.strip():
        diagnostics.append("missing_extraction_status" if extraction_status is None else "invalid_extraction_status")
        extraction_status = "unknown"
    graph_coverage = run.get("graph_coverage")
    if graph_coverage is not None and not isinstance(graph_coverage, dict):
        diagnostics.append("invalid_graph_coverage")
        graph_coverage = None
    over_budget = run.get("over_budget_seconds")
    if over_budget is not None and (not _number(over_budget) or over_budget < 0):
        diagnostics.append("invalid_over_budget_seconds")
        over_budget = None
    task_id = _task_id(run["task_id"])
    return {
        "trial_path": trial.relative_to(root).as_posix(),
        "task_id": task_id,
        "run_id": run.get("run_id"),
        "condition": run["condition"],
        "model": run["model"],
        "reasoning_effort": run["reasoning_effort"],
        "codex_version": run["codex_version"],
        "config": run["config"],
        "provenance": {key: run.get(key) for key in PROVENANCE_FIELDS},
        "status": run["status"],
        "started_at": run.get("started_at"),
        "finished_at": run.get("finished_at"),
        "duration_seconds": run.get("duration_seconds"),
        "over_budget_seconds": over_budget,
        "extraction_status": extraction_status,
        "graph_sha256": run.get("graph_sha256"),
        "graph_coverage": graph_coverage,
        "stages": stages,
        "usage": usage,
        "patch_sha256": run.get("patch_sha256"),
        "official_reward": official,
        "public": public,
        "private": private,
        "exact_private_success": _private_success(private, candidate, (trial / "verifier/junit.xml").exists(), candidate_error),
        "matched_test_outcomes": matched,
        "development_exposed": (run.get("development_exposed") is True if run.get("exposure_policy") == "explicit_split_v1"
                                else task_id in DEVELOPMENT_TASKS or run.get("development_exposed") is True),
        "prior_private_test_exposure": (run.get("prior_private_test_exposure") is True if run.get("exposure_policy") == "explicit_split_v1"
                                        else task_id in PRIVATE_EXPOSURE_TASKS),
        "exposure_policy": run.get("exposure_policy", "legacy"),
        "evaluation_partition": run.get("evaluation_partition"),
        "diagnostics": sorted(set(diagnostics)),
        "artifact_sha256": {
            name: hashlib.sha256((trial / name).read_bytes()).hexdigest() if (trial / name).is_file() else None
            for name in ARTIFACTS
        },
    }


def _pairs(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_condition: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_condition[row["task_id"], row["condition"]].append(row)
    for key, attempts in by_condition.items():
        if len(attempts) > 1:
            ids = [row["run_id"] for row in attempts]
            if None in ids or len(ids) != len(set(ids)):
                raise AnalysisError(f"Ambiguous duplicate attempts for {key}; supply distinct explicit run_id values")
    grouped: dict[tuple[str, str | None], dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in rows:
        grouped[row["task_id"], row["run_id"]][row["condition"]] = row
    pairs = []
    for (task_id, run_id), conditions in sorted(grouped.items(), key=lambda item: (item[0][0], item[0][1] or "")):
        baseline, science = conditions.get("baseline"), conditions.get("science")
        if baseline and science:
            for key in ("model", "reasoning_effort", "codex_version", "provenance"):
                if baseline[key] != science[key]:
                    raise AnalysisError(f"Incomparable pair {task_id}/{run_id}: {key} differs")
            baseline_config = {key: value for key, value in baseline["config"].items() if key != "extraction_seconds"}
            science_config = {key: value for key, value in science["config"].items() if key != "extraction_seconds"}
            if baseline_config != science_config:
                raise AnalysisError(f"Incomparable pair {task_id}/{run_id}: config differs outside extraction_seconds")
        left = baseline["exact_private_success"] if baseline else None
        right = science["exact_private_success"] if science else None
        if baseline is None:
            outcome = "missing_baseline"
        elif science is None:
            outcome = "missing_science"
        elif left is None or right is None:
            outcome = "unknown"
        else:
            outcome = {(True, True): "both_success", (True, False): "baseline_only", (False, True): "science_only", (False, False): "both_failure"}[left, right]
        pairs.append({
            "task_id": task_id, "run_id": run_id,
            "baseline_trial": baseline["trial_path"] if baseline else None,
            "science_trial": science["trial_path"] if science else None,
            "baseline_success": left, "science_success": right, "outcome": outcome,
            "development_exposed": any(row and row["development_exposed"] for row in (baseline, science)),
        })
    return pairs


def _metrics(rows: list[dict[str, Any]], pairs: list[dict[str, Any]]) -> dict[str, Any]:
    conditions = {}
    for condition in ("baseline", "science"):
        selected = [row for row in rows if row["condition"] == condition]
        successes = sum(row["exact_private_success"] is True for row in selected)
        failures = sum(row["exact_private_success"] is False for row in selected)
        rewards = [row["official_reward"] for row in selected if row["official_reward"] is not None]
        resources = {}
        for field in (*TOKEN_FIELDS, "duration_seconds", "over_budget_seconds"):
            values = [row["usage"][field] if field in TOKEN_FIELDS else row.get(field) for row in selected]
            observed = [value for value in values if _number(value) and value >= 0]
            resources[field] = {
                "observed_trials": len(observed), "missing_trials": len(selected) - len(observed),
                "observed_total": sum(observed) if observed else None,
                "observed_mean": sum(observed) / len(observed) if observed else None,
            }
        stage_counts: dict[str, Counter] = defaultdict(Counter)
        for row in selected:
            for stage in row["stages"]:
                stage_counts[str(stage.get("name", "unknown"))][str(stage.get("status", "unknown"))] += 1
        conditions[condition] = {
            "attempts": len(selected), "unique_tasks": len({row["task_id"] for row in selected}),
            "exact_private_successes": successes, "exact_private_failures": failures,
            "exact_private_unknown": len(selected) - successes - failures,
            "observed_exact_private_success_rate": successes / (successes + failures) if successes + failures else None,
            "success_fraction_all_attempts": successes / len(selected) if selected else None,
            "official_reward_observations": len(rewards), "official_reward_missing": len(selected) - len(rewards),
            "mean_official_reward_observed": sum(rewards) / len(rewards) if rewards else None,
            "run_status_counts": dict(sorted(Counter(row["status"] for row in selected).items())),
            "extraction_status_counts": dict(sorted(Counter(row["extraction_status"] for row in selected).items())),
            "resources": resources,
            "stage_status_counts": {name: dict(sorted(counts.items())) for name, counts in sorted(stage_counts.items())},
        }
    counts = {name: sum(pair["outcome"] == name for pair in pairs) for name in (
        "both_success", "baseline_only", "science_only", "both_failure", "unknown", "missing_baseline", "missing_science",
    )}
    known = sum(counts[name] for name in ("both_success", "baseline_only", "science_only", "both_failure"))
    return {
        "conditions": conditions, "pair_outcome_counts": counts, "observed_pairs": known,
        "observed_paired_success_delta_percentage_points": 100 * (counts["science_only"] - counts["baseline_only"]) / known if known else None,
    }


def summarize_runs(root: Path) -> dict[str, Any]:
    """Read all ``run.json`` trials below root, retaining incomplete outcomes.

    Invalid trial identity or incompatible paired configurations raise AnalysisError.
    Missing/malformed verifier artifacts remain explicit unknowns. No significance
    tests are performed. Observed rates always report their known/missing counts.
    """
    root = Path(root).resolve()
    if not root.is_dir():
        raise AnalysisError(f"Trial root is not a directory: {root}")
    receipts = []
    for directory, subdirectories, files in os.walk(root, followlinks=False):
        # Agent-controlled scratch and verifier artifacts may contain arbitrary
        # run.json files. They are never experiment trial receipts. Prune these
        # trees before descending, while retaining arbitrary nested job layouts.
        subdirectories[:] = sorted(name for name in subdirectories if name not in OWNED_ARTIFACT_SUBTREES)
        if "run.json" in files:
            receipts.append(Path(directory) / "run.json")
    rows = [_trial_row(root, path) for path in sorted(receipts)]
    pairs = _pairs(rows)
    untouched_rows = [row for row in rows if not row["development_exposed"]]
    untouched_pairs = [pair for pair in pairs if not pair["development_exposed"]]
    return {
        "schema_version": "1.0", "task_ids": sorted({row["task_id"] for row in rows}),
        "exposure": {"development_tasks": sorted((DEVELOPMENT_TASKS if any(r["exposure_policy"] == "legacy" for r in rows) else set()) |
                       {row["task_id"] for row in rows if row["development_exposed"]}),
                     "prior_private_test_exposure": sorted((PRIVATE_EXPOSURE_TASKS if any(r["exposure_policy"] == "legacy" for r in rows) else set()) |
                       {row["task_id"] for row in rows if row["prior_private_test_exposure"]})},
        "trials": rows, "pairs": pairs,
        "metrics": {"all": _metrics(rows, pairs), "untouched": _metrics(untouched_rows, untouched_pairs)},
    }


def write_summary(root: Path, output: Path) -> dict[str, Any]:
    """Write canonical summary.json and a flat, lossless-for-scalars trials.csv."""
    summary = summarize_runs(root)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    (output / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    fields = ["trial_path", "task_id", "run_id", "condition", "status", "duration_seconds", "over_budget_seconds",
              "extraction_status", "graph_sha256", "graph_coverage", "official_reward", "exact_private_success",
              "development_exposed", "prior_private_test_exposure", *TOKEN_FIELDS, *PROVENANCE_FIELDS]
    with (output / "trials.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for trial in summary["trials"]:
            flat = {key: trial["usage"][key] if key in TOKEN_FIELDS else trial["provenance"][key] if key in PROVENANCE_FIELDS else trial[key] for key in fields}
            # Nested coverage and prompt-bundle hashes remain JSON, not Python repr.
            writer.writerow({key: json.dumps(value, sort_keys=True, allow_nan=False) if isinstance(value, (dict, list)) else value for key, value in flat.items()})
    return summary
