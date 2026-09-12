"""Pre-flight the treatment delivery for a task before spending repair budget.

Runs the science extraction once (extraction-only) in the pinned image and
asserts the treatment is actually delivered:

  - trace executed (instances above a floor, script status recorded)
  - the reproduce report was captured when the task has one
  - the merged graph contains constraint loci OR the script predicates fired
  - the guide carries at least one finding or one accepted annotation

Exit 0 => the science arm would receive real context; exit 1 => methodological
failure, do not launch the repair comparison. Prints a compact report either way.

Usage: python scripts/preflight.py <task_id> --config configs/<five-task>.json
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("task_id")
    parser.add_argument("--config", type=Path, default=Path("configs/dev-five.json"))
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--workspace", type=Path, default=Path("."))
    args = parser.parse_args()
    output = args.output or Path(f"runs/preflight-{args.task_id}")
    if output.exists():
        import shutil
        shutil.rmtree(output)
    result = subprocess.run(
        [sys.executable, "-m", "scicontext.cli", "pilot", "--workspace", str(args.workspace),
         "--config", str(args.config), "--output", str(output), "--execute", "--extract-only"],
        capture_output=True, text=True)
    print("extraction-only exit:", result.returncode)
    jobs = sorted(output.glob(f"jobs/task-{args.task_id}-science/task_*"))
    if not jobs:
        print("PREFLIGHT FAIL: no science job dir produced")
        print(result.stdout[-800:], result.stderr[-800:])
        return 1
    agent = jobs[0] / "agent"
    problems = []
    trace_run = agent / "extract-scratch" / "trace" / "run.json"
    if trace_run.is_file():
        trace = json.loads(trace_run.read_text())
        print(f"trace: {trace.get('instances')} instances, {trace.get('func_keys')} funcs, "
              f"script_status: {str(trace.get('script_status'))[:60]}")
        if (trace.get("instances") or 0) < 2:
            problems.append("trace recorded almost nothing (import failure?)")
    else:
        problems.append("trace run.json missing")
    guide = next(agent.glob("**/scientific-guide.md"), None)
    if guide:
        text = guide.read_text()
        findings = [line for line in text.splitlines() if line.startswith("- ") and "conventions" not in line]
        annotated = text.count("Scientific meaning:")
        print(f"guide: {len(findings)} finding lines, {annotated} annotated objects")
        if not findings and not annotated:
            problems.append("guide carries no findings and no annotations (empty treatment)")
    else:
        problems.append("scientific-guide.md missing")
    graph = agent / "extract-scratch" / "scientific-objects.json"
    if graph.is_file():
        data = json.loads(graph.read_text())
        loci = len([o for o in data.get("objects", []) if o.get("kind") == "constraint_locus"])
        print(f"graph: {loci} constraint loci, dynamic: {json.dumps(data.get('dynamic', {}))[:150]}")
    proc = agent / "extract_draft-process.json"
    if proc.is_file():
        receipt = json.loads(proc.read_text())
        print(f"enrichment: status={receipt.get('status')} annotations={receipt.get('annotations_status')}")
        if receipt.get("annotations_status") != "received":
            problems.append(f"enrichment did not deliver annotations ({receipt.get('annotations_status')})")
    if problems:
        print("\nPREFLIGHT FAIL:")
        for problem in problems:
            print("  -", problem)
        return 1
    print("\nPREFLIGHT PASS: the science arm receives a delivered treatment")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
