"""Export one compact, self-contained brief of the experiment for external review.

Everything a reader (or another model) needs to understand what was done and to see every number
the report uses, in a single Markdown file small enough to paste into a chat window. The fuller
machine-readable packet stays in results/evidence-packet.json for local use.

Writes results/experiment-brief.md
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

from analyze_locked_k3 import load_runs  # noqa: E402

OUT = REPO / "results" / "experiment-brief.md"

LOCKED_RUNS = ["deepseek-locked89-k1-v2", "deepseek-locked89-k2-v2", "deepseek-locked89-k3-clean-v1"]
DEV_RUNS = ["deepseek-development-e2e-40-v1", "deepseek-development-e2e-40-low-v1",
            "deepseek-development-e2e-tail-10-low-v1", "deepseek-dev30-contracts-low-v1",
            "deepseek-dev30-v3"]


def counts(data: dict[str, Any], task: str, arm: str) -> tuple[int, int]:
    rewards = [r["reward"] for r in data.get(task, {}).get(arm, [])]
    verified = [int(r) for r in rewards if r is not None]
    return sum(verified), len(verified)


def main() -> int:
    packet = json.loads((REPO / "results" / "evidence-packet.json").read_text())
    domains = json.loads((REPO / "results" / "benchmark-task-domains.json").read_text())["tasks"]
    locked = load_runs([REPO / "runs" / name for name in LOCKED_RUNS])
    dev = load_runs([REPO / "runs" / name for name in DEV_RUNS])
    headline = packet["headline"]["locked89_k3"]
    dev_head = packet["headline"]["dev30_k4"]

    L: list[str] = []
    add = L.append

    add("# Experiment brief: computation-and-boundary evidence (CBE) for scientific repair")
    add("")
    add("This file is the complete record behind the accompanying report. It states what was done and")
    add("gives every number used, so no other data is required to check or plot it.")
    add("")

    add("## 1. Question")
    add("")
    add("Does giving a repository-level repair agent a prepared, queryable account of a task's")
    add("scientific structure change repair, at the same model, tools and time budget?")
    add("")

    add("## 2. What CBE is")
    add("")
    add("Preparation runs once per task, with no model call and no code execution. Files are ranked so")
    add("that execution evidence and boundary callers precede shallow entry points; Python is parsed")
    add("with Tree-sitter and C, C++, Fortran and Cython with Joern code property graphs, with explicit")
    add("fallback when a frontend is unavailable. The store holds four things:")
    add("")
    add("1. computations: name, path, the source span that anchors the result, expressions;")
    add("2. conditions and findings that guard those computations;")
    add("3. documented public definitions;")
    add("4. call boundaries, each labelled internal, external with a named provider, or unknown.")
    add("")
    add("The agent queries the store through `science_find` (targets and excerpts), `science_inspect`")
    add("(relationships, definitions, source, contracts) and an optional `science_note`. External")
    add("providers are treated as assumed-correct interfaces; unresolved callees are labelled rather")
    add("than guessed. Both arms get identical shell tools; the endpoints add no budget.")
    add("")

    add("## 3. Protocol")
    add("")
    exp = packet["experiment"]
    add(f"- Benchmark: {exp['benchmark']}; {len(locked)} held-out tasks and {len(dev)} development tasks.")
    add(f"- Model: {exp['model']}; {exp['decoding']}.")
    add(f"- Budget: {exp['agent_budget_seconds']} s per attempt for the agent, "
        f"{exp['verifier_budget_seconds']} s for the verifier; {exp['network']}.")
    add(f"- Verifier: {exp['verifier_timing']}.")
    add("- Replicates: 3 runs on the held-out partition, 4 on development; both arms in every run.")
    add("- A solve is the official verifier reward of one attempt. `verified` counts attempts that")
    add("  produced a verdict; the few attempts lost to provider or container failures are excluded,")
    add("  not counted as failures. Rates always carry their denominator.")
    add("- Development tasks were used for iteration; the held-out partition is the only basis for")
    add("  the headline claim.")
    add("")

    add("## 4. Headline result")
    add("")
    add("| partition | baseline | CBE | contrast |")
    add("|---|---|---|---|")
    add(f"| held-out 89, k=3 | {headline['baseline']['solved']}/{headline['baseline']['verified']} "
        f"({headline['baseline']['solve_rate']:.1%}) | {headline['cbe']['solved']}/"
        f"{headline['cbe']['verified']} ({headline['cbe']['solve_rate']:.1%}) | "
        f"{headline['tasks_cbe_better']} tasks better, {headline['tasks_baseline_better']} worse, "
        f"{headline['tasks_tied']} tied |")
    add(f"| development 30, k=4 | {dev_head['baseline']['solved']}/{dev_head['baseline']['verified']} "
        f"({dev_head['baseline']['solve_rate']:.1%}) | {dev_head['cbe']['solved']}/"
        f"{dev_head['cbe']['verified']} ({dev_head['cbe']['solve_rate']:.1%}) | --- |")
    add("")
    add(f"Paired test over the 89 held-out tasks: sign test p = {headline['sign_test_p']:.2f}, "
        f"bootstrap 95% interval for the mean per-task difference "
        f"{headline['bootstrap_95ci_pp'][0]:+.1f} to {headline['bootstrap_95ci_pp'][1]:+.1f} "
        f"percentage points. Parity is the finding, not a null we hid.")
    add("")

    add("## 5. Cost and partial credit (held-out, 522 verified attempts)")
    add("")
    add("| measure | baseline | CBE | change |")
    add("|---|---|---|---|")
    for key, label, scale in (("output_tokens", "output tokens", 1e6),
                              ("input_tokens", "input tokens", 1e6)):
        base = headline["baseline"][key] / scale
        cbe = headline["cbe"][key] / scale
        add(f"| {label} | {base:.2f}M | {cbe:.2f}M | {(cbe / base - 1) * 100:+.1f}% |")
    add(f"| mean output per attempt | {headline['baseline']['mean_output_tokens_per_attempt'] / 1000:.1f}k "
        f"| {headline['cbe']['mean_output_tokens_per_attempt'] / 1000:.1f}k | "
        f"{(headline['cbe']['mean_output_tokens_per_attempt'] / headline['baseline']['mean_output_tokens_per_attempt'] - 1) * 100:+.1f}% |")
    add(f"| agent work per attempt | {headline['baseline']['mean_work_seconds_per_attempt']:.0f} s "
        f"| {headline['cbe']['mean_work_seconds_per_attempt']:.0f} s | "
        f"{headline['cbe']['mean_work_seconds_per_attempt'] - headline['baseline']['mean_work_seconds_per_attempt']:+.0f} s |")
    add(f"| private tests passed | {headline['baseline']['private_tests_passed']}/"
        f"{headline['baseline']['private_tests_collected']} "
        f"({headline['baseline']['private_test_rate']:.1%}) | "
        f"{headline['cbe']['private_tests_passed']}/{headline['cbe']['private_tests_collected']} "
        f"({headline['cbe']['private_test_rate']:.1%}) | "
        f"{(headline['cbe']['private_test_rate'] - headline['baseline']['private_test_rate']) * 100:+.1f} pp |")
    add("")

    add("## 6. By scientific discipline (held-out)")
    add("")
    add("| discipline | tasks | baseline | CBE | delta pp |")
    add("|---|---|---|---|---|")
    for row in packet["by_domain"]["locked89_k3"]:
        add(f"| {row['domain']} | {row['n_tasks']} | {row['baseline_solved']}/{row['baseline_verified']} | "
            f"{row['cbe_solved']}/{row['cbe_verified']} | {row['delta_pp']:+.1f} |")
    add("")
    add("Development partition, same columns:")
    add("")
    add("| discipline | tasks | baseline | CBE | delta pp |")
    add("|---|---|---|---|---|")
    for row in packet["by_domain"]["dev30_k4"]:
        add(f"| {row['domain']} | {row['n_tasks']} | {row['baseline_solved']}/{row['baseline_verified']} | "
            f"{row['cbe_solved']}/{row['cbe_verified']} | {row['delta_pp']:+.1f} |")
    add("")

    add("## 7. Replicate structure (held-out)")
    add("")
    add("| solves out of 3 runs | baseline tasks | CBE tasks |")
    add("|---|---|---|")
    for k in range(4):
        add(f"| {k} | {packet['replication']['histogram']['baseline'][str(k)]} | "
            f"{packet['replication']['histogram']['cbe'][str(k)]} |")
    add("")
    add("Across arms: 15 tasks differ, 18 flip within an arm. A single run cannot resolve a")
    add("difference of a few points on this benchmark.")
    add("")

    add("## 8. Reasoning effort (development tasks)")
    add("")
    add("| cells | baseline | CBE |")
    add("|---|---|---|")
    for effort in ("high_effort", "low_effort"):
        cell = packet["reasoning_effort"]["dev30"][effort]
        add(f"| {effort.replace('_', ' ')} (30 tasks) | {cell['baseline']} | {cell['science']} |")
    for effort in ("high_effort", "low_effort"):
        cell = packet["reasoning_effort"]["matched20"][effort]
        add(f"| {effort.replace('_', ' ')} (matched 20) | {cell['baseline']} | {cell['science']} |")
    add("")
    add("The two tasks the CBE arm gains under low effort (002, 009) are the two it lost at high")
    add("effort, which is what external evidence substituting for deliberation looks like.")
    add("")

    add("## 9. Which tasks move, and the per-task data")
    add("")
    add(f"CBE gains on: {', '.join(headline['rate_gain_tasks'])}. "
        f"It loses on: {', '.join(headline['rate_loss_tasks'])}.")
    add("")
    add("Task 103 (pyNastran, stiffness matrices of a symmetric composite laminate) is solved 2 of 3")
    add("times with CBE and 0 of 3 without; the recorded trajectory inspects the ply-angle computation")
    add("and its library boundaries before editing. Task 022 (nilearn, volume-to-surface projection) is")
    add("the mirror image: 2 of 3 with the baseline, 0 of 3 with CBE, where the trajectory reasoned")
    add("about projection mathematics before touching the atlas label mapping the instruction describes.")
    add("")
    add("Complete per-task outcomes, held out (task, discipline, baseline solved/verified, CBE")
    add("solved/verified). Every held-out task appears; runs = 3 per arm.")
    add("")
    add("| task | discipline | baseline | CBE |")
    add("|---|---|---|---|")
    for task in sorted(locked):
        base_solved, base_verified = counts(locked, task, "baseline")
        cbe_solved, cbe_verified = counts(locked, task, "science")
        add(f"| {task} | {domains[task]['domain']} | {base_solved}/{base_verified} | "
            f"{cbe_solved}/{cbe_verified} |")
    add("")
    add("Development tasks (4 runs per arm):")
    add("")
    add("| task | baseline | CBE |")
    add("|---|---|---|")
    for task in sorted(dev):
        base_solved, base_verified = counts(dev, task, "baseline")
        cbe_solved, cbe_verified = counts(dev, task, "science")
        add(f"| {task} | {base_solved}/{base_verified} | {cbe_solved}/{cbe_verified} |")
    add("")

    add("## 10. What the figures must and must not do")
    add("")
    add("- Do **not** draw confidence intervals or error bars: with 2-3 attempts per task they are")
    add("  decoration. Annotate counts (`0/3 -> 2/3`) or percentage-point differences instead.")
    add("- Keep the encoding fixed paper-wide: baseline arm = circle; CBE arm = square; blue for the")
    add("  baseline, teal when CBE improves something, rust when it worsens something.")
    add("- One figure = one claim, stated in the caption's first sentence.")
    add("- Type: serif, nothing below 6 pt at design size; design at 5.5 in wide and let the report")
    add("  place it at 6.5 in, or design at 6.5 in and place at natural size. Never shrink a figure.")
    add("- No number may be typed into plot code: read it from this file or the receipts.")
    add("")

    OUT.write_text("\n".join(L) + "\n")
    size_kb = OUT.stat().st_size / 1024
    print(f"Wrote {OUT.relative_to(REPO)} ({size_kb:.1f} KB, {len(L)} lines)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
