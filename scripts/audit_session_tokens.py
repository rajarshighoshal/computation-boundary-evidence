#!/usr/bin/env python3
"""Independently check completed CLI turns against saved cumulative session counters."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


FIELDS = ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens")


def events(path):
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            value = json.loads(line)
        except ValueError:
            continue
        if isinstance(value, dict):
            yield value


def audit_stage(trial, stage):
    if "model_calls" in stage:
        calls = stage["model_calls"]
        if (stage.get("name") != "extract" or not isinstance(calls, list)
                or any(not isinstance(call, dict) or "model_calls" in call for call in calls)
                or [call.get("name") for call in calls] not in (
                    [], ["extract_draft"], ["extract_draft", "extract_revision"])):
            raise ValueError("Malformed extraction model_calls: expected draft and optional revision once each")
        leaves = [audit_leaf(trial, call, allow_missing=True) for call in calls]
        result = {"stage": "extract", "model_calls": leaves}
        if stage.get("status") != "completed" or not leaves or any(
                leaf["status"] != "verified" for leaf in leaves):
            return {**result, "status": "unknown_incomplete_stage"}
        totals = {field: sum(leaf["usage"][field] for leaf in leaves) for field in leaves[0]["usage"]}
        recorded = stage.get("usage") or {}
        if any(type(recorded.get(field)) is not int or recorded[field] < 0 for field in FIELDS[:3]):
            return {**result, "status": "unknown_missing_usage"}
        if any(recorded[field] != totals[field] for field in FIELDS[:3]) or (
                recorded.get("reasoning_output_tokens") is not None
                and recorded["reasoning_output_tokens"] != totals["reasoning_output_tokens"]):
            raise ValueError(f"Extraction aggregate receipt differs from raw usage: {trial}")
        return {**result, "status": "verified", "usage": totals}
    return audit_leaf(trial, stage)


def audit_leaf(trial, stage, *, allow_missing=False):
    name = stage["name"]
    if stage.get("status") != "completed":
        return {"stage": name, "status": "unknown_incomplete_stage"}
    raw = trial / "agent" / f"{name}.jsonl"
    sessions = sorted((trial / "agent" / f"{name}-sessions").rglob("*.jsonl"))
    if allow_missing and (not raw.is_file() or not sessions):
        return {"stage": name, "status": "unknown_missing_artifacts"}
    if len(sessions) != 1:
        raise ValueError(f"Expected one session for independent accounting, found {len(sessions)}: {trial}/{name}")
    session_events = list(events(sessions[0]))
    metadata = [e["payload"] for e in session_events if e.get("type") == "session_meta"]
    if len(metadata) != 1 or metadata[0].get("source") != "exec":
        raise ValueError(f"Unexpected session origin: {sessions[0]}")
    counters = [e["payload"]["info"]["total_token_usage"] for e in session_events
                if e.get("type") == "event_msg" and e.get("payload", {}).get("type") == "token_count"
                and e["payload"].get("info")]
    usages = [e.get("usage") for e in events(raw) if e.get("type") == "turn.completed"]
    if allow_missing and (not counters or not usages or any(
            not isinstance(u, dict) or any(type(u.get(field)) is not int or u[field] < 0 for field in FIELDS)
            for u in usages) or any(type((stage.get("usage") or {}).get(field)) is not int
                                  for field in FIELDS[:3])):
        return {"stage": name, "status": "unknown_missing_usage"}
    if not counters or not usages:
        raise ValueError(f"Missing token counters: {trial}/{name}")
    if any(type(u.get(field)) is not int or u[field] < 0 for u in usages for field in FIELDS):
        raise ValueError(f"Incomplete completed-turn usage: {raw}")
    totals = {field: sum(u[field] for u in usages) for field in FIELDS}
    totals["total_tokens"] = totals["input_tokens"] + totals["output_tokens"]
    if any(counters[-1].get(field) != value for field, value in totals.items()):
        raise ValueError(f"CLI and cumulative session usage disagree: {trial}/{name}")
    if any(stage.get("usage", {}).get(field) != totals[field] for field in FIELDS[:3]):
        raise ValueError(f"Stage receipt differs from raw usage: {trial}/{name}")
    if allow_missing and stage["usage"].get("reasoning_output_tokens") is not None and (
            stage["usage"]["reasoning_output_tokens"] != totals["reasoning_output_tokens"]):
        raise ValueError(f"Stage receipt differs from raw usage: {trial}/{name}/reasoning_output_tokens")
    if any(u["cached_input_tokens"] > u["input_tokens"] or u["reasoning_output_tokens"] > u["output_tokens"] for u in usages):
        raise ValueError(f"Invalid token subsets: {trial}/{name}")
    totals["uncached_input_tokens"] = totals["input_tokens"] - totals["cached_input_tokens"]
    totals["nonreasoning_output_tokens"] = totals["output_tokens"] - totals["reasoning_output_tokens"]
    return {"stage": name, "status": "verified", "usage": totals,
            "cli_log": str(raw), "session_file": str(sessions[0]),
            "cli_sha256": hashlib.sha256(raw.read_bytes()).hexdigest(),
            "session_sha256": hashlib.sha256(sessions[0].read_bytes()).hexdigest()}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    records = []
    for path in sorted((args.run_root / "jobs").glob("*/*/run.json")):
        run = json.loads(path.read_text())
        for stage in run.get("stages", []):
            records.append({"task_id": run["task_id"], "condition": run["condition"],
                            **audit_stage(path.parent, stage)})
    if not records:
        raise ValueError("No stage receipts found")
    result = {"run_root": str(args.run_root),
              "method": "Completed-turn usage independently matched to final cumulative exec-session counters; subsets are not added twice",
              "records": records}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"Audited {sum(r['status'] == 'verified' for r in records)} stages; "
          f"{sum(r['status'] != 'verified' for r in records)} unknown: {args.output}")


if __name__ == "__main__":
    main()
