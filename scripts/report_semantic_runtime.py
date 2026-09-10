#!/usr/bin/env python3
"""Report extraction timing, partial usage and sampled memory without running agents."""
import argparse
import datetime as dt
import hashlib
import json
import re
from pathlib import Path

from report_comparison import number, read, table


def memory_bytes(text):
    match = re.fullmatch(r"([0-9.]+)(B|KiB|MiB|GiB|TiB)", text.strip())
    if not match:
        raise ValueError(f"Unknown Docker memory unit: {text}")
    return float(match[1]) * 1024 ** ("B", "KiB", "MiB", "GiB", "TiB").index(match[2])


def partial_usage(trial, call):
    paths = list((trial / "agent" / f"{call['name']}-sessions").rglob("*.jsonl"))
    if len(paths) != 1:
        return {"status": "unavailable_or_ambiguous", "full_cost_known": False}
    last = None
    for line in paths[0].read_text().splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        payload = event.get("payload", {})
        if event.get("type") == "event_msg" and payload.get("type") == "token_count" and payload.get("info"):
            last = {"timestamp": event.get("timestamp"), "usage": payload["info"]["total_token_usage"]}
    if last is None:
        return {"status": "no_counter", "full_cost_known": False}
    u = last["usage"]
    fields = ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens", "total_tokens")
    if (any(type(u.get(k)) is not int or u[k] < 0 for k in fields)
            or u["cached_input_tokens"] > u["input_tokens"]
            or u["reasoning_output_tokens"] > u["output_tokens"]
            or u["total_tokens"] != u["input_tokens"] + u["output_tokens"]):
        raise ValueError("Invalid partial token counter")
    return {"status": "last_observed_cumulative_counter", "full_cost_known": False,
            "timestamp": last["timestamp"], "usage": {k: u[k] for k in fields},
            "source": str(paths[0]), "sha256": hashlib.sha256(paths[0].read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--json-output", type=Path, required=True)
    parser.add_argument("--markdown-output", type=Path, required=True)
    args = parser.parse_args()
    schedule = read(args.run_root / "schedule.json")
    records = []
    for path in sorted((args.run_root / "jobs").glob("*/*/run.json")):
        run = read(path)
        stage = next(s for s in run["stages"] if s["name"] == "extract")
        cap = run["config"]["extraction_seconds"]
        records.append({"task_id": run["task_id"], "stage_status": stage["status"],
            "extraction_status": run.get("extraction_status"), "cap_seconds": cap,
            "elapsed_seconds": run["duration_seconds"],
            "unused_allowance_seconds": max(0, cap - run["duration_seconds"]),
            "selected_model_call": stage.get("selected_model_call"),
            "calls": [{"name": c["name"], "status": c["status"],
                "command_allowance_seconds": c.get("timeout_seconds"),
                "interpretation_elapsed_seconds": c.get("duration_seconds"),
                **({"partial_usage": partial_usage(path.parent, c)} if c["status"] != "completed" else {})}
                for c in stage["model_calls"]]})
    samples = []
    for path in sorted((args.run_root / "resource-samples").glob("*.json")):
        sample = read(path)
        if sample["return_code"]:
            continue
        values = [memory_bytes(c["MemUsage"].split(" / ")[0]) for c in sample["containers"]]
        samples.append({"recorded_at": sample["recorded_at"], "containers": len(values),
                        "approx_reported_memory_bytes": sum(values), "source": str(path),
                        "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    elapsed = (dt.datetime.fromisoformat(schedule["finished_at"]) -
               dt.datetime.fromisoformat(schedule["started_at"])).total_seconds()
    result = {"kind": "extraction_runtime_observations", "run_root": str(args.run_root),
              "schedule_elapsed_seconds": elapsed, "execution_policy": schedule["execution_policy"],
              "records": records, "resource_samples": samples,
              "limitations": "Partial counters are not completed-call/full costs. Sparse Docker samples do not establish actual peak RAM or causal effect of parallelism. No repairs or hidden tests ran."}
    args.json_output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    lines = ["# Semantic extraction: runtime and incomplete usage", "",
             f"Schedule elapsed (including setup and cleanup): {number(elapsed)} seconds.", "",
             "Execution policy: `" + json.dumps(schedule["execution_policy"], sort_keys=True) + "`.", ""]
    table(lines, ["Task", "Extraction stage", "Handoff", "Cap seconds", "Elapsed seconds", "Unused allowance seconds"],
          [(r["task_id"], r["stage_status"], r["extraction_status"], number(r["cap_seconds"]),
            number(r["elapsed_seconds"]), number(r["unused_allowance_seconds"])) for r in records])
    table(lines, ["Task", "Call", "Status", "GNU command allowance seconds", "Interpretation elapsed seconds"],
          [(r["task_id"], c["name"], c["status"], number(c["command_allowance_seconds"]),
            number(c["interpretation_elapsed_seconds"])) for r in records for c in r["calls"]])
    lines += ["## Partial counters—not full costs", "",
              "These are the last observed cumulative session counters before a timeout. Later or in-flight "
              "usage may be absent. Do not substitute these values for the unknown full-stage cost, combine "
              "them into a complete-trial total, or add cached/reasoning subsets twice.", ""]
    table(lines, ["Task", "Call", "Counter timestamp", "Input", "Cached input", "Output", "Reasoning output", "Observed total"],
          [(r["task_id"], c["name"], p.get("timestamp"), *(number(p.get("usage", {}).get(k), 0) for k in
              ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens", "total_tokens")))
           for r in records for c in r["calls"] if (p := c.get("partial_usage"))])
    lines += ["## Resource samples", ""]
    table(lines, ["Time", "Current-trial containers", "Approx. summed reported MiB"],
          [(s["recorded_at"], s["containers"], number(s["approx_reported_memory_bytes"] / 1024**2)) for s in samples])
    lines += ["Summing Docker's rounded CLI values gives approximate container-reported memory, not VM-wide "
              "memory pressure or a guaranteed peak. These sparse samples cannot rule out an unobserved "
              "spike or measure parallel speedup against a matched serial run.", ""]
    args.markdown_output.write_text("\n".join(lines))
    print(f"Generated {args.markdown_output}")


if __name__ == "__main__":
    main()
