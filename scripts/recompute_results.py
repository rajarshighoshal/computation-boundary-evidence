#!/usr/bin/env python3
"""Independent, stdlib-only audit of results against immutable run receipts.

Usage: python scripts/recompute_results.py RUN_ROOT --verify SUMMARY_JSON
       python scripts/recompute_results.py RUN_ROOT --output SUMMARY_JSON

This intentionally does not import scicontext or reuse its aggregation functions.
It reconstructs each row and paired statistic before comparing the entire report.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


FILES = ("run.json", "verifier/reward.json", "verifier/junit.xml", "baseline-tests.json")
TOKENS = ("input_tokens", "cached_input_tokens", "output_tokens")
PROVENANCE = ("selection_sha256", "dataset_revision", "benchmark_revision", "environment_image", "verifier_image", "runner_version")
OUTCOMES = ("both_success", "baseline_only", "science_only", "both_failure", "unknown", "missing_baseline", "missing_science")


def object_from(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    if type(data) is not dict:
        raise ValueError(f"Not a JSON object: {path}")
    return data


def count(x):
    return type(x) is int and x >= 0


def finite(x):
    return type(x) in (int, float) and math.isfinite(x)


def xml_statuses(path):
    if not path.exists():
        return None, "missing_candidate_test_data"
    statuses = {}
    try:
        tree = ET.parse(path)
        for case in tree.getroot().iter("testcase"):
            props = {prop.attrib.get("name"): prop.attrib.get("value") for prop in case.findall("./properties/property")}
            identity = case.get("nodeid") or props.get("nodeid") or props.get("pytest_nodeid")
            if not identity and case.get("classname") and case.get("name"):
                identity = case.get("classname") + "::" + case.get("name")
            if not identity or identity in statuses:
                return None, "ambiguous_candidate_test_ids"
            tag_names = [child.tag for child in case]
            status = "passed"
            for tag, result in (("skipped", "skipped"), ("failure", "failed"), ("error", "error")):
                if tag in tag_names:
                    status = result
            statuses[identity] = status
        for region in tree.getroot().iter():
            if region.tag in ("testsuite", "testsuites"):
                cases = list(region.iter("testcase"))
                checks = {"skipped": "skipped", "disabled": "skipped", "failures": "failure", "errors": "error"}
                for attr, tag in checks.items():
                    if attr in region.attrib:
                        declared = int(region.attrib[attr])
                        observed = len([case for case in cases if case.find(tag) is not None])
                        if declared < 0 or declared > observed:
                            return None, "candidate_suite_status_mismatch"
                if "tests" in region.attrib and int(region.attrib["tests"]) != len(cases):
                    return None, "candidate_suite_count_mismatch"
    except (ET.ParseError, OSError, ValueError):
        return None, "invalid_candidate_test_data"
    return (statuses, None) if statuses else (None, "empty_candidate_test_data")


def exact_success(private, statuses, xml_exists, error):
    if private is None or not count(private.get("collected")) or private["collected"] == 0:
        return None
    if not count(private.get("passed")) or private["passed"] > private["collected"]:
        return None
    if any(key in private and not count(private[key]) for key in ("failed", "errors", "error", "skipped")):
        return None
    if type(private.get("return_code")) is not int:
        return None
    if private["return_code"] != 0 or private["passed"] < private["collected"]:
        return False
    if any(private.get(key, 0) > 0 for key in ("failed", "errors", "error", "skipped")):
        return False
    if xml_exists:
        if error or statuses is None:
            return None
        if len(statuses) != private["collected"]:
            return None
        if set(statuses.values()) != {"passed"}:
            return False
    return True


def per_test(directory, statuses, private, xml_error):
    baseline_file = directory / "baseline-tests.json"
    if not baseline_file.exists():
        return None, "missing_baseline_test_data"
    if statuses is None:
        return None, xml_error
    try:
        records = object_from(baseline_file)["tests"]
        if type(records) is not list:
            raise ValueError("Invalid records")
        original = {}
        for record in records:
            identity, status = record["id"], record["status"]
            if type(identity) is not str or not identity or identity in original or status not in {"passed", "failed", "error", "skipped"}:
                raise ValueError("Invalid records")
            original[identity] = status
    except (KeyError, TypeError, ValueError, OSError):
        return None, "invalid_baseline_test_data"
    if not original or set(original) != set(statuses):
        return None, "unmatched_test_ids"
    if any(status == "skipped" for status in original.values()):
        return None, "skipped_baseline_tests"
    if private is None or private.get("collected") != len(statuses) or private.get("passed") != list(statuses.values()).count("passed"):
        return None, "candidate_test_count_mismatch"
    metrics = {}
    for name, accepted in (("fail2pass", ("failed", "error")), ("pass2pass", ("passed",))):
        eligible = [identity for identity in original if original[identity] in accepted]
        passed = len([identity for identity in eligible if statuses[identity] == "passed"])
        metrics[name] = {"passed": passed, "total": len(eligible), "rate": passed / len(eligible) if eligible else None}
    return metrics, None


def reconstruct_row(root, receipt):
    data, directory = object_from(receipt), receipt.parent
    required = {"task_id", "condition", "model", "reasoning_effort", "codex_version", "config", "status"}
    if not required.issubset(data) or data["condition"] not in ("baseline", "science"):
        raise ValueError(f"Invalid run record {receipt}")
    if data["task_id"] is None or not str(data["task_id"]) or any(type(data[key]) is not str or not data[key] for key in ("model", "reasoning_effort", "codex_version", "status")):
        raise ValueError(f"Invalid identity, model/version/status {receipt}")
    if type(data["config"]) is not dict or not finite(data["config"].get("total_seconds")) or data["config"]["total_seconds"] <= 0:
        raise ValueError(f"Invalid run budget {receipt}")
    if data.get("run_id") is not None and (type(data["run_id"]) is not str or not data["run_id"]):
        raise ValueError(f"Invalid run identity {receipt}")
    problems, reward = set(), None
    reward_file = directory / FILES[1]
    if reward_file.exists():
        try:
            reward = object_from(reward_file)
        except (ValueError, OSError):
            problems.add("invalid_reward_artifact")
    else:
        problems.add("missing_reward_artifact")
    value = reward.get("reward") if reward else None
    if value is not None and not finite(value):
        value = None
        problems.add("invalid_official_reward")
    private = reward.get("private") if reward and type(reward.get("private")) is dict else None
    public = reward.get("public") if reward and type(reward.get("public")) is dict else None
    statuses, xml_error = xml_statuses(directory / FILES[2])
    if xml_error:
        problems.add(xml_error)
    matched, matched_error = per_test(directory, statuses, private, xml_error)
    if matched_error:
        problems.add(matched_error)
    stages = data.get("stages", [])
    if type(stages) is not list or any(type(stage) is not dict for stage in stages):
        stages = []
        problems.add("invalid_stage_data")
    usage = {}
    for token in TOKENS:
        observations = []
        for stage in stages:
            record = stage.get("usage")
            observations.append(record.get(token) if type(record) is dict else None)
        usage[token] = sum(observations) if observations and all(count(item) for item in observations) else None
    if None in usage.values():
        problems.add("incomplete_token_usage")
    task = str(data["task_id"])
    if task.isdigit():
        task = task.zfill(3)
    row = {key: data.get(key) for key in ("run_id", "condition", "model", "reasoning_effort", "codex_version", "config", "status", "started_at", "finished_at", "duration_seconds", "patch_sha256")}
    row.update({
        "trial_path": directory.relative_to(root).as_posix(), "task_id": task,
        "provenance": {key: data.get(key) for key in PROVENANCE}, "stages": stages, "usage": usage,
        "official_reward": value, "public": public, "private": private,
        "exact_private_success": exact_success(private, statuses, (directory / FILES[2]).exists(), xml_error),
        "matched_test_outcomes": matched, "development_exposed": task in ("002", "077"),
        "prior_private_test_exposure": task == "002", "diagnostics": sorted(problems),
        "artifact_sha256": {file: hashlib.sha256((directory / file).read_bytes()).hexdigest() if (directory / file).is_file() else None for file in FILES},
    })
    return row


def reconstruct_pairs(rows):
    index, seen = {}, {}
    for row in rows:
        condition_key = (row["task_id"], row["condition"])
        identities = seen.setdefault(condition_key, [])
        identities.append(row["run_id"])
        if len(identities) > 1 and (None in identities or len(set(identities)) != len(identities)):
            raise ValueError(f"Ambiguous attempts: {condition_key}")
        index.setdefault((row["task_id"], row["run_id"]), {})[row["condition"]] = row
    pairs = []
    for task, repetition in sorted(index, key=lambda key: (key[0], key[1] or "")):
        item = index[(task, repetition)]
        left, right = item.get("baseline"), item.get("science")
        if left and right:
            for key in ("model", "reasoning_effort", "codex_version", "provenance"):
                if left[key] != right[key]:
                    raise ValueError(f"Incomparable {task}: {key}")
            settings = [{key: value for key, value in record["config"].items() if key != "extraction_seconds"} for record in (left, right)]
            if settings[0] != settings[1]:
                raise ValueError(f"Incomparable {task}: config")
        l_success, r_success = (left["exact_private_success"] if left else None), (right["exact_private_success"] if right else None)
        if left is None:
            outcome = "missing_baseline"
        elif right is None:
            outcome = "missing_science"
        elif l_success is None or r_success is None:
            outcome = "unknown"
        elif l_success and r_success:
            outcome = "both_success"
        elif l_success:
            outcome = "baseline_only"
        elif r_success:
            outcome = "science_only"
        else:
            outcome = "both_failure"
        pairs.append({"task_id": task, "run_id": repetition, "baseline_trial": left["trial_path"] if left else None, "science_trial": right["trial_path"] if right else None, "baseline_success": l_success, "science_success": r_success, "outcome": outcome, "development_exposed": task in ("002", "077")})
    return pairs


def compute_metrics(rows, pairs):
    conditions = {}
    for name in ("baseline", "science"):
        records = [row for row in rows if row["condition"] == name]
        successes = len([row for row in records if row["exact_private_success"] is True])
        failures = len([row for row in records if row["exact_private_success"] is False])
        rewards = [row["official_reward"] for row in records if row["official_reward"] is not None]
        status_counts = {}
        for row in records:
            status_counts[row["status"]] = status_counts.get(row["status"], 0) + 1
        resources, stage_counts = {}, {}
        for quantity in (*TOKENS, "duration_seconds"):
            items = []
            for row in records:
                value = row.get(quantity) if quantity == "duration_seconds" else row["usage"][quantity]
                if finite(value) and value >= 0:
                    items.append(value)
            resources[quantity] = {"observed_trials": len(items), "missing_trials": len(records) - len(items), "observed_total": sum(items) if items else None, "observed_mean": sum(items) / len(items) if items else None}
        for row in records:
            for stage in row["stages"]:
                stage_name, stage_status = str(stage.get("name", "unknown")), str(stage.get("status", "unknown"))
                counts = stage_counts.setdefault(stage_name, {})
                counts[stage_status] = counts.get(stage_status, 0) + 1
        conditions[name] = {
            "attempts": len(records), "unique_tasks": len({row["task_id"] for row in records}),
            "exact_private_successes": successes, "exact_private_failures": failures, "exact_private_unknown": len(records) - successes - failures,
            "observed_exact_private_success_rate": successes / (successes + failures) if successes + failures else None,
            "success_fraction_all_attempts": successes / len(records) if records else None,
            "official_reward_observations": len(rewards), "official_reward_missing": len(records) - len(rewards),
            "mean_official_reward_observed": sum(rewards) / len(rewards) if rewards else None, "run_status_counts": dict(sorted(status_counts.items())),
            "resources": resources, "stage_status_counts": {stage: dict(sorted(counts.items())) for stage, counts in sorted(stage_counts.items())},
        }
    outcomes = {outcome: len([pair for pair in pairs if pair["outcome"] == outcome]) for outcome in OUTCOMES}
    n = sum(outcomes[outcome] for outcome in OUTCOMES[:4])
    return {"conditions": conditions, "pair_outcome_counts": outcomes, "observed_pairs": n, "observed_paired_success_delta_percentage_points": 100 * (outcomes["science_only"] - outcomes["baseline_only"]) / n if n else None}


def recompute(root):
    root = Path(root).resolve()
    if not root.is_dir():
        raise ValueError(f"Missing trial directory: {root}")
    rows = [reconstruct_row(root, receipt) for receipt in sorted(root.rglob("run.json"))]
    pairs = reconstruct_pairs(rows)
    return {
        "schema_version": "1.0", "task_ids": sorted({row["task_id"] for row in rows}),
        "exposure": {"development_tasks": ["002", "077"], "prior_private_test_exposure": ["002"]},
        "trials": rows, "pairs": pairs,
        "metrics": {"all": compute_metrics(rows, pairs), "untouched": compute_metrics([row for row in rows if not row["development_exposed"]], [pair for pair in pairs if not pair["development_exposed"]])},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runs", type=Path)
    parser.add_argument("--verify", type=Path, help="Require exact equality with a supplied summary.json")
    parser.add_argument("--output", type=Path, help="Write independently reconstructed JSON")
    args = parser.parse_args()
    try:
        result = recompute(args.runs)
        rendered = json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + "\n"
        if args.verify:
            supplied = object_from(args.verify)
            # Compare serialized types too: JSON true must not equal the number 1.
            if json.dumps(supplied, sort_keys=True, allow_nan=False) != json.dumps(result, sort_keys=True, allow_nan=False):
                raise ValueError("Summary does not match independent recomputation from raw artifacts")
        if args.output:
            args.output.write_text(rendered, encoding="utf-8")
        if args.verify:
            print(f"Verified {len(result['trials'])} trials and {len(result['pairs'])} task/run pairs.")
        elif not args.output:
            print(rendered, end="")
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(f"Recomputation failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
