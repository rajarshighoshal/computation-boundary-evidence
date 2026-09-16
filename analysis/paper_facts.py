"""Assemble every number the report quotes into one durable receipt.

Naming: the intervention arm is published as CBE (computation and boundary evidence). Frozen
run directories and the frozen locked-89 receipt encode it as "science"; this receipt reports the
published name and records that mapping under provenance.arm_naming.

Sources: the frozen locked-89 k=3 receipt, the dev-30 consolidation, the matched
2x2 effort evaluation, and per-attempt verifier records under runs/. Writes
results/paper-facts.json; the report text is written from that file only.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "analysis"))

from analyze_locked_k3 import load_runs, sign_test_p  # noqa: E402
from domain_arm_analysis import DEV_RUNS, LOCKED_RUNS, Z95  # noqa: E402

OUT = REPO / "results" / "paper-facts.json"

# Published arm name for the on-disk "science" arm.
ON_DISK_ARM = {"baseline": "baseline", "cbe": "science"}


def wilson(solved: int, verified: int) -> list[float]:
    import math

    if verified == 0:
        return [0.0, 0.0]
    phat = solved / verified
    denom = 1 + Z95**2 / verified
    center = (phat + Z95**2 / (2 * verified)) / denom
    spread = (Z95 / denom) * math.sqrt(phat * (1 - phat) / verified + Z95**2 / (4 * verified**2))
    return [round(max(0.0, center - spread), 4), round(min(1.0, center + spread), 4)]


def arm_summary(data: dict[str, Any], arm: str) -> dict[str, Any]:
    solved = verified = 0
    for task in sorted(data):
        for record in data[task].get(arm, []):
            if record["reward"] is None:
                continue
            verified += 1
            solved += int(record["reward"])
    return {"solved": solved, "verified": verified, "rate": round(solved / verified, 4),
            "wilson_95ci": wilson(solved, verified)}


def solve_count_map(data: dict[str, Any], arm: str) -> dict[str, int]:
    out = {}
    for task in sorted(data):
        rewards = [int(r["reward"]) for r in data[task].get(arm, []) if r["reward"] is not None]
        out[task] = sum(rewards)
    return out


def pass_at_k(data: dict[str, Any], arm: str, k: int) -> float:
    solved = total = 0
    for task in sorted(data):
        rewards = [r["reward"] for r in data[task].get(arm, [])][:k]
        verified = [int(r) for r in rewards if r is not None]
        if not verified:
            continue
        total += 1
        solved += any(verified)
    return round(solved / total, 4) if total else 0.0


def main() -> int:
    locked = load_runs([REPO / "runs" / name for name in LOCKED_RUNS])
    dev = load_runs([REPO / "runs" / name for name in DEV_RUNS])
    frozen = json.loads((REPO / "results" / "locked89-k3-clean-analysis.json").read_text())
    domains = json.loads((REPO / "results" / "benchmark-task-domains.json").read_text())["tasks"]
    consolidation = json.loads((REPO / "results" / "dev30-four-run-consolidation.json").read_text())
    matrix = json.loads((REPO / "results" / "complete-30-task-2x2-matrix.json").read_text())
    matched = json.loads((REPO / "results" / "deepseek-2x2-matched-evaluation.json").read_text())

    b_locked = solve_count_map(locked, "baseline")
    s_locked = solve_count_map(locked, "science")
    joint = Counter((b_locked[task], s_locked[task]) for task in b_locked)
    b_dev = solve_count_map(dev, "baseline")
    s_dev = solve_count_map(dev, "science")

    # Two mover definitions, both reported: by raw solve count, and by solve rate (the definition
    # the paired sign test uses, since verified attempt counts differ between arms).
    science_only = [t for t in sorted(b_locked) if s_locked[t] and not b_locked[t]]
    baseline_only = [t for t in sorted(b_locked) if b_locked[t] and not s_locked[t]]
    rate_gains: list[str] = []
    rate_losses: list[str] = []
    for task in sorted(b_locked):
        base = [int(r["reward"]) for r in locked[task].get("baseline", []) if r["reward"] is not None]
        cbe = [int(r["reward"]) for r in locked[task].get("science", []) if r["reward"] is not None]
        if not base or not cbe:
            continue
        base_rate, cbe_rate = sum(base) / len(base), sum(cbe) / len(cbe)
        if cbe_rate > base_rate:
            rate_gains.append(task)
        elif cbe_rate < base_rate:
            rate_losses.append(task)

    facts = {
        "kind": "report-facts",
        "provenance": {
            "locked_receipt": "results/locked89-k3-clean-analysis.json",
            "locked_runs": LOCKED_RUNS,
            "dev_runs": DEV_RUNS,
            "domain_mapping": "results/benchmark-task-domains.json",
            "effort_matrix": "results/complete-30-task-2x2-matrix.json",
            "matched_effort": "results/deepseek-2x2-matched-evaluation.json",
            "consolidation": "results/dev30-four-run-consolidation.json",
            "arm_naming": {"baseline": "ordinary shell tools",
                           "cbe": "computation and boundary evidence (CBE) tools; frozen runs and "
                                  "verifier receipts encode this arm as 'science'"},
        },
        "model": "DeepSeek V4.1 Flash (temperature 0, PYTHONHASHSEED=0, no container network)",
        "locked89_k3": {
            "baseline": arm_summary(locked, ON_DISK_ARM["baseline"]),
            "cbe": arm_summary(locked, ON_DISK_ARM["cbe"]),
            "token_totals": {
                arm: {
                    "input": frozen["totals"][arm]["input_tokens"],
                    "cached_input": frozen["totals"][arm]["cached_input_tokens"],
                    "output": frozen["totals"][arm]["output_tokens"],
                    "mean_output_per_attempt": round(
                        frozen["totals"][arm]["output_tokens"] / frozen["totals"][arm]["attempts_verified"]),
                    "mean_work_seconds": frozen["totals"][arm]["mean_work_seconds_per_attempt"],
                    "graded_test_rate": frozen["totals"][arm]["graded_test_rate"],
                    "graded_tests_passed": frozen["totals"][arm]["private_tests_passed"],
                    "graded_tests_collected": frozen["totals"][arm]["private_tests_collected"],
                }
                for arm in (ON_DISK_ARM["baseline"], ON_DISK_ARM["cbe"])
            },
            "output_token_delta_pct": round(
                (frozen["totals"]["science"]["output_tokens"] / frozen["totals"]["baseline"]["output_tokens"] - 1) * 100, 1),
            "output_tokens_saved": frozen["totals"]["baseline"]["output_tokens"]
                                    - frozen["totals"]["science"]["output_tokens"],
            "comparison": frozen["comparison"],
            "replication": {
                "joint_solve_counts_baseline_science": {f"{b}/{s}": n for (b, s), n in sorted(joint.items())},
                "tasks_solved_all_3": {"baseline": sorted(t for t in b_locked if b_locked[t] == 3),
                                       "cbe": sorted(t for t in s_locked if s_locked[t] == 3)},
                "tasks_solved_none": {"baseline": [t for t in sorted(b_locked) if b_locked[t] == 0],
                                      "science": [t for t in sorted(s_locked) if s_locked[t] == 0]},
                "tasks_flipping": {
                    "baseline": [t for t in sorted(b_locked) if 0 < b_locked[t] < 3],
                    "cbe": [t for t in sorted(s_locked) if 0 < s_locked[t] < 3],
                },
                "science_only_tasks": science_only,
                "baseline_only_tasks": baseline_only,
                "rate_gain_tasks": rate_gains,
                "rate_loss_tasks": rate_losses,
                "pass_at_k": {
                    label: {k: pass_at_k(locked, arm, k) for k in (1, 2, 3)}
                    for label, arm in ON_DISK_ARM.items()
                },
            },
        },
        "dev30_k4": {
            "baseline": arm_summary(dev, ON_DISK_ARM["baseline"]),
            "cbe": arm_summary(dev, ON_DISK_ARM["cbe"]),
            "pass_at_k": {label: {k: pass_at_k(dev, arm, k) for k in (1, 2, 3, 4)}
                          for label, arm in ON_DISK_ARM.items()},
            "science_only_tasks": [t for t in sorted(b_dev) if s_dev[t] and not b_dev[t]],
            "baseline_only_tasks": [t for t in sorted(b_dev) if b_dev[t] and not s_dev[t]],
            "tokens": {
                arm: {
                    "input": sum(r["in"] for t in dev for r in dev[t].get(arm, []) if r["reward"] is not None),
                    "output": sum(r["out"] for t in dev for r in dev[t].get(arm, []) if r["reward"] is not None),
                    "attempts": sum(1 for t in dev for r in dev[t].get(arm, []) if r["reward"] is not None),
                }
                for arm in (ON_DISK_ARM["baseline"], ON_DISK_ARM["cbe"])
            },
            "consolidation_claim": consolidation["pooled_totals"],
        },
        "effort_matrix": {
            "dev30": matrix["matrix_results"],
            "matched20": matched["matrix_success_rates"],
        },
        "task_examples": {
            "103": {
                "domain": domains["103"]["domain"],
                "locked": {"baseline": b_locked.get("103"), "cbe": s_locked.get("103")},
            },
            "077": {
                "domain": domains["077"]["domain"] if "077" in domains else None,
                "dev": {"baseline": b_dev.get("077"), "cbe": s_dev.get("077")},
            },
            "022": {
                "domain": domains.get("022", {}).get("domain"),
                "locked": {"baseline": b_locked.get("022"), "cbe": s_locked.get("022")},
            },
        },
    }

    hard = [t for t in sorted(b_locked) if b_locked[t] == 0 and s_locked[t] == 0]
    facts["locked89_k3"]["replication"]["tasks_never_solved_either_arm"] = hard

    OUT.write_text(json.dumps(facts, indent=1) + "\n")
    print(f"Wrote {OUT.relative_to(REPO)}")
    print(json.dumps(facts["locked89_k3"]["comparison"], indent=1))
    print("locked:", facts["locked89_k3"]["baseline"], facts["locked89_k3"]["cbe"])
    print("dev:", facts["dev30_k4"]["baseline"], facts["dev30_k4"]["cbe"])
    print("joint solve counts:", facts["locked89_k3"]["replication"]["joint_solve_counts_baseline_science"])
    print("pass@k locked:", facts["locked89_k3"]["replication"]["pass_at_k"])
    print("science-only (count):", science_only, "baseline-only (count):", baseline_only)
    print("rate gains:", rate_gains, "| rate losses:", rate_losses)
    print("examples:", json.dumps(facts["task_examples"], indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
