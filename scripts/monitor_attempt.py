"""Live monitor for a dev run: one compact line per poll per attempt.

Usage: python scripts/monitor_attempt.py runs/dev-058-science-v1 [--interval 45]

Watches the schedule plus, for each attempt, its extraction phases, repair
session progress (tool calls, tokens), and any recorded error - so failures
are visible while they happen, not after the run ends.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path


def attempt_state(run_dir: Path, task: str, condition: str) -> str:
    import glob
    jobs = list(run_dir.glob(f"jobs/task-{task}-{condition}/task_*"))
    if not jobs:
        return "no job dir yet"
    agent = jobs[0] / "agent"
    parts = [f"{task}/{condition}"]
    phases_path = agent / "extraction-phases.json"
    if phases_path.is_file():
        phases = json.loads(phases_path.read_text())
        parts.append("ext:" + "/".join(f"{p['name'][:4]}:{p['status'][:1]}"
                                       for p in phases.get("phases", [])))
    session_path = agent / "repair-session.json"
    if session_path.is_file():
        session = json.loads(session_path.read_text())
        usage = session.get("usage", {})
        parts.append(f"steps:{len(session.get('messages', []))} "
                     f"in:{usage.get('input_tokens', 0)} out:{usage.get('output_tokens', 0)}")
        steps = session.get("messages", [])
        if steps:
            last = steps[-1]
            calls = last.get("tool_calls") or []
            if calls:
                command = calls[-1].get("function", {}).get("arguments", "")
                parts.append(f"tool:{command[:60]}")
            elif last.get("content"):
                parts.append("final-text")
    tool_log = agent / "tool-outputs.log"
    if tool_log.is_file():
        count = sum(1 for line in tool_log.read_text().splitlines() if line.startswith("==="))
        parts.append(f"tools:{count}")
    result_path = jobs[0] / "result.json"
    if result_path.is_file():
        result = json.loads(result_path.read_text())
        exception = result.get("exception") or {}
        message = exception.get("message", "") if isinstance(exception, dict) else str(exception)
        parts.append(f"END:{message[:80]}" if message else "END")
    return " | ".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--interval", type=int, default=45)
    args = parser.parse_args()
    schedule_path = args.run_dir / "schedule.json"
    if not schedule_path.is_file():
        print(f"no schedule at {schedule_path}")
        return 1
    schedule = json.loads(schedule_path.read_text())
    items = schedule["schedule"]
    seen: dict = {}
    while True:
        lines = []
        for item in items:
            state = attempt_state(args.run_dir, item["task_id"], item["condition"])
            key = state[:120]
            if seen.get(item["condition"] + item["task_id"]) != key:
                lines.append(state)
                seen[item["condition"] + item["task_id"]] = key
        if lines:
            print(f"--- {time.strftime('%H:%M:%S')} ---")
            for line in lines:
                print(" ", line)
        finished = all((args.run_dir / f"task-{i['task_id']}-{i['condition']}-runner.log").exists()
                       for i in items) and all(
            (args.run_dir / "jobs" / f"task-{i['task_id']}-{i['condition']}" / "result.json").exists()
            for i in items)
        done = all(any((args.run_dir / "jobs" / f"task-{i['task_id']}-{i['condition']}").glob("task_*/result.json"))
                   for i in items)
        if done:
            print("--- all attempts finished ---")
            break
        time.sleep(args.interval)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
