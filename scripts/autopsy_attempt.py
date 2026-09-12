"""Autopsy a single comparison attempt: prompt, guide, patch, tools, reasoning.

Usage: python scripts/autopsy_attempt.py runs/<run>/jobs/task-058-science/task_058__XXXX

Prints the complete diagnostic bundle for one attempt so a failure can be
read as a mechanism (what the model saw, what it did, what it changed),
never as a bare pass/fail verdict.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def read_json(path: Path):
    return json.loads(path.read_text())


def section(title: str):
    print(f"\n{'=' * 70}\n{title}\n{'=' * 70}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("attempt_dir", type=Path)
    args = parser.parse_args()
    base = args.attempt_dir
    agent = base / "agent"

    run = read_json(base / "run.json") if (base / "run.json").is_file() else None
    setup = read_json(agent / "setup.json") if (agent / "setup.json").is_file() else None
    section("ATTEMPT")
    print("path:", base)
    if run:
        print("config:", json.dumps(run.get("config", {}), indent=1))
    if setup:
        print("setup:", {k: setup.get(k) for k in ("agent", "model", "extractor", "frozen_source",
                                                   "extraction_model_call_cap", "max_output_tokens")})

    reward = base / "verifier" / "reward.json"
    if reward.is_file():
        section("VERIFIER OUTCOME")
        data = read_json(reward)
        print("reward:", data.get("reward"), "| resolved:", data.get("resolved"))
        for key in ("public", "private"):
            value = data.get(key) or {}
            print(f"{key}: passed {value.get('passed')}/{value.get('total')} "
                  f"(failed {value.get('failed', 0)}, collected {value.get('collected')})")

    patch = next(base.glob("artifacts/model.patch"), None)
    if patch and patch.is_file():
        section("MODEL PATCH")
        print(patch.read_text()[:4000])
    else:
        section("MODEL PATCH")
        print("(none produced)")

    session = agent / "repair-session.json"
    if session.is_file():
        section("REPAIR SESSION")
        data = read_json(session)
        print("status:", data.get("status"), "| usage:", json.dumps(data.get("usage")))
        for step in data.get("messages", []):
            content = step.get("content") or ""
            reasoning = step.get("reasoning") or ""
            tools = step.get("tool_calls") or []
            print(f"\n-- step {step['step']} finish={step.get('finish_reason')}")
            if reasoning:
                print(f"   reasoning ({len(reasoning)} chars): {reasoning[:400]}")
            if content:
                print(f"   content ({len(content)} chars): {content[:400]}")
            for call in tools:
                print(f"   tool: {call['function']['name']} {call['function'].get('arguments', '')[:300]}")

    tool_log = agent / "tool-outputs.log"
    if tool_log.is_file():
        section("TOOL OUTPUTS (commands + sizes)")
        for line in tool_log.read_text().splitlines():
            if line.startswith("==="):
                print(line[:200])
            else:
                print(f"   ... {len(line)} chars output")

    prompt = agent / "repair-prompt.txt"
    if prompt.is_file():
        section("REPAIR PROMPT (head + guide excerpt)")
        text = prompt.read_text()
        print("total prompt chars:", len(text))
        print(text[:1500])
        guide_marker = "# Scientific working model"
        marker_at = text.find(guide_marker)
        if marker_at >= 0:
            print("\n... guide section ...\n")
            print(text[marker_at:marker_at + 2500])

    extraction = agent / "extraction-phases.json"
    if extraction.is_file():
        section("EXTRACTION")
        data = read_json(extraction)
        print("phases:", [(p["name"], p["status"], round(p.get("duration_seconds", 0), 1))
                          for p in data.get("phases", [])])
        print("pipeline:", data.get("pipeline_status"), "| selected call:", data.get("selected_model_call"))
        print("usage:", json.dumps(data.get("usage")))
        for call in data.get("model_calls", []):
            print("call:", call.get("name"), call.get("status"),
                  "| annotations:", call.get("annotations_status"), "| finish:", call.get("finish_reason"))

    guide = next(agent.glob("**/scientific-guide.md"), None)
    if guide and guide.is_file():
        section("GUIDE (what the science repair actually saw)")
        print(guide.read_text()[:3000])

    trace = agent / "extract-scratch"
    if trace.is_dir():
        run_file = trace / "run.json"
        if run_file.is_file():
            data = read_json(run_file)
            print(f"\ntrace: {data.get('instances')} instances, {data.get('func_keys')} functions, "
                  f"wall {data.get('wall_seconds')}s, shims {data.get('shim_status')}")

    baseline = base.parent / "task-058-baseline"
    print("\n(compare against:", baseline.resolve(), "if the pair is complete)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
