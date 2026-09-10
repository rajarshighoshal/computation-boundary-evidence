#!/usr/bin/env python3
"""Consolidate the fixed initial cohort without hiding interrupted/quota receipts."""
import json
from pathlib import Path

from recompute_results import recompute
from report_comparison import BREAKDOWN, number, read, stage_token_breakdown, table


def main():
    selection = read(Path("configs/random-five-v1.selection.json"))
    sources = [("random-five-v1", "random-five-v1-high"),
               ("random-five-medium-v1", "random-five-medium-v1"),
               ("random-five-medium-resume-v1", "random-five-medium-resume-v1")]
    completed, interrupted = {}, []
    for run_name, summary_name in sources:
        root = Path("runs") / run_name
        summary = read(Path("results") / f"{summary_name}.json")
        assert recompute(root / "jobs") == summary
        for row in summary["trials"]:
            record = {**row, "source_run": run_name}
            if row["status"] != "completed":
                interrupted.append(record)
                continue
            key = row["task_id"], row["condition"]
            if key in completed:
                raise ValueError("Multiple completed attempts: cannot select a best result")
            trial = root / "jobs" / row["trial_path"]
            usage = [stage_token_breakdown(trial, stage) for stage in row["stages"]]
            record["full_token_breakdown"] = {field: sum(u[field] for u in usage)
                if usage and all(u[field] is not None for u in usage) else None for field in BREAKDOWN}
            completed[key] = record
    expected = {(task, arm) for task in selection["task_ids"] for arm in ("baseline", "science")}
    if set(completed) != expected:
        raise ValueError("Original cohort is not fully complete")
    rows = [completed[task, arm] for task in selection["task_ids"] for arm in ("baseline", "science")]
    successes = {arm: sum(completed[task, arm]["exact_private_success"] is True
                         for task in selection["task_ids"]) for arm in ("baseline", "science")}
    discordant = {arm: sum(completed[task, arm]["exact_private_success"] is True
                          and completed[task, "science" if arm == "baseline" else "baseline"]["exact_private_success"] is False
                          for task in selection["task_ids"]) for arm in ("baseline", "science")}
    output = {"kind": "initial_checks_mixed_versions", "task_ids": selection["task_ids"],
              "successes": successes, "single_condition_successes": discordant,
              "completed_trials": rows, "non_completed_receipts": interrupted}
    Path("results/initial-five-overview.json").write_text(json.dumps(output, sort_keys=True, indent=2) + "\n")
    lines = ["# Initial five-task checks", "",
             f"Baseline solved {successes['baseline']}/{len(selection['task_ids'])}; context-assisted repair solved "
             f"{successes['science']}/{len(selection['task_ids'])}. "
             f"Baseline-only successes: {discordant['baseline']}; context-only successes: {discordant['science']}.", "",
             "These exploratory checks used different effort/method revisions and predate the task-local redesign. "
             "They are not a uniform locked experiment or evidence of a general effect. The original draw was retained.", ""]
    table(lines, ["Task", "Effort", "Baseline hidden tests", "Context hidden tests", "Baseline seconds", "Context seconds", "Context handoff"],
          [(task, completed[task, "baseline"]["reasoning_effort"],
            *(f"{completed[task, arm]['private']['passed']}/{completed[task, arm]['private']['collected']}" for arm in ("baseline", "science")),
            *(number(completed[task, arm]["duration_seconds"]) for arm in ("baseline", "science")),
            completed[task, "science"]["extraction_status"]) for task in selection["task_ids"]])
    table(lines, ["Task", "Arm", "Input", "Cached input", "Output", "Reasoning (subset)", "Total"],
          [(row["task_id"], row["condition"], *(number(row["full_token_breakdown"][field], 0)
            for field in ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens", "total_tokens"))) for row in rows])
    lines += ["Input includes cached input; output includes reasoning. Total = input + output. "
              "Times include extraction/handoff but exclude setup and hidden tests. These cost rows cover completed attempts only.", "",
              f"Preserved non-completed receipts: {len(interrupted)}. "
              "The operator stop occurred during an image pull; the subscription-quota failure preceded repair. "
              "They remain in the JSON and original reports, with missing usage unknown rather than zero.", "",
              "Task 058's earlier Git-warning rejection led to repair without its graph. Later checks used native read-only extraction. "
              "The task-local redesign has separate extraction-only tests, not repair results in this table.", "",
              "Reproduce: `python scripts/report_initial_five.py`. Source runs: " + ", ".join(f"`runs/{a}`" for a, _ in sources) + ".", ""]
    Path("docs/INITIAL_FIVE_OVERVIEW.md").write_text("\n".join(lines))
    print(json.dumps({"task_ids": output["task_ids"], "successes": successes, "non_completed_receipts": len(interrupted)}))


if __name__ == "__main__":
    main()
