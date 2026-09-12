"""Cost report for a run: measured tokens, cache split, USD at Flash rates.

Rates (official deepseek-flash, checked 2026-09-10, USD per 1M tokens):
  off-peak: cache-hit input 0.003, cache-miss input 0.15, output 0.60
  peak (Mon-Fri 01:00-04:00 and 06:00-10:00 UTC): double all three
Defaults to off-peak; --peak for the worst case.

Usage: python scripts/cost_report.py runs/<run> [--peak]
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

OFF_PEAK = {"cache_hit": 0.003, "cache_miss": 0.15, "output": 0.60}


def attempt_tokens(agent: Path) -> dict:
    tokens = {"cache_hit": 0, "cache_miss": 0, "input": 0, "output": 0}
    session = agent / "repair-session.json"
    if session.is_file():
        usage = json.loads(session.read_text()).get("usage", {}) or {}
        tokens["input"] += usage.get("input_tokens") or 0
        tokens["output"] += usage.get("output_tokens") or 0
        tokens["cache_hit"] += usage.get("cache_hit_tokens") or 0
        tokens["cache_miss"] += usage.get("cache_miss_tokens") or 0
    extraction = agent / "extraction-phases.json"
    if extraction.is_file():
        usage = json.loads(extraction.read_text()).get("usage", {}) or {}
        tokens["input"] += usage.get("input_tokens") or 0
        tokens["output"] += usage.get("output_tokens") or 0
        tokens["cache_hit"] += usage.get("cache_hit_tokens") or 0
        tokens["cache_miss"] += usage.get("cache_miss_tokens") or 0
    return tokens


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--peak", action="store_true", help="bill at peak rates (2x)")
    args = parser.parse_args()
    multiplier = 2.0 if args.peak else 1.0
    totals = {"cache_hit": 0, "cache_miss": 0, "input": 0, "output": 0}
    rows = []
    for job in sorted(args.run_dir.glob("jobs/task-*")):
        agents = list(job.glob("task_*/agent"))
        if not agents:
            continue
        tokens = attempt_tokens(agents[0])
        for key in totals:
            totals[key] += tokens[key]
        rows.append((job.name, tokens))
    unknown_cache = totals["cache_hit"] == 0 and totals["input"] > 0
    if unknown_cache:
        # No cache split recorded: bill all input at the miss rate (worst case).
        cost = (totals["input"] * OFF_PEAK["cache_miss"] + totals["output"] * OFF_PEAK["output"]) / 1_000_000
    else:
        cost = (totals["cache_hit"] * OFF_PEAK["cache_hit"]
                + totals["cache_miss"] * OFF_PEAK["cache_miss"]
                + totals["output"] * OFF_PEAK["output"]) / 1_000_000
    cost *= multiplier
    for name, tokens in rows:
        print(f"{name:<24} in {tokens['input']:>10,} (hit {tokens['cache_hit']:>10,} / miss {tokens['cache_miss']:>9,}) out {tokens['output']:>7,}")
    print(f"\nTOTAL input {totals['input']:,} (cache hit {totals['cache_hit']:,} / miss {totals['cache_miss']:,}) | output {totals['output']:,}")
    print(f"cache split recorded: {not unknown_cache}")
    print(f"estimated cost ({'peak' if args.peak else 'off-peak'}): ${cost:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
