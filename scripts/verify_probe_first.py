#!/usr/bin/env python3
"""Reproduce no-model probe-first verification and preserve machine-derived results."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

from scicontext.extraction import extraction_reserve
from scicontext.io import digest_file, write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="Fresh directory for logs and receipts")
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    workspace = Path(__file__).resolve().parents[1]
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    xml = output / "pytest.xml"
    commands = [
        ("full_suite", [sys.executable, "-m", "pytest", "-q", "--junitxml", str(xml),
                        "--basetemp", str(output / "test-artifacts")]),
        ("original_public_source", [sys.executable, "scripts/check_task_local_extractor.py",
            "--workspace", str(workspace), "--output", str(output / "public-source")]),
        ("historical_comparison", [sys.executable, "scripts/recompute_results.py",
            "runs/task-local-five-v2/jobs", "--verify", "results/task-local-five-v2.json"]),
        ("diff_check", ["git", "diff", "--check"]),
    ]
    receipt = {"kind": "probe_first_no_model_verification", "new_benchmark_model_calls": 0,
        "boundary": "Local fixtures and preserved public source, not live scientific-quality or repair evidence",
        "implementation_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=workspace, text=True).strip(),
        "tracked_diff_before": subprocess.check_output(["git", "diff", "HEAD", "--stat"], cwd=workspace, text=True),
        "script_sha256": digest_file(Path(__file__)), "steps": [],
        "default_work_budget": {"seconds": 300, "code_work_reserve_seconds": extraction_reserve(300),
            "draft_allowance_seconds": 300 - extraction_reserve(300), "old_draft_allowance_seconds": min(240, 300 * .45)}}
    for name, command in commands:
        started = time.monotonic()
        log = output / (name + ".log")
        with log.open("w") as stream:
            result = subprocess.run(command, cwd=workspace, stdout=stream, stderr=subprocess.STDOUT)
        receipt["steps"].append({"name": name, "command": command, "exit_code": result.returncode,
            "seconds": time.monotonic() - started, "log": str(log.relative_to(workspace)),
            "log_sha256": digest_file(log)})
        write_json(args.receipt, receipt)
        print(f"{name}: {'passed' if result.returncode == 0 else 'failed'}", flush=True)
    if xml.is_file():
        suites = list(ET.parse(xml).getroot().iter("testsuite"))
        counts = {key: sum(int(s.get(key, 0)) for s in suites)
                  for key in ("tests", "failures", "errors", "skipped")}
        receipt["pytest"] = {**counts, "passed": counts["tests"] - counts["failures"] - counts["errors"] - counts["skipped"],
                             "artifact": str(xml.relative_to(workspace)), "sha256": digest_file(xml)}
    receipt["status"] = "passed" if all(s["exit_code"] == 0 for s in receipt["steps"]) else "failed"
    write_json(args.receipt, receipt)
    print(json.dumps(receipt, indent=2))
    return 0 if receipt["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
