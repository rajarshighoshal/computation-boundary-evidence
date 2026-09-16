"""Repeated-measures analysis for the locked-89 k=2 evaluation (Runs k=1 and k=2).

Usage:
    .venv/bin/python scripts/analyze_locked_k2.py --output results/locked89-k2-analysis.json \
        runs/deepseek-locked89-k1-v2 runs/deepseek-locked89-k2-v2
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
    data: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for run_dir in run_dirs:
        for trial in sorted(run_dir.glob("jobs/task-*/task_*")):
            seg = trial.parent.name
            _, task, arm = seg.split("-", 2)
            reward = None
            private_passed = private_collected = None
            reward_path = trial / "verifier" / "reward.json"
            if reward_path.is_file():
                try:
                    reward_payload = json.loads(reward_path.read_text())
                    reward = reward_payload.get("reward")
                    private = reward_payload.get("private") or {}
                    private_passed = private.get("passed")
                    private_collected = private.get("collected")
                except ValueError:
                    reward = None
            usage = defaultdict(int)
            work_seconds = 0.0
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
                work_seconds += stage.get("work_seconds") or 0.0
            data[task][arm].append({
                "reward": reward, "run": run_dir.name,
                "private_passed": private_passed, "private_collected": private_collected,
                "in": usage["input_tokens"], "cached": usage["cached_input_tokens"],
                "out": usage["output_tokens"],
                "seconds": record.get("duration_seconds") or 0,
                "work_seconds": round(work_seconds, 1),
            })
    return data


def sign_test_p(wins: int, losses: int) -> float:
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
    report: dict[str, Any] = {"schema": "locked-k2-analysis-1.0", "k": k,
                              "runs": [r.name for r in args.runs], "tasks": {}, "totals": {}}

    diffs: list[float] = []
    wins = losses = ties_zero = 0
    per_arm: dict[str, defaultdict[str, Any]] = {"baseline": defaultdict(int), "science": defaultdict(int)}
    for task in sorted(data):
        arms = data[task]
        b_rewards = [r["reward"] for r in arms.get("baseline", [])]
        s_rewards = [r["reward"] for r in arms.get("science", [])]
        b_ok = [int(r) for r in b_rewards if r is not None]
        s_ok = [int(r) for r in s_rewards if r is not None]
        b_rate = sum(b_ok) / len(b_ok) if b_ok else None
        s_rate = sum(s_ok) / len(s_ok) if s_ok else None
        entry: dict[str, Any] = {"baseline": {"verified": len(b_ok), "solved": sum(b_ok)},
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
                per_arm[arm]["seconds"] += float(r["seconds"])
                per_arm[arm]["work_seconds"] += float(r["work_seconds"])
                if r["private_collected"]:
                    per_arm[arm]["tests_passed"] += r["private_passed"] or 0
                    per_arm[arm]["tests_collected"] += r["private_collected"]
        for arm in ("baseline", "science"):
            passed = sum(r["private_passed"] or 0 for r in arms.get(arm, []) if r["private_collected"])
            collected = sum(r["private_collected"] or 0 for r in arms.get(arm, []) if r["private_collected"])
            if collected:
                entry[arm]["tests_passed_rate"] = round(passed / collected, 4)

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
            "private_tests_passed": totals["tests_passed"], "private_tests_collected": totals["tests_collected"],
            "graded_test_rate": round(totals["tests_passed"] / totals["tests_collected"], 4)
                                if totals["tests_collected"] else None,
            "input_tokens": totals["in"], "cached_input_tokens": totals["cached"],
            "output_tokens": totals["out"],
            "work_seconds_total": round(totals["work_seconds"], 1),
            "duration_seconds_total": round(totals["seconds"], 1),
            "mean_work_seconds_per_attempt": round(totals["work_seconds"] / totals["verified"], 1)
                                             if totals["verified"] else None,
        }
    args.output.write_text(json.dumps(report, indent=1, sort_keys=True))
    print(f"k={k}; tasks with both arms: {len(diffs)}")
    for arm in ("baseline", "science"):
        t = report["totals"][arm]
        print(f"  {arm}: {t['attempts_solved']}/{t['attempts_verified']} ({t['solve_rate']:.1%}) | "
              f"graded tests {t['private_tests_passed']}/{t['private_tests_collected']} "
              f"({t['graded_test_rate']:.1%}) | in={t['input_tokens']/1e6:.1f}M out={t['output_tokens']/1e3:.0f}k "
              f"| work {t['mean_work_seconds_per_attempt']:.0f}s/attempt")
    print(f"  paired: science better {wins}, baseline better {losses}, ties {ties_zero}; "
          f"sign-test p={sign_test_p(wins, losses):.4f}")
    print(f"  mean rate difference {mean_diff:+.3f} "
          f"[95% CI {ci_low:+.3f}, {ci_high:+.3f}]")


if __name__ == "__main__":
    main()
