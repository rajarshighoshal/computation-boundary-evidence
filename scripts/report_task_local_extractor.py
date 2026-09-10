#!/usr/bin/env python3
"""Report extraction quality from preserved development receipts, without repair scoring."""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
from pathlib import Path

from recompute_results import recompute
from report_comparison import (BREAKDOWN, extraction_calls, leaf_token_breakdown, number,
                               optional_object, read, stage_token_breakdown, table)


def counts(items):
    return dict(collections.Counter(item.get("status", "unknown") for item in items)) if isinstance(items, list) else None


def session_metadata(trial, stage=None):
    """Read only session headers; do not copy prompts or model trajectories."""
    result = []
    calls = extraction_calls(stage or {})
    names = [call["name"] for call in calls] if calls is not None else ["extract"]
    paths = [path for name in names for path in (trial / "agent" / f"{name}-sessions").rglob("*.jsonl")]
    for path in sorted(paths):
        with path.open(encoding="utf-8", errors="replace") as stream:
            try:
                event = json.loads(next(stream, "{}"))
            except ValueError:
                continue
        if event.get("type") == "session_meta":
            payload = event.get("payload", {})
            result.append({"path": path.relative_to(trial).as_posix(), **{
                key: payload.get(key) for key in ("id", "cwd", "cli_version", "source", "model_provider")}})
    return result or None


def collect(root):
    schedule = read(root / "schedule.json")
    planned = schedule["schedule"]
    task_ids = [item["task_id"] for item in planned]
    if (schedule.get("kind") != "extraction_verification" or len(set(task_ids)) != len(task_ids)
            or any(item["condition"] != "science" for item in planned)
            or task_ids != schedule["config"]["task_ids"]):
        raise ValueError("Expected one science-only extraction check per configured task")
    raw = {}
    for path in sorted((root / "jobs").rglob("run.json")):
        run = read(path)
        task = str(run["task_id"]).zfill(3)
        stages = run.get("stages", [])
        if (task not in task_ids or task in raw or run.get("condition") != "science"
                or len(stages) > 1 or any(s.get("name") != "extract" for s in stages)
                or (stages and run.get("extraction_only") is not True)):
            raise ValueError("Unexpected task, duplicate attempt, or non-extraction run")
        if any((path.parent / artifact).exists() for artifact in (
                "verifier/reward.json", "verifier/junit.xml", "agent/repair.jsonl")):
            raise ValueError("Extraction-only report cannot include repairs or hidden tests")
        raw[task] = (path.parent, run)
    audited = recompute(root / "jobs")
    summary_paths = [p for p in (root / "summary/summary.json", root / "summary.json") if p.is_file()]
    for path in summary_paths:
        if json.dumps(read(path), sort_keys=True) != json.dumps(audited, sort_keys=True):
            raise ValueError("Summary does not match independent recomputation")
    records = []
    for item in planned:
        task = item["task_id"]
        trial, run = raw.get(task, (None, {}))
        stage = next(iter(run.get("stages", [])), {})
        bundle, graph_status = optional_object(trial / "graph-bundle.json") if trial else ({}, "missing")
        graph = bundle.get("graph")
        digest = None
        if isinstance(graph, dict):
            digest = hashlib.sha256(json.dumps(graph, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
            for expected in (run.get("graph_sha256"), bundle.get("graph_sha256")):
                if expected is not None and expected != digest:
                    raise ValueError(f"Graph hash mismatch: {task}")
            graph_status = "verified" if run.get("graph_sha256") else "missing run hash"
        elif graph_status == "available":
            graph_status = "missing graph object"
        assembly, analysis = bundle.get("assembly") or {}, bundle.get("analysis") or {}
        completed = run.get("status") == "completed" and stage.get("status") == "completed"
        usable = (run.get("extraction_status") == "usable_graph" and bundle.get("validation", {}).get("valid") is True
                  and assembly.get("usable") is True) if completed and graph_status == "verified" else None
        measured = completed and graph_status == "verified"
        accepted = assembly.get("accepted_claim_ids")
        grounding, bindings, alignments = (counts(analysis.get("code_grounding")),
                                          counts(assembly.get("code_bindings")), counts(analysis.get("alignments")))
        metric = lambda value, key: value.get(key, 0) if measured and value is not None else None
        calls = extraction_calls(stage)
        selected = stage.get("selected_model_call") if calls is not None else "extract"
        if calls is not None and selected is not None and selected not in [call["name"] for call in calls]:
            raise ValueError(f"Selected extraction call has no receipt: {task}")
        annotations, annotations_status = (optional_object(trial / "agent" / f"{selected}-final.txt")
                                           if trial and selected else ({}, "missing"))
        probes, probes_status = optional_object(trial / "agent/extract-scratch/probe-results.json") if trial else ({}, "missing")
        setup, setup_status = optional_object(trial / "agent/setup.json") if trial else ({}, "missing")
        records.append({"task_id": task, "schedule_status": item.get("status"), "status": run.get("status", "no receipt"),
                        "completed": completed, "usable_graph": usable, "graph_status": graph_status, "graph_sha256": digest,
                        "seconds": run.get("duration_seconds"), "stage_status": stage.get("status"),
                        "accepted_claims": len(accepted) if measured and isinstance(accepted, list) else None,
                        "source_matched_implementations": metric(grounding, "source_matched"),
                        "matched_quantity_bindings": metric(bindings, "source_matched"),
                        "unknown_alignments": metric(alignments, "unknown"),
                        "tokens": stage_token_breakdown(trial, stage) if trial else dict.fromkeys(BREAKDOWN),
                        "phases": stage.get("phases"), "assembly": assembly or None, "analysis": analysis or None,
                        "annotations_status": annotations_status,
                        "annotation_schema_version": annotations.get("schema_version"),
                        "declared_probes": len(annotations.get("probes", []))
                            if annotations.get("schema_version") == "annotations-1.0"
                            and isinstance(annotations.get("probes", []), list) else None,
                        "probe_receipt_status": probes_status, "probe_results": probes.get("results"),
                        "setup_status": setup_status, "setup": setup or None,
                        "session_metadata": session_metadata(trial, stage) if trial else None,
                        "provenance": {key: run.get(key) for key in (
                            "model", "reasoning_effort", "codex_version", "implementation_revision", "dataset_revision",
                            "benchmark_revision", "environment_image", "prompt_sha256", "selection_sha256", "config")},
                        "trial_path": trial.relative_to(root).as_posix() if trial else None})
        if calls is not None:
            records[-1]["selected_model_call"] = selected
            records[-1]["model_calls"] = [{"name": call["name"], "status": call.get("status"),
                                          "tokens": leaf_token_breakdown(trial, call)} for call in calls]
    return {"kind": "development_extraction_quality", "source_run_root": str(root), "task_ids": task_ids,
            "summary_audit": "verified" if summary_paths else "independently reconstructed; stored summary missing",
            "schedule": schedule, "records": records}


def render(result):
    lines = ["# Task-local extraction checks", "",
             "Development extraction quality only: these checks do not measure repair gains. "
             "No repair or hidden-test artifacts are included. Source matches and quantity bindings establish traceability, "
             "not scientific correctness. Unknown alignments remain unresolved.", "",
             f"Schedule: {result['schedule'].get('status', 'unknown')}. Summary audit: {result['summary_audit']}.", ""]
    records = result["records"]
    table(lines, ["Task", "Status", "Completed", "Usable graph", "Graph receipt", "Seconds", "Accepted claims",
                  "Source-matched implementations", "Matched quantity bindings", "Unknown alignments"],
          [(r["task_id"], r["status"], r["completed"], r["usable_graph"], r["graph_status"], number(r["seconds"]),
            r["accepted_claims"], r["source_matched_implementations"], r["matched_quantity_bindings"], r["unknown_alignments"])
           for r in records])
    table(lines, ["Task", "Input", "Cached input (subset)", "Output", "Reasoning (output subset)", "Total"],
          [(r["task_id"], *(number(r["tokens"][key], 0) for key in (
              "input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens", "total_tokens"))) for r in records])
    lines += ["Total = input + output. Cached input and reasoning are already included. Missing usage and incomplete-stage "
              "costs remain unknown. Missing graphs and incomplete stages do not produce zero quality counts.", ""]
    if any("model_calls" in r for r in records):
        lines += ["Attempted extraction calls are shown below. The task totals above include each call once.", ""]
        table(lines, ["Task", "Call", "Status", "Input", "Cached input (subset)", "Output",
                      "Reasoning (output subset)", "Total"],
              [(r["task_id"], call["name"], call["status"], *(number(call["tokens"][key], 0) for key in (
                  "input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens", "total_tokens")))
               for r in records for call in r.get("model_calls", [])])
    for r in records:
        statuses = counts(r["probe_results"])
        lines.append(f"Task {r['task_id']} probe results: " + (json.dumps(statuses, sort_keys=True)
                     if statuses is not None else "none declared" if r["declared_probes"] == 0 else "unknown") + ".")
    lines += ["", "Probe outcomes describe execution on the original implementation; they are not scientific proof. "
              "The JSON report preserves phases, assembly relations and dependency links when recorded, analysis coverage, "
              "source selection, setup, available session headers, and protocol provenance.", ""]
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--json-output", type=Path, required=True)
    parser.add_argument("--markdown-output", type=Path, required=True)
    args = parser.parse_args(argv)
    result = collect(args.run_root)
    markdown = render(result)
    for path, content in ((args.json_output, json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + "\n"),
                          (args.markdown_output, markdown)):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    main()
