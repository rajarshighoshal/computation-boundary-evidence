"""Deep comparison of development-run variants: per-task truth tables from raw receipts.

Usage:
    .venv/bin/python scripts/compare_dev_runs.py RUN_DIR [RUN_DIR ...] --output results/dev-comparison.json

Reads, per run directory: jobs/task-*/task_*/run.json (stage statuses, usage) and
jobs/task-*/task_*/verifier/reward.json (official outcome). Produces per-task matrices,
paired discordants, resource sums, and run-level verdicts. Never reads scheduler status
labels (they mislabel cleanup timeouts); verifier rewards and run.json stages are truth.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


def _load(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def run_rows(run_dir: Path) -> dict[str, dict[str, Any]]:
    """task -> arm -> {reward, repair, cleanup_err, in, cached, out, seconds}"""
    rows: dict[str, dict[str, Any]] = defaultdict(dict)
    for trial in sorted(run_dir.glob("jobs/task-*/task_*")):
        seg = trial.parent.name                      # task-001-science
        parts = seg.split("-")
        task, arm = parts[1], parts[2]
        record: dict[str, Any] = _load(trial / "run.json") or {}
        stages = {s.get("name") or s.get("stage"): s for s in record.get("stages", [])}
        usage: defaultdict[str, int] = defaultdict(int)
        for stage in stages.values():
            for key in ("input_tokens", "cached_input_tokens", "output_tokens"):
                usage[key] += (stage.get("usage") or {}).get(key) or 0
        reward = _load(trial / "verifier" / "reward.json")
        rows[task][arm] = {
            "reward": (reward or {}).get("reward"),
            "public": (reward or {}).get("public"),
            "private": (reward or {}).get("private"),
            "repair": (stages.get("repair") or {}).get("status"),
            "cleanup_err": bool(record.get("cleanup_error")),
            "in": usage["input_tokens"], "cached": usage["cached_input_tokens"],
            "out": usage["output_tokens"],
            "seconds": record.get("duration_seconds") or 0,
        }
    return rows


def summarize(rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {"arms": {}, "pairs": {}}
    for arm in ("baseline", "science"):
        entries = [r[arm] for r in rows.values() if arm in r]
        solved = sum(1 for e in entries if e["reward"] == 1)
        out["arms"][arm] = {
            "attempts": len(entries), "solved": solved,
            "no_verifier": sum(1 for e in entries if e["reward"] is None),
            "mean_reward": round(sum(e["reward"] or 0 for e in entries) / max(1, len(entries)), 3),
            "input_m": round(sum(e["in"] for e in entries) / 1e6, 1),
            "output_k": round(sum(e["out"] for e in entries) / 1e3, 1),
            "mean_seconds": round(sum(e["seconds"] for e in entries) / max(1, len(entries))),
        }
    buckets = {"both": [], "baseline_only": [], "science_only": [], "neither": []}
    for task in sorted(rows):
        b = rows[task].get("baseline", {}).get("reward")
        s = rows[task].get("science", {}).get("reward")
        if b == 1 and s == 1:
            buckets["both"].append(task)
        elif b == 1:
            buckets["baseline_only"].append(task)
        elif s == 1:
            buckets["science_only"].append(task)
        else:
            buckets["neither"].append(task)
    out["pairs"] = {k: v for k, v in buckets.items()}
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runs", nargs="+", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report: dict[str, Any] = {"runs": {}}
    for run_dir in args.runs:
        rows = run_rows(run_dir)
        report["runs"][str(run_dir)] = {"summary": summarize(rows),
                                        "rows": {t: {a: r for a, r in arms.items()}
                                                 for t, arms in rows.items()}}
    if len(args.runs) > 1:
        first, *rest = args.runs
        base = run_rows(first)
        report["transitions"] = {}
        for other in rest:
            change = run_rows(other)
            flips: dict[str, list[str]] = {"gained_science": [], "lost_science": [], "gained_baseline": [], "lost_baseline": []}
            for task in sorted(set(base) & set(change)):
                for arm, gained, lost in (("science", "gained_science", "lost_science"),
                                          ("baseline", "gained_baseline", "lost_baseline")):
                    before = base[task].get(arm, {}).get("reward")
                    after = change[task].get(arm, {}).get("reward")
                    if before == 0 and after == 1:
                        flips[gained].append(task)
                    elif before == 1 and after == 0:
                        flips[lost].append(task)
            report["transitions"][f"{first} -> {other}"] = flips
    args.output.write_text(json.dumps(report, indent=1, sort_keys=True))
    for name, data in report["runs"].items():
        arms = data["summary"]["arms"]
        pairs = data["summary"]["pairs"]
        print(f"{Path(name).name}: baseline {arms['baseline']['solved']}/{arms['baseline']['attempts']} "
              f"| science {arms['science']['solved']}/{arms['science']['attempts']} "
              f"| sci-only {pairs['science_only']} base-only {pairs['baseline_only']}")
    if "transitions" in report:
        for pair, flips in report["transitions"].items():
            print(f"transition {Path(pair.split(' -> ')[0]).name} -> {Path(pair.split(' -> ')[1]).name}: "
                  f"+sci {flips['gained_science']} -sci {flips['lost_science']} "
                  f"+base {flips['gained_baseline']} -base {flips['lost_baseline']}")


if __name__ == "__main__":
    main()
