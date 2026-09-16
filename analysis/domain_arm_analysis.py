"""Domain / task-type stratified analysis of the CBE intervention.

Produces the per-domain and per-task-type performance comparison between the two arms
(baseline shell tools vs. computation-and-boundary evidence, CBE) from raw run receipts.

Naming: the published arm name is CBE (computation and boundary evidence). The frozen
run directories encode that arm with the suffix "-science"; receipts written here use the
published name and record the mapping under provenance.arm_naming.

Partitions
----------
- locked89_k3 : the held-out evaluation, 89 tasks x 2 arms x 3 replicate runs
                (runs/deepseek-locked89-k1-v2, -k2-v2, -k3-clean-v1).
- dev30_k4    : the development partition, 30 tasks x 2 arms x 4 replicate runs
                (runs/deepseek-development-e2e-40-v1, -e2e-40-low-v1 + -e2e-tail-10-low-v1,
                -dev30-contracts-low-v1, -dev30-v3).

Stratification axes (both benchmark-native, no invented provenance)
-------------------------------------------------------------------
- scientific domain  : 20 domains from the benchmark paper's Appendix Table 5, extracted and
                       validated verbatim by analysis/benchmark_task_domains.py.
- language            : benchmark metadata `language` field.
- knowledge ablation  : benchmark metadata `science_knowledge_ablation` flag.

Validation
----------
Recomputing the locked partition must reproduce results/locked89-k3-clean-analysis.json
(per-task solved counts and per-arm totals) exactly; a mismatch is a hard error.
"""

from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

from analyze_locked_k3 import load_runs, sign_test_p  # noqa: E402

OUT = REPO / "results" / "domain-arm-analysis.json"
FROZEN_LOCKED = REPO / "results" / "locked89-k3-clean-analysis.json"
DOMAIN_RECEIPT = REPO / "results" / "benchmark-task-domains.json"
TASKS_METADATA = REPO / "vendor" / "swe-bench-science" / "huggingface" / "tasks"
SPLIT = REPO / "configs" / "interactive-science.split.json"

LOCKED_RUNS = [
    "deepseek-locked89-k1-v2",
    "deepseek-locked89-k2-v2",
    "deepseek-locked89-k3-clean-v1",
]
DEV_RUNS = [
    "deepseek-development-e2e-40-v1",
    "deepseek-development-e2e-40-low-v1",
    "deepseek-development-e2e-tail-10-low-v1",
    "deepseek-dev30-contracts-low-v1",
    "deepseek-dev30-v3",
]

Z95 = 1.959963984540054

# On-disk run directories label the intervention arm "science"; the published name is CBE.
ON_DISK_ARM = {"baseline": "baseline", "cbe": "science"}


def wilson(solved: int, verified: int) -> list[float]:
    """Wilson score interval for a binomial rate."""
    if verified == 0:
        return [0.0, 0.0, 0.0]
    phat = solved / verified
    denom = 1 + Z95**2 / verified
    center = (phat + Z95**2 / (2 * verified)) / denom
    spread = (Z95 / denom) * math.sqrt(phat * (1 - phat) / verified + Z95**2 / (4 * verified**2))
    return [round(phat, 4), round(max(0.0, center - spread), 4), round(min(1.0, center + spread), 4)]


def arm_stats(data: dict[str, dict[str, list[dict[str, Any]]]], tasks: list[str], arm: str) -> dict[str, Any]:
    solved = verified = 0
    for task in tasks:
        for record in data.get(task, {}).get(arm, []):
            if record["reward"] is None:
                continue
            verified += 1
            solved += int(record["reward"])
    rate, low, high = wilson(solved, verified)
    return {"solved": solved, "verified": verified, "rate": rate, "wilson_95ci": [low, high]}


def stratify(
    data: dict[str, dict[str, list[dict[str, Any]]]],
    groups: dict[str, list[str]],
    label: str,
) -> dict[str, Any]:
    table: dict[str, Any] = {}
    for group, tasks in sorted(groups.items()):
        tasks = [t for t in tasks if t in data]
        if not tasks:
            continue
        base = arm_stats(data, tasks, "baseline")
        sci = arm_stats(data, tasks, "science")
        diffs: list[float] = []
        wins = losses = 0
        for task in tasks:
            b = [int(r["reward"]) for r in data[task].get("baseline", []) if r["reward"] is not None]
            s = [int(r["reward"]) for r in data[task].get("science", []) if r["reward"] is not None]
            if not b or not s:
                continue
            diff = sum(s) / len(s) - sum(b) / len(b)
            diffs.append(diff)
            wins += diff > 0
            losses += diff < 0
        table[group] = {
            "n_tasks": len(tasks),
            "tasks": sorted(tasks),
            "baseline": base,
            "cbe": sci,
            "delta_pp": round((sci["rate"] - base["rate"]) * 100, 1),
            "paired": {
                "tasks_compared": len(diffs),
                "science_better": wins,
                "baseline_better": losses,
                "ties": len(diffs) - wins - losses,
                "sign_test_p": round(sign_test_p(wins, losses), 4),
            },
        }
    return {"axis": label, "groups": table}


def main() -> int:
    split = json.loads(SPLIT.read_text())
    dev_ids = sorted(split["development_task_ids"])
    locked_ids = sorted(split["locked_evaluation_task_ids"])

    domains = json.loads(DOMAIN_RECEIPT.read_text())["tasks"]
    manifest: dict[str, dict[str, Any]] = {}
    for meta_path in sorted(TASKS_METADATA.glob("task_*/metadata.json")):
        record = json.loads(meta_path.read_text())
        manifest[record["task_id"]] = record

    def groups_axis(key: str, ids: list[str]) -> dict[str, list[str]]:
        groups: dict[str, list[str]] = defaultdict(list)
        for task in ids:
            if key == "domain":
                value = domains[task]["domain"]
            elif key == "language":
                value = manifest[task]["language"]
            elif key == "ablation":
                flag = manifest[task].get("science_knowledge_ablation")
                value = "knowledge-ablated" if flag else "knowledge-provided"
            else:
                raise ValueError(key)
            groups[value].append(task)
        return dict(groups)

    partitions: dict[str, Any] = {}
    frozen: dict[str, Any] = {}
    for name, run_names, ids, k in (
        ("locked89_k3", LOCKED_RUNS, locked_ids, 3),
        ("dev30_k4", DEV_RUNS, dev_ids, 4),
    ):
        data = load_runs([REPO / "runs" / run for run in run_names])
        partition: dict[str, Any] = {
            "runs": run_names,
            "replicate_runs": k,
            "n_tasks": len(ids),
            "overall": {
                "baseline": arm_stats(data, ids, "baseline"),
                "cbe": arm_stats(data, ids, ON_DISK_ARM["cbe"]),
            },
            "by_domain": stratify(data, groups_axis("domain", ids), "scientific domain"),
            "by_language": stratify(data, groups_axis("language", ids), "task language"),
            "by_ablation": stratify(data, groups_axis("ablation", ids), "knowledge-ablation flag"),
        }
        overall = partition["overall"]
        overall["delta_pp"] = round((overall["cbe"]["rate"] - overall["baseline"]["rate"]) * 100, 1)
        partitions[name] = partition
        frozen[name] = data

    # --- validation against the frozen locked-89 receipt -------------------------------
    receipt = json.loads(FROZEN_LOCKED.read_text())
    problems: list[str] = []
    for label, on_disk in ON_DISK_ARM.items():
        got = partitions["locked89_k3"]["overall"][label]
        want = receipt["totals"][on_disk]
        if got["solved"] != want["attempts_solved"] or got["verified"] != want["attempts_verified"]:
            problems.append(
                f"[{label}] recomputed {got['solved']}/{got['verified']} != frozen "
                f"{want['attempts_solved']}/{want['attempts_verified']}"
            )
    for task, entry in receipt["tasks"].items():
        recomputed = {
            label: arm_stats(frozen["locked89_k3"], [task], on_disk)["solved"]
            for label, on_disk in ON_DISK_ARM.items()
        }
        for label, on_disk in ON_DISK_ARM.items():
            if recomputed[label] != entry[on_disk]["solved"]:
                problems.append(
                    f"task {task} [{label}] recomputed {recomputed[label]} != frozen {entry[on_disk]['solved']}"
                )
    if problems:
        print("VALIDATION FAILED against frozen locked-89 receipt:", file=sys.stderr)
        for problem in problems[:20]:
            print(" -", problem, file=sys.stderr)
        return 1

    payload = {
        "kind": "cbe-domain-and-task-type-analysis",
        "provenance": {
            "verdicts": "per-attempt verifier reward.json + run.json usage under runs/",
            "domains": "results/benchmark-task-domains.json (paper Appendix Table 5, validated)",
            "task_metadata": "vendor/swe-bench-science/huggingface/tasks/task_*/metadata.json",
            "split": str(SPLIT.relative_to(REPO)),
            "validated_against": str(FROZEN_LOCKED.relative_to(REPO)),
            "arm_naming": {"baseline": "baseline (ordinary shell tools)",
                           "cbe": "computational and boundary evidence tools; on-disk run suffix "
                                  "'-science', arm key 'science' in raw verifier receipts"},
        },
        "partitions": partitions,
    }
    OUT.write_text(json.dumps(payload, indent=1) + "\n")

    for name, partition in partitions.items():
        print(f"\n=== {name} ({partition['replicate_runs']} replicate runs, {partition['n_tasks']} tasks)")
        base, sci = partition["overall"]["baseline"], partition["overall"]["cbe"]
        print(
            f"overall: baseline {base['solved']}/{base['verified']} ({base['rate']:.1%}) vs "
            f"CBE {sci['solved']}/{sci['verified']} ({sci['rate']:.1%}) "
            f"[{partition['overall']['delta_pp']:+.1f} pp]"
        )
        for axis in ("by_domain", "by_language", "by_ablation"):
            print(f"  -- {partition[axis]['axis']}")
            for group, row in partition[axis]["groups"].items():
                print(
                    f"     {group:<46} n={row['n_tasks']:<3} "
                    f"base {row['baseline']['rate']:.1%} ({row['baseline']['solved']}/{row['baseline']['verified']})  "
                    f"CBE {row['cbe']['rate']:.1%} ({row['cbe']['solved']}/{row['cbe']['verified']})  "
                    f"delta {row['delta_pp']:+5.1f} pp"
                )
    print(f"\nWrote {OUT.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
