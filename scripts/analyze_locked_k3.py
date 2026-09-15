"""Repeated-measures analysis for the locked-89 k=3 evaluation.

Usage:
    .venv/bin/python scripts/analyze_locked_k3.py --output results/locked89-k3-analysis.json \
        runs/deepseek-locked89-k1-v1 runs/deepseek-locked89-k2-v1 runs/deepseek-locked89-k3-v1

Per task and arm it counts verified successes across the k replicate runs, then compares arms
with a paired sign test over per-task success-rate differences and a bootstrap CI for the mean
difference. Resource totals come from run.json usage records. Scheduler status labels are never
read; verifier rewards and run.json stages are the authority. Deterministic: fixed RNG seed.
"""
from __future__ import annotations

import argparse
import json
import math
import random
from collections import defaultdict
from pathlib import Path
from typing import Any


def load_runs(run_dirs: list[Path]) -> dict[str, dict[str, list[dict[str, Any]]]]:
    """task -> arm -> list of per-run records (ordered by run directory)."""
    data: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for run_dir in run_dirs:
        for trial in sorted(run_dir.glob("jobs/task-*/task_*")):
            seg = trial.parent.name
            _, task, arm = seg.split("-", 2)
            reward = None
            reward_path = trial / "verifier" / "reward.json"
            if reward_path.is_file():
                try:
                    reward = json.loads(reward_path.read_text()).get("reward")
                except ValueError:
                    reward = None
            usage = defaultdict(int)
            record = {}
            if (trial / "run.json").is_file():
                try:
                    record = json.loads((trial / "run.json").read_text())
                except ValueError:
                    record = {}
            for stage in record.get("stages", []):
                stage_usage = stage.get("usage") or {}
                for key in ("input_tokens", "cached_input_tokens", "output_tokens"):
                    usage[key] += stage_usage.get(key) or 0
            data[task][arm].append({
                "reward": reward, "run": run_dir.name,
                "in": usage["input_tokens"], "cached": usage["cached_input_tokens"],
                "out": usage["output_tokens"],
                "seconds": record.get("duration_seconds") or 0,
            })
    return data


def sign_test_p(wins: int, losses: int) -> float:
    """Two-sided exact binomial sign test."""
    n = wins + losses
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, i) for i in range(0, min(wins, losses) + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def bootstrap_ci(diffs: list[float], seed: int = 20260916, draws: int = 20000) -> tuple[float, float]:
    rng = random.Random(seed)
    n = len(diffs)
    if n == 0:
        return (0.0, 0.0)
    means = sorted(sum(rng.choices(diffs, k=n)) / n for _ in range(draws))
    return means[int(0.025 * draws)], means[int(0.975 * draws)]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runs", nargs="+", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    data = load_runs(args.runs)
    k = len(args.runs)
    report: dict[str, Any] = {"schema": "locked-k3-analysis-1.0", "k": k,
                              "runs": [r.name for r in args.runs], "tasks": {}, "totals": {}}

    diffs: list[float] = []
    wins = losses = ties_zero = 0
    per_arm = {"baseline": defaultdict(int), "science": defaultdict(int)}
    for task in sorted(data):
        arms = data[task]
        b_rewards = [r["reward"] for r in arms.get("baseline", [])]
        s_rewards = [r["reward"] for r in arms.get("science", [])]
        b_ok = [int(r) for r in b_rewards if r is not None]
        s_ok = [int(r) for r in s_rewards if r is not None]
        b_rate = sum(b_ok) / len(b_ok) if b_ok else None
        s_rate = sum(s_ok) / len(s_ok) if s_ok else None
        entry = {"baseline": {"verified": len(b_ok), "solved": sum(b_ok)},
                 "science": {"verified": len(s_ok), "solved": sum(s_ok)}}
        if b_rate is not None and s_rate is not None:
            diff = s_rate - b_rate
            entry["rate_difference"] = round(diff, 4)
            diffs.append(diff)
            if diff > 0:
                wins += 1
            elif diff < 0:
                losses += 1
            else:
                ties_zero += 1
        report["tasks"][task] = entry
        for arm, rewards in (("baseline", b_ok), ("science", s_ok)):
            per_arm[arm]["solved"] += sum(rewards)
            per_arm[arm]["verified"] += len(rewards)
        for arm in ("baseline", "science"):
            for r in arms.get(arm, []):
                per_arm[arm]["in"] += r["in"]
                per_arm[arm]["cached"] += r["cached"]
                per_arm[arm]["out"] += r["out"]
                per_arm[arm]["seconds"] += r["seconds"]

    ci_low, ci_high = bootstrap_ci(diffs)
    mean_diff = sum(diffs) / len(diffs) if diffs else 0.0
    report["comparison"] = {
        "tasks_with_both_arms": len(diffs),
        "science_better": wins, "baseline_better": losses, "ties": ties_zero,
        "sign_test_p": round(sign_test_p(wins, losses), 4),
        "mean_rate_difference": round(mean_diff, 4),
        "bootstrap_95ci": [round(ci_low, 4), round(ci_high, 4)],
    }
    for arm in ("baseline", "science"):
        totals = per_arm[arm]
        report["totals"][arm] = {
            "attempts_verified": totals["verified"], "attempts_solved": totals["solved"],
            "solve_rate": round(totals["solved"] / totals["verified"], 4) if totals["verified"] else None,
            "input_tokens": totals["in"], "cached_input_tokens": totals["cached"],
            "output_tokens": totals["out"], "work_seconds": round(totals["seconds"], 1),
        }
    args.output.write_text(json.dumps(report, indent=1, sort_keys=True))
    print(f"k={k}; tasks with both arms: {len(diffs)}")
    for arm in ("baseline", "science"):
        t = report["totals"][arm]
        print(f"  {arm}: {t['attempts_solved']}/{t['attempts_verified']} "
              f"({t['solve_rate']:.1%}) in={t['input_tokens']/1e6:.1f}M out={t['output_tokens']/1e3:.0f}k")
    print(f"  paired: science better {wins}, baseline better {losses}, ties {ties_zero}; "
          f"sign-test p={sign_test_p(wins, losses):.4f}")
    print(f"  mean rate difference {mean_diff:+.3f} "
          f"[95% CI {ci_low:+.3f}, {ci_high:+.3f}]")


if __name__ == "__main__":
    main()
