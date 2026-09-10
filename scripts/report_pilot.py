#!/usr/bin/env python3
"""Generate quantitative pilot prose/tables from independently checked receipts."""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import hashlib
import json
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", type=Path, default=Path("runs/pilot-v2"))
    parser.add_argument("--summary", type=Path, default=Path("results/pilot-v2.json"))
    parser.add_argument("--output", type=Path, default=Path("docs/PILOT_RESULTS.md"))
    args = parser.parse_args()
    subprocess.run([sys.executable, str(Path(__file__).with_name("recompute_results.py")),
                    str(args.run_root / "jobs"), "--verify", str(args.summary)], check=True)
    summary = json.loads(args.summary.read_text())
    schedule = json.loads((args.run_root / "schedule.json").read_text())
    rows = {(r["task_id"], r["condition"]): r for r in summary["trials"]}
    metrics = summary["metrics"]["all"]["conditions"]
    totals = {name: values["resources"]["duration_seconds"]["observed_total"]
              for name, values in metrics.items()}
    baseline, science = metrics["baseline"], metrics["science"]
    lines = ["# Development pilot: results", "",
             f"Baseline succeeded on {baseline['exact_private_successes']}/{baseline['attempts']} tasks; "
             f"context succeeded on {science['exact_private_successes']}/{science['attempts']}. "
             "This development pilot is too small for a general effectiveness claim.", "",
             "## Verifier outcomes and time", "",
             "| Task | Baseline private tests | Context private tests | Baseline minutes | Context minutes |",
             "| --- | --- | --- | ---: | ---: |"]
    for task in summary["task_ids"]:
        a, b = rows[task, "baseline"], rows[task, "science"]
        scores = [f"{r['private']['passed']}/{r['private']['collected']}" for r in (a, b)]
        lines.append(f"| {task} | {scores[0]} | {scores[1]} | {a['duration_seconds']/60:.1f} | {b['duration_seconds']/60:.1f} |")
    all_public = all(r["public"]["passed"] == r["public"]["collected"] and r["public"]["return_code"] == 0 for r in rows.values())
    wall = (dt.datetime.fromisoformat(schedule["finished_at"]) - dt.datetime.fromisoformat(schedule["started_at"])).total_seconds()
    increase = 100 * (totals["science"] / totals["baseline"] - 1)
    delta = summary["metrics"]["all"]["observed_paired_success_delta_percentage_points"]
    overruns = sum(r["over_budget_seconds"] > 0 for r in rows.values())
    lines += ["", f"All public checks passed: {all_public}. Official rewards: " + ", ".join(
        f"{r['task_id']}/{r['condition']}={r['official_reward']}" for r in summary["trials"]) + ".",
        f"Paired success difference: {delta:.1f} percentage points on {len(summary['pairs'])} pairs. No significance claim is made.", "",
        "Times are measured agent-phase totals, including extraction/handoff where applicable, excluding environment preparation and official verification. "
        f"Aggregate time was {totals['baseline']/60:.2f} minutes for baseline and {totals['science']/60:.2f} for context "
        f"({increase:.1f}% more). The full serialized pilot took {wall/60:.2f} minutes. Trials exceeding the total allowance: {overruns}.", "",
        "## Extraction and mechanical coverage", ""]
    for task in summary["task_ids"]:
        row = rows[task, "science"]
        trial = args.run_root / "jobs" / row["trial_path"]
        bundle = json.loads((trial / "graph-bundle.json").read_text())
        check = json.loads((trial / "agent/extraction-source-check.json").read_text())
        coverage = bundle["analysis"]["coverage"]
        grounding = collections.Counter(x["status"] for x in bundle["analysis"]["code_grounding"])
        alignment = collections.Counter(x["status"] for x in bundle["analysis"]["alignments"])
        stage = next(s for s in row["stages"] if s["name"] == "extract")
        lines += [f"### Task {task}", "",
                  f"Extraction status: `{stage['status']}` after {stage['duration_seconds']:.2f}s; handoff: `{row['extraction_status']}`. "
                  f"Source changed: {check['source_changed']}. Graph nodes: " + ", ".join(f"{len(bundle['graph'][k])} {k}" for k in ("claims", "quantities", "evidence", "observations")) + ".",
                  f"Source-corroborated implementation expressions: {grounding['source_matched']}. "
                  f"Alignments: {alignment['match']} matching, {alignment['mismatch']} differing, {alignment['unknown']} unknown. "
                  f"Supported semantic lifting: {coverage['lift_supported']}; dimensions resolved: {coverage['dimension_resolved']}; "
                  f"scales resolved: {coverage['scale_resolved']}; shapes resolved: {coverage['shape_resolved']}.", ""]
    lines += ["These counters are not correctness proofs. They include properties propagated through LLM-supplied scientific relations, not only implementation expressions. "
              "In the physics case, the threshold dimensional conflict was partly a literal-representation limitation, explicitly qualified in the graph. "
              "In geometry, only an alias was source-corroborated; the underlying engine was opaque to the index.", "",
              "Both geometry repairs independently implemented exact integer-lattice geometry. Baseline preserved modern-engine dispatch; context used its local implementation throughout. "
              "Both physics repairs addressed units and spin-density handling; context additionally parsed electronic-state metadata. These descriptive differences do not establish causal benefit or superiority.", "",
              "## Timing and measurement limitations", "",
              "The saved checkpoints were usable despite extraction cutoffs. Asking the extractor to repeat the full graph as its final response duplicates a validated artifact. "
              "A firmer stopping rule and a short checkpoint identifier are proposed before increasing the cap; see [pilot notes](PILOT_NOTES.md). No such change was applied mid-pilot.", "",
              f"Full context-condition input-token totals are unavailable for {science['resources']['input_tokens']['missing_trials']}/{science['attempts']} trials, "
              "because interrupted extractions emitted no completed-turn totals. Unknown is not zero; repair-only usage must not be presented as total method cost. Raw sessions are preserved. "
              "Fail2Pass/Pass2Pass remain unavailable without matching original-baseline per-test records.", "",
              "## Protocol and evidence", "",
              "Evaluated task IDs: **" + ", ".join(summary["task_ids"]) + "**. Both are development cases; prior private-test exposure: " + ", ".join(summary["exposure"]["prior_private_test_exposure"]) + ".",
              f"Model: {schedule['config']['model']}/{schedule['config']['reasoning_effort']}; Codex {schedule['config']['codex_version']}; Pier {schedule['config']['pier_version']}. "
              f"Total allowance {schedule['config']['total_seconds']}s; extraction cap {schedule['config']['extraction_seconds']}s including validation/handoff. "
              f"Attempts per condition: {schedule['config']['attempts']}; concurrency: {schedule['config']['concurrency']}.",
              "Order: " + " → ".join(f"{x['task_id']}/{x['condition']}" for x in schedule["schedule"]) + ".",
              f"Evaluated implementation: `{schedule['implementation_revision']}`. Prompts/settings were unchanged during the pilot. Standard Docker execution and subscription auth were used; no API-key fallback.", "",
              "Pinned dataset/benchmark revisions, images, prompt/config hashes and exact trial paths are in [the committed summary](../results/pilot-v2.json). "
              "Raw records remain under `runs/pilot-v2/`; the earlier interrupted pilot is preserved separately and not pooled. No full-benchmark run was started."]
    for row in rows.values():
        patch = args.run_root / "jobs" / row["trial_path"] / "artifacts/model.patch"
        if hashlib.sha256(patch.read_bytes()).hexdigest() != row["patch_sha256"]:
            raise ValueError("Candidate patch hash changed")
    setup = json.loads((args.run_root / "jobs" / next(iter(rows.values()))["trial_path"] / "agent/setup.json").read_text())
    lines += ["", f"Docker exposed {setup['docker_memory_bytes']/1024**3:.2f} GiB versus the task's requested {setup['task_requested_memory_mb']/1024:.0f} GiB. "
              "Successful development runs do not establish full-benchmark resource feasibility or parity with published runs.", "",
              f"Independent reconstruction verified {len(rows)} trials and {len(summary['pairs'])} pairs; all candidate patch hashes were checked. "
              "This document's quantitative text and tables are generated from the preserved records.", "",
              "```bash", "uv run --no-sync python scripts/report_pilot.py", "```"]
    args.output.write_text("\n".join(lines) + "\n")
    print(f"Generated {args.output}")


if __name__ == "__main__":
    main()
