"""Offline timing analysis and synthetic review counterexamples; never launch a model."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import heapq
import json
import statistics
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace


def read(path):
    return json.loads(path.read_text())


def elapsed(record):
    return (datetime.fromisoformat(record["finished_at"]) -
            datetime.fromisoformat(record["started_at"])).total_seconds()


def run_review(root):
    schedule = read(root / "schedule.json")
    durations, attempts = [], []
    for item in schedule["schedule"]:
        result_path = next((root / "jobs" / f"task-{item['task_id']}-{item['condition']}").glob("*/result.json"))
        result = read(result_path)
        duration = elapsed(result)
        durations.append(duration)
        attempts.append({"task": item["task_id"], "arm": item["condition"], "seconds": duration,
                         "source": str(result_path), "sha256": hashlib.sha256(result_path.read_bytes()).hexdigest()})
    simulations = []
    for width in (6, 8, 20, 30):
        slots = [0.0] * width
        batch = sum(max(durations[i:i + width]) for i in range(0, len(durations), width))
        for duration in durations:
            start = heapq.heappop(slots)
            heapq.heappush(slots, start + duration)
        simulations.append({"workers": width, "batch_minutes": batch / 60,
                            "rolling_minutes": max(slots) / 60,
                            "full_238_attempt_service_hours_lower_bound": 238 * statistics.mean(durations) / width / 3600})
    return {"run": str(root), "schedule_status": schedule["status"], "schedule_minutes": elapsed(schedule) / 60,
            "attempts": attempts, "mean_attempt_minutes": statistics.mean(durations) / 60,
            "max_attempt_minutes": max(durations) / 60, "simulations": simulations,
            "warning": "Counterfactual schedule replay only: fixed observed durations, no pull delays, contention or API changes. "
                       "The 238-attempt extrapolation assumes this five-task development duration mix and is not a forecast."}


def counterexamples():
    import numpy as np
    from scicontext.fingerprint import fingerprint
    from scicontext.relations import _output_relation, derive_loci
    from scicontext.pier_agent import ScientificCodex
    a = np.arange(10000, dtype=np.float64)
    b = a.copy()
    b[100], b[101] = a[101], a[100]
    fa, fb = fingerprint(a), fingerprint(b)
    mismatch = {"bytes_per_array": a.nbytes, "actually_equal": bool(np.array_equal(a, b)),
                "byte_hash_available": fa["exact"] is not None,
                "summary_hash_equal": fa["content"] == fb["content"],
                "classified_as": _output_relation({"return_fp": fa}, {"return_fp": fb})}
    loci = derive_loci([], [], script_report={"status": "workflow_completed",
                     "observation": {"collapse": False, "boundary_difference": 1.0}})["loci"]
    calls = []
    async def helper(command, seconds):
        calls.append(command)
        raise RuntimeError("synthetic trace failure")
    driver = SimpleNamespace(condition="science", root="/app/task_synthetic", task_id="synthetic", _helper=helper)
    trace_failure = None
    try:
        asyncio.run(ScientificCodex.prepare(driver, 1200))
    except RuntimeError as error:
        trace_failure = str(error)
    return {"different_arrays_classified_identical": mismatch,
            "name_based_predicates": [{k: o["properties"][k] for k in ("rule_id", "constraint_type", "status", "predicate_source", "evidence")} for o in loci],
            "trace_failure_fallback": {"error": trace_failure, "helper_calls": len(calls),
                                       "packet_attempted": any(" packet " in c for c in calls)}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, default=Path("runs/dev-five-v5"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--system", action="store_true", help="Read Docker/host resource state without modifying it")
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Preserve prior diagnostics; choose a fresh output")
    result = {"at": datetime.now(timezone.utc).isoformat(), "timing": run_review(args.run),
              "counterexamples": counterexamples(), "model_calls": 0, "candidate_code_executed": False,
              "cloud_example": {"provider": "Hetzner", "plan": "CX53", "region": "Germany/Finland",
                  "usd_hourly_excluding_tax_ipv4": 0.0561, "hours": 24, "base_usd": 0.0561 * 24,
                  "source": "https://docs.hetzner.com/general/infrastructure-and-availability/price-adjustment/",
                  "availability": "Public product page says unavailable; console inventory not verified"}}
    result["source_hashes"] = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in [
        Path("src/scicontext/cli.py"), Path("src/scicontext/pier_agent.py"),
        Path("src/scicontext/relations.py"), Path("src/scicontext/fingerprint.py"), Path("scripts/cost_report.py")]}
    if args.system:
        commands = {"docker_info": ["docker", "info", "--format", '{{.NCPU}} {{.MemTotal}} {{.Architecture}}'],
                    "docker_stats": ["docker", "stats", "--no-stream", "--format", '{{.Name}} | {{.CPUPerc}} | {{.MemUsage}}'],
                    "docker_disk": ["docker", "system", "df"],
                    "host_cpu_ram": ["sysctl", "-n", "hw.ncpu", "hw.memsize"],
                    "host_memory_pressure": ["memory_pressure", "-Q"],
                    "host_disk": ["df", "-h", str(Path.cwd())]}
        result["system"] = {}
        for name, command in commands.items():
            proc = subprocess.run(command, text=True, capture_output=True, timeout=30)
            result["system"][name] = {"command": command, "exit": proc.returncode,
                                      "stdout": proc.stdout, "stderr": proc.stderr}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"timing": {k: v for k, v in result["timing"].items() if k != "attempts"},
                      "counterexamples": result["counterexamples"], "cloud_example": result["cloud_example"]}, indent=2))


if __name__ == "__main__":
    main()
