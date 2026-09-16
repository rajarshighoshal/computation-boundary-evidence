"""Export one self-contained evidence packet for the reported experiment.

The packet is meant to be handed to another person or model together with
``docs/PLOT_SPEC.md``: it carries every aggregate and every per-task outcome that the figures
and tables use, described by field, so plots can be produced without access to the run tree.

Writes:
  results/evidence-packet.json   machine-readable, plot-ready
  results/evidence-packet.md     the same content as prose tables for reading or pasting
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

from analyze_locked_k3 import load_runs  # noqa: E402

OUT_JSON = REPO / "results" / "evidence-packet.json"
OUT_MD = REPO / "results" / "evidence-packet.md"

LOCKED_RUNS = ["deepseek-locked89-k1-v2", "deepseek-locked89-k2-v2", "deepseek-locked89-k3-clean-v1"]
GAP_FILL_RUN = "rerun-missing-k3-v1"
DEV_RUNS = ["deepseek-development-e2e-40-v1", "deepseek-development-e2e-40-low-v1",
            "deepseek-development-e2e-tail-10-low-v1", "deepseek-dev30-contracts-low-v1",
            "deepseek-dev30-v3"]


def per_task(data: dict[str, Any], arm: str) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    for task in sorted(data):
        rewards = [r["reward"] for r in data[task].get(arm, [])]
        verified = [int(r) for r in rewards if r is not None]
        out[task] = {"solved": sum(verified), "verified": len(verified)}
    return out


def arm_totals(data: dict[str, Any], arm: str) -> dict[str, Any]:
    solved = verified = out_tokens = in_tokens = 0
    passed = collected = 0
    work_seconds = 0.0
    for task in sorted(data):
        for record in data[task].get(arm, []):
            out_tokens += record["out"]
            in_tokens += record["in"]
            work_seconds += record["work_seconds"]
            if record["reward"] is None:
                continue
            verified += 1
            solved += int(record["reward"])
            if record["private_collected"]:
                passed += record["private_passed"] or 0
                collected += record["private_collected"]
    return {
        "solved": solved,
        "verified": verified,
        "solve_rate": round(solved / verified, 4) if verified else None,
        "output_tokens": out_tokens,
        "input_tokens": in_tokens,
        "mean_output_tokens_per_attempt": round(out_tokens / verified) if verified else None,
        "mean_work_seconds_per_attempt": round(work_seconds / verified, 1) if verified else None,
        "private_tests_passed": passed,
        "private_tests_collected": collected,
        "private_test_rate": round(passed / collected, 4) if collected else None,
    }


def main() -> int:
    locked = load_runs([REPO / "runs" / name for name in LOCKED_RUNS],
                       gap_fill=REPO / "runs" / GAP_FILL_RUN)
    dev = load_runs([REPO / "runs" / name for name in DEV_RUNS])
    domains = json.loads((REPO / "results" / "benchmark-task-domains.json").read_text())["tasks"]
    strata = json.loads((REPO / "results" / "domain-arm-analysis.json").read_text())
    facts = json.loads((REPO / "results" / "paper-facts.json").read_text())
    matrix = json.loads((REPO / "results" / "complete-30-task-2x2-matrix.json").read_text())
    matched = json.loads((REPO / "results" / "deepseek-2x2-matched-evaluation.json").read_text())

    def domain_table(partition: str) -> list[dict[str, Any]]:
        groups = strata["partitions"][partition]["by_domain"]["groups"]
        rows = []
        for name, row in groups.items():
            rows.append({
                "domain": name,
                "n_tasks": row["n_tasks"],
                "baseline_solved": row["baseline"]["solved"],
                "baseline_verified": row["baseline"]["verified"],
                "cbe_solved": row["cbe"]["solved"],
                "cbe_verified": row["cbe"]["verified"],
                "delta_pp": row["delta_pp"],
            })
        rows.sort(key=lambda item: -item["delta_pp"])
        return rows

    packet = {
        "kind": "swe-bench-science-cbe-evidence-packet",
        "read_me": (
            "Everything a plot needs for the reported experiment. Two arms: 'baseline' uses only "
            "shell tools; 'cbe' adds science_find / science_inspect / science_note over a prepared "
            "evidence store. A solve is the official verifier reward for one attempt. "
            "'verified' counts attempts that produced a verifier verdict; a few attempts were lost "
            "to provider or container failures and are excluded rather than counted as failures."
        ),
        "experiment": {
            "model": "DeepSeek V4.1 Flash",
            "decoding": "temperature 0.0, PYTHONHASHSEED=0, provider seed ignored per provider check",
            "agent_budget_seconds": 1800,
            "verifier_budget_seconds": 1800,
            "network": "none in agent or verifier container",
            "verifier_timing": "runs only after the repair stops; private tests never visible to the agent",
            "benchmark": "SWE-bench Science, all 119 tasks",
            "partitions": {
                "locked89_k3": {"tasks": len(locked), "replicate_runs": 3,
                                "task_ids": sorted(locked)},
                "dev30_k4": {"tasks": len(dev), "replicate_runs": 4, "task_ids": sorted(dev)},
            },
            "context_tools": ["science_find", "science_inspect", "science_note"],
            "preparation": "static: file ranking, Tree-sitter for Python, Joern CPGs for C/C++/Fortran/"
                           "Cython, import and dynamic-binding resolution; no model call, no execution",
        },
        "headline": {
            "locked89_k3": {
                "baseline": arm_totals(locked, "baseline"),
                "cbe": arm_totals(locked, "science"),
                "sign_test_p": facts["locked89_k3"]["comparison"]["sign_test_p"],
                "bootstrap_95ci_pp": [round(100 * value, 1)
                                      for value in facts["locked89_k3"]["comparison"]["bootstrap_95ci"]],
                "tasks_tied": facts["locked89_k3"]["comparison"]["ties"],
                "tasks_cbe_better": facts["locked89_k3"]["comparison"]["science_better"],
                "tasks_baseline_better": facts["locked89_k3"]["comparison"]["baseline_better"],
                "rate_gain_tasks": facts["locked89_k3"]["replication"]["rate_gain_tasks"],
                "rate_loss_tasks": facts["locked89_k3"]["replication"]["rate_loss_tasks"],
            },
            "dev30_k4": {"baseline": arm_totals(dev, "baseline"), "cbe": arm_totals(dev, "science")},
        },
        "by_domain": {
            "locked89_k3": domain_table("locked89_k3"),
            "dev30_k4": domain_table("dev30_k4"),
        },
        "by_task": {
            "locked89_k3": {
                "baseline": per_task(locked, "baseline"),
                "cbe": per_task(locked, "science"),
                "domain": {task: domains[task]["domain"] for task in sorted(domains)},
            },
            "dev30_k4": {"baseline": per_task(dev, "baseline"), "cbe": per_task(dev, "science")},
        },
        "reasoning_effort": {
            "dev30": matrix["matrix_results"],
            "matched20": matched["matrix_success_rates"],
            "note": "high and low effort cells on the same tasks; the low-effort CBE arm recovers "
                    "the two tasks it lost at high effort",
        },
        "replication": {
            "k": 3,
            "note": "counts per task of replicate runs that solved it, held-out partition",
            "histogram": {
                "baseline": {str(k): sum(1 for t, e in per_task(locked, "baseline").items()
                                        if e["solved"] == k) for k in range(4)},
                "cbe": {str(k): sum(1 for t, e in per_task(locked, "science").items()
                                   if e["solved"] == k) for k in range(4)},
            },
        },
    }

    OUT_JSON.write_text(json.dumps(packet, indent=1) + "\n")

    lines = [
        "# Evidence packet — CBE vs baseline on SWE-bench Science",
        "",
        packet["read_me"],
        "",
        f"Model {packet['experiment']['model']}; budget "
        f"{packet['experiment']['agent_budget_seconds']}s per attempt; "
        f"{packet['experiment']['partitions']['locked89_k3']['tasks']} held-out tasks x 2 arms x 3 runs "
        f"and {packet['experiment']['partitions']['dev30_k4']['tasks']} development tasks x 2 arms x 4 runs.",
        "",
        "## Headline (held out)",
        "",
        "| arm | solved | verified | solve rate | output tokens | mean output/attempt | "
        "private tests |",
        "|---|---|---|---|---|---|---|",
    ]
    for arm in ("baseline", "cbe"):
        row = packet["headline"]["locked89_k3"][arm]
        lines.append(
            f"| {arm} | {row['solved']} | {row['verified']} | {row['solve_rate']:.1%} | "
            f"{row['output_tokens'] / 1e6:.2f}M | {row['mean_output_tokens_per_attempt'] / 1000:.1f}k | "
            f"{row['private_tests_passed']}/{row['private_tests_collected']} "
            f"({row['private_test_rate']:.1%}) |")
    lines += ["", "## By scientific domain (held out, k=3)", "",
              "| domain | tasks | baseline | CBE | delta pp |", "|---|---|---|---|---|"]
    for row in packet["by_domain"]["locked89_k3"]:
        lines.append(f"| {row['domain']} | {row['n_tasks']} | "
                     f"{row['baseline_solved']}/{row['baseline_verified']} | "
                     f"{row['cbe_solved']}/{row['cbe_verified']} | {row['delta_pp']:+.1f} |")
    lines += ["", "## By scientific domain (development, k=4)", "",
              "| domain | tasks | baseline | CBE | delta pp |", "|---|---|---|---|---|"]
    for row in packet["by_domain"]["dev30_k4"]:
        lines.append(f"| {row['domain']} | {row['n_tasks']} | "
                     f"{row['baseline_solved']}/{row['baseline_verified']} | "
                     f"{row['cbe_solved']}/{row['cbe_verified']} | {row['delta_pp']:+.1f} |")
    lines += ["", "## Replicate structure (held out)", "",
              "| solves out of 3 | baseline tasks | CBE tasks |", "|---|---|---|"]
    for k in range(4):
        lines.append(f"| {k} | {packet['replication']['histogram']['baseline'][str(k)]} | "
                     f"{packet['replication']['histogram']['cbe'][str(k)]} |")
    lines += ["", "## Reasoning effort", "",
              "| cell | baseline | CBE |", "|---|---|---|"]
    for effort in ("high_effort", "low_effort"):
        lines.append(f"| {effort} | {matrix['matrix_results'][effort]['baseline']} | "
                     f"{matrix['matrix_results'][effort]['science']} |")
    lines += ["", "Per-task rows for both partitions are in `evidence-packet.json` under `by_task` "
              "(solved and verified attempts for every task and arm), together with the domain of "
              "each task.", ""]
    OUT_MD.write_text("\n".join(lines))

    print(f"Wrote {OUT_JSON.relative_to(REPO)} and {OUT_MD.relative_to(REPO)}")
    print(f"  held-out: {packet['headline']['locked89_k3']['baseline']['solved']}"
          f"/{packet['headline']['locked89_k3']['baseline']['verified']} vs "
          f"{packet['headline']['locked89_k3']['cbe']['solved']}"
          f"/{packet['headline']['locked89_k3']['cbe']['verified']}")
    print(f"  dev: {packet['headline']['dev30_k4']['baseline']['solved']}"
          f"/{packet['headline']['dev30_k4']['baseline']['verified']} vs "
          f"{packet['headline']['dev30_k4']['cbe']['solved']}"
          f"/{packet['headline']['dev30_k4']['cbe']['verified']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
