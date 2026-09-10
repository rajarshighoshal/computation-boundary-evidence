#!/usr/bin/env python3
"""Render a paired comparison, including unrun arms, from independently audited receipts."""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path


ARMS = ("baseline", "science")
TOKENS = ("input_tokens", "cached_input_tokens", "output_tokens")


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def optional_object(path):
    if not path.is_file():
        return {}, "missing"
    try:
        value = read(path)
        if not isinstance(value, dict):
            raise ValueError("Expected object")
        return value, "available"
    except (ValueError, OSError):
        return {}, "unreadable"


def text(value):
    return "unknown" if value is None else str(value).replace("|", "\\|").replace("\n", " ")


def number(value, digits=2, divisor=1):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        return "unknown"
    return f"{value / divisor:.{digits}f}"


def outcome(row):
    value = row.get("exact_private_success")
    return "pass" if value is True else "fail" if value is False else "unknown"


def private_counts(row):
    private = row.get("private") or {}
    return f"{number(private.get('passed'), 0)}/{number(private.get('collected'), 0)}"


def table(lines, headers, rows):
    lines.extend(["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"])
    lines.extend("| " + " | ".join(text(value) for value in row) + " |" for row in rows)
    lines.append("")


def trial_path(root, row):
    path = (root / "jobs" / row["trial_path"]).resolve()
    if not path.is_relative_to((root / "jobs").resolve()):
        raise ValueError("Trial path escapes jobs directory")
    return path


def render(run_root, summary):
    schedule = read(run_root / "schedule.json")
    config = schedule["config"]
    tasks = config["task_ids"]
    planned = schedule["schedule"]
    keys = [(item["task_id"], item["condition"]) for item in planned]
    if len(set(tasks)) != len(tasks) or len(keys) != len(set(keys)) or set(keys) != {(task, arm) for task in tasks for arm in ARMS}:
        raise ValueError("Expected exactly one planned attempt per task and condition")
    if config.get("condition_order") and keys != [(task, arm) for task in tasks for arm in config["condition_order"][task]]:
        raise ValueError("Schedule differs from configured condition order")
    rows = {(row["task_id"], row["condition"]): row for row in summary["trials"]}
    if len(rows) != len(summary["trials"]) or not set(rows).issubset(keys):
        raise ValueError("Unplanned or duplicate trial receipts")
    patches = collections.Counter()
    setups, bundles = {}, {}
    for key, row in rows.items():
        for field in ("model", "reasoning_effort", "codex_version"):
            if config.get(field) is not None and row[field] != config[field]:
                raise ValueError(f"Run differs from schedule: {key}/{field}")
        for field in ("total_seconds", "extraction_seconds"):
            if config.get(field) is not None and row["config"].get(field) != config[field]:
                raise ValueError(f"Run budget differs from schedule: {key}/{field}")
        for field in ("selection_sha256", "implementation_revision", "uv_lock_sha256", "prompt_sha256"):
            if schedule.get(field) is not None and row["provenance"].get(field) != schedule[field]:
                raise ValueError(f"Run provenance differs from schedule: {key}/{field}")
        trial = trial_path(run_root, row)
        patch = trial / "artifacts/model.patch"
        if patch.is_file():
            expected = row.get("patch_sha256")
            if expected is not None and hashlib.sha256(patch.read_bytes()).hexdigest() != expected:
                raise ValueError(f"Candidate patch hash changed: {key}")
            patches["checked" if expected else "present_without_recorded_hash"] += 1
        else:
            patches["missing"] += 1
        setups[key] = optional_object(trial / "agent/setup.json")
        bundles[key] = optional_object(trial / "graph-bundle.json")
        bundle = bundles[key][0]
        if isinstance(bundle.get("graph"), dict):
            digest = hashlib.sha256(json.dumps(bundle["graph"], sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
            if any(expected is not None and expected != digest for expected in (row.get("graph_sha256"), bundle.get("graph_sha256"))):
                raise ValueError(f"Graph hash changed: {key}")

    absent = len(planned) - len(rows)
    lines = ["# Paired comparison: results", "",
             f"Planned tasks (configuration order): {', '.join(tasks)}. Recorded attempts: {len(rows)}/{len(planned)}; "
             f"planned attempts without a run receipt: {absent}. Schedule status: `{text(schedule.get('status'))}`.", "",
             "This is an exploratory comparison, not evidence of a general improvement. Unknown outcomes are not failures or successes; "
             "missing cost measurements are not zero. No significance or causal-attribution claim is made.", ""]
    if absent or schedule.get("status") != "completed":
        lines += ["**The planned comparison is incomplete.** All selected tasks and arms remain listed below; "
                  "unrun arms are not silently dropped or included as failures in an observed success rate.", ""]
    if schedule.get("error"):
        lines += ["Schedule error: " + text(schedule["error"]), ""]
    lines += ["## Outcomes for the full planned selection", ""]
    table(lines, ["Task", "Arm", "Schedule status", "Run status", "Exact private", "Private passed/collected", "Official reward", "Agent seconds"],
          [(item["task_id"], item["condition"], item.get("status"),
            rows.get(key, {}).get("status", "no receipt"), outcome(rows.get(key, {})),
            private_counts(rows.get(key, {})), rows.get(key, {}).get("official_reward"),
            number(rows.get(key, {}).get("duration_seconds"))) for item, key in zip(planned, keys)])
    metrics = summary["metrics"]["all"]
    table(lines, ["Arm", "Planned", "Recorded", "Exact pass", "Exact fail", "Unknown recorded", "No receipt"],
          [(arm, sum(key[1] == arm for key in keys), values["attempts"], values["exact_private_successes"],
            values["exact_private_failures"], values["exact_private_unknown"],
            sum(key[1] == arm and key not in rows for key in keys))
           for arm, values in metrics["conditions"].items()])
    pair_counts = collections.Counter()
    for task in tasks:
        left, right = rows.get((task, "baseline")), rows.get((task, "science"))
        if left is None and right is None:
            label = "neither_arm_recorded"
        elif left is None or right is None:
            label = "missing_baseline" if left is None else "missing_science"
        elif "unknown" in (outcome(left), outcome(right)):
            label = "unknown"
        else:
            label = {("pass", "pass"): "both_success", ("pass", "fail"): "baseline_only",
                     ("fail", "pass"): "science_only", ("fail", "fail"): "both_failure"}[outcome(left), outcome(right)]
        pair_counts[label] += 1
    table(lines, ["Paired outcome", "Tasks"], [(name, pair_counts[name]) for name in
          ("both_success", "baseline_only", "science_only", "both_failure", "unknown", "missing_baseline", "missing_science", "neither_arm_recorded")])
    lines += ["Exact private success and official reward are reported separately. Per-test Fail2Pass/Pass2Pass require matching "
              "original-baseline test identities; availability and diagnostics remain in the audited summary.", "",
              "## Time and token accounting", "",
              "Agent time includes extraction and handoff where applicable, but excludes image pulls, environment preparation and official verification. "
              "Token totals require usage from every recorded agent stage; repair-only usage is not reported as a full science-arm total. "
              "Observed totals below cover only the stated measured trials, not unrecorded attempts.", ""]
    resource_rows = []
    for arm in ARMS:
        resources = metrics["conditions"][arm]["resources"]
        for name in ("duration_seconds", *TOKENS, "over_budget_seconds"):
            value = resources[name]
            resource_rows.append((arm, name, number(value["observed_total"], 0 if name in TOKENS else 2),
                                  value["observed_trials"], value["missing_trials"]))
    table(lines, ["Arm", "Quantity", "Observed total", "Measured trials", "Missing recorded trials"], resource_rows)
    wall = None
    try:
        wall = (dt.datetime.fromisoformat(schedule["finished_at"]) - dt.datetime.fromisoformat(schedule["started_at"])).total_seconds()
    except (KeyError, ValueError, TypeError):
        pass
    lines += [f"Schedule elapsed seconds (including setup and verification): {number(wall)}.", "",
              "## Extraction and graph coverage", ""]
    for task in tasks:
        row = rows.get((task, "science"), {})
        bundle, bundle_status = bundles.get((task, "science"), ({}, "missing"))
        graph = bundle.get("graph") if isinstance(bundle.get("graph"), dict) else {}
        stages = [stage for stage in row.get("stages", []) if stage.get("name") == "extract"]
        lines += [f"### Task {task}", "",
                  f"Handoff status: `{text(row.get('extraction_status'))}`; graph artifact: {bundle_status}.", ""]
        if stages:
            table(lines, ["Stage/phase", "Status", "Seconds"],
                  [("extract", stage.get("status"), number(stage.get("duration_seconds"))) for stage in stages] +
                  [(phase.get("name"), phase.get("status"), number(phase.get("duration_seconds")))
                   for stage in stages for phase in stage.get("phases", [])])
        else:
            lines += ["Extraction timing/status receipt unavailable.", ""]
        counts = [(name, len(graph[name]) if isinstance(graph.get(name), list) else None)
                  for name in ("claims", "quantities", "evidence", "observations")]
        coverage = row.get("graph_coverage") or {}
        lines += ["Graph nodes: " + ", ".join(f"{name}={text(value)}" for name, value in counts) + ".",
                  "Recorded mechanical coverage: " + (", ".join(f"{name}={text(value)}" for name, value in sorted(coverage.items())) if coverage else "unknown") + ".", ""]
        analysis = bundle.get("analysis") if isinstance(bundle.get("analysis"), dict) else {}
        for name in ("code_grounding", "alignments"):
            items = analysis.get(name)
            counters = collections.Counter(item.get("status", "unknown") for item in items if isinstance(item, dict)) if isinstance(items, list) else None
            lines += [f"{name}: " + (", ".join(f"{status}={count}" for status, count in sorted(counters.items())) if counters else "no entries" if counters is not None else "unknown") + "."]
        lines.append("")
    lines += ["Coverage counters measure recoverable representations and supported rules, not scientific correctness. "
              "Neither successful extraction nor a passed probe establishes that the supplied guidance caused a repair outcome.", "",
              "## Measured Docker resources", ""]
    table(lines, ["Task", "Arm", "Setup receipt", "Docker GiB", "Task requested GiB", "Docker CPUs", "Below requested memory"],
          [(item["task_id"], item["condition"], status, number(setup.get("docker_memory_bytes"), divisor=1024**3),
            number(setup.get("task_requested_memory_mb"), divisor=1024), setup.get("docker_cpus"),
            setup.get("host_memory_below_task_request"))
           for item, key in zip(planned, keys) for setup, status in [setups.get(key, ({}, "missing"))]])
    lines += ["Docker totals are measured daemon allocation, not proof of per-container effective limits or parity with published benchmark resources. "
              "Missing setup receipts leave actual allocation unknown; requested resources alone do not establish feasibility.", "",
              "## Protocol and provenance", "",
              f"Model: {text(config.get('model'))}/{text(config.get('reasoning_effort'))}; "
              f"Codex {text(config.get('codex_version'))}; Pier {text(config.get('pier_version'))}. "
              f"Total allowance: {text(config.get('total_seconds'))} seconds; extraction cap: {text(config.get('extraction_seconds'))} seconds. "
              f"Attempts per task/arm: {text(config.get('attempts'))}; concurrency: {text(config.get('concurrency'))}.", "",
              "Planned order: " + " → ".join(f"{task}/{arm}" for task, arm in keys) + ".", ""]
    provenance = [(name, schedule.get(name)) for name in ("implementation_revision", "implementation_dirty", "config_sha256", "selection_sha256", "uv_lock_sha256", "prompt_sha256")]
    provenance += [(name, config.get(name)) for name in ("dataset_revision", "release_commit", "release_receipt", "sampling_manifest", "sampling_manifest_sha256", "allow_restricted_licenses")]
    table(lines, ["Record", "Value"], provenance)
    table(lines, ["Task", "Arm", "Trial path", "Environment image", "Verifier image"],
          [(row["task_id"], row["condition"], row["trial_path"], row["provenance"].get("environment_image"), row["provenance"].get("verifier_image")) for row in summary["trials"]])
    exposed = [task for task in tasks if task in summary["exposure"]["development_tasks"]]
    prior = [task for task in tasks if task in summary["exposure"]["prior_private_test_exposure"]]
    lines += [f"Recorded development-task overlap: {', '.join(exposed) or 'none'}; recorded prior private-test exposure: {', '.join(prior) or 'none'}. "
              "These markers are not a claim about other possible exposure.", "",
              f"Independent reconstruction verified {len(rows)} recorded trials and {len(summary['pairs'])} recorded task/run pairs. "
              f"Patch hashes checked: {patches['checked']}; patches missing: {patches['missing']}; "
              f"patches present without a recorded hash: {patches['present_without_recorded_hash']}.", "",
              "This document's quantitative text and tables are generated from durable records. Raw trajectories, patches, verifier receipts "
              f"and failure diagnostics remain under `{run_root}`. Only receipts beneath this run root are included; earlier development "
              "runs are not pooled. Unknowns and incomplete schedules must remain explicit in any downstream claims.", ""]
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", required=True, type=Path)
    parser.add_argument("--summary", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    subprocess.run([sys.executable, str(Path(__file__).with_name("recompute_results.py")),
                    str(args.run_root / "jobs"), "--verify", str(args.summary)], check=True)
    content = render(args.run_root, read(args.summary))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(content, encoding="utf-8")
    print(f"Generated {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
