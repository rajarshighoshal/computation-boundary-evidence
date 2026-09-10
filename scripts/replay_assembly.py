#!/usr/bin/env python3
"""Replay saved annotations through graph assembly only; never call a model."""
import argparse
import json
import platform
import subprocess
import sys
import time
from pathlib import Path

from scicontext.io import digest_file, read_json, write_json
from scicontext.packet import build_packet


def write_report(record, destination):
    lines = ["# Assembly timeout fix", "",
             "The exact saved annotations were replayed in the original pinned scientific environment. "
             "Only graph assembly ran: no model calls, repair, scientific probes or hidden tests.", "",
             "| Allocation | Allowance seconds | Actual seconds | Exit code | Usable graph |",
             "| --- | ---: | ---: | ---: | --- |"]
    for result in record["results"]:
        lines.append(f"| {result['label']} | {result['allowance_seconds']:.2f} | "
                     f"{result['elapsed_seconds']:.2f} | {result['return_code']} | {result['usable']} |")
    lines += ["", f"Overall extraction cap: {record['extraction_cap_seconds']:.0f}s; "
              f"unchanged collection/shutdown reserve: {record['collection_shutdown_reserve_seconds']:.0f}s. "
              f"The shared work allowance is {record['work_budget_seconds']:.0f}s.", "",
              "The old allocation terminated the helper before it finished. The corrected allocation "
              "uses the work time remaining after interpretation, without spending the outer cleanup reserve. "
              "This verifies the saved failure case, not a guarantee that every extraction fits its total budget.", "",
              "The benchmark comparison remains stopped at the user's request. Raw replay inputs, outputs "
              "and commands are preserved under `runs/assembly-budget-replay-v1/`.", ""]
    destination.write_text("\n".join(lines))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    metadata = read_json(args.input / "replay-input.json")
    args.output.mkdir(parents=True, exist_ok=True)
    packet = build_packet(args.root, args.input / "context")
    packet["task_id"] = metadata["task_id"]
    phase = next(p for p in metadata["failed_phases"]["phases"] if p["name"] == "assemble_initial")
    extraction_cap = metadata["extraction_seconds"]
    reserve = min(60.0, extraction_cap / 6)
    work_budget = extraction_cap - reserve
    remaining = work_budget - phase["started_offset_seconds"]
    results = []
    for label, allowance in (("old_limit", phase["allowance_seconds"]), ("remaining_budget", remaining)):
        packet_path = args.output / f"{label}-packet.json"
        bundle_path = args.output / f"{label}-bundle.json"
        write_json(packet_path, packet)  # Cold pre-assembly packet for each replay.
        command = ["timeout", "--signal=TERM", "--kill-after=2s", f"{max(.05, allowance - 3)}s",
                   sys.executable, "-m", "scicontext.tool_cli", "assemble", "--root", str(args.root),
                   "--context-root", str(args.input / "context"), "--packet", str(packet_path),
                   "--annotations", str(args.input / "annotations.json"), "--output", str(bundle_path)]
        started = time.monotonic()
        process = subprocess.run(command, capture_output=True, text=True, timeout=allowance + 2)
        elapsed = time.monotonic() - started
        (args.output / f"{label}-stdout.txt").write_text(process.stdout)
        (args.output / f"{label}-stderr.txt").write_text(process.stderr)
        try:
            response = json.loads(process.stdout)
        except ValueError:
            response = {}
        results.append({"label": label, "allowance_seconds": allowance, "elapsed_seconds": elapsed,
                        "return_code": process.returncode, "status": response.get("status"),
                        "usable": response.get("usable", False), "command": command,
                        "bundle": str(bundle_path), "graph_sha256": response.get("graph_sha256")})
    fixed = results[-1]
    record = {"kind": "assembly_budget_replay", "model_calls": 0,
              "python": platform.python_version(), "machine": platform.machine(),
              "annotations_sha256": digest_file(args.input / "annotations.json"),
              "input_metadata": metadata, "extraction_cap_seconds": extraction_cap,
              "collection_shutdown_reserve_seconds": reserve, "work_budget_seconds": work_budget,
              "projected_work_seconds": phase["started_offset_seconds"] + fixed["elapsed_seconds"],
              "results": results,
              "verified": fixed["return_code"] == 0 and fixed["usable"]
                          and fixed["elapsed_seconds"] < remaining}
    write_json(args.output / "replay-result.json", record)
    write_report(record, args.output / "report.md")
    print(json.dumps({k: record[k] for k in ("verified", "projected_work_seconds", "results")}, indent=2))
    return 0 if record["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
