"""Audit delivered context and successful artifact-reference commands; no model calls.

These are delivery/access measurements, not proof of understanding or causal benefit.
Only schedule-finalized science attempts are included; private assertion bodies are not read.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


FILES = ("scientific-guide.md", "scientific-graph.json", "scientific-sources.json", "scientific-model.json")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--tasks", nargs="+")
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Preserve prior audit receipts; choose a fresh output")
    schedule = json.loads((args.run_root / "schedule.json").read_text())
    rows = []
    for item in schedule["schedule"]:
        if item["condition"] != "science" or item["status"] != "completed":
            continue
        if args.tasks and item["task_id"] not in args.tasks:
            continue
        trials = list((args.run_root / "jobs" / f"task-{item['task_id']}-science").glob("task_*"))
        if len(trials) != 1:
            raise ValueError(f"Ambiguous trial: {item['task_id']}")
        agent = trials[0] / "agent"
        prompt_path = agent / "repair-prompt.txt"
        guide_path = agent / "repair-context-scientific-guide.md"
        graph_path = agent / "repair-context-scientific-graph.json"
        log_path = agent / "repair.jsonl"
        required = (prompt_path, guide_path, graph_path, log_path)
        missing = [str(p) for p in required if not p.is_file()]
        if missing:
            rows.append({"task_id": item["task_id"], "status": "missing_artifacts", "missing": missing})
            continue
        prompt, guide = prompt_path.read_text(), guide_path.read_text()
        graph = json.loads(graph_path.read_text())
        annotated = [o for o in graph.get("objects", []) if o.get("interpretation")]
        shown = [o for o in annotated if f"## {o['id']} " in guide]
        model = graph.get("scientific_model", {})
        computations = model.get("computations", [])
        displayed = [c for c in computations if f"Computation: {c['id']} " in guide]
        source_map = {s["id"]: s for s in model.get("sources", [])}
        references = {name: [] for name in FILES}
        for line in log_path.read_text().splitlines():
            try:
                event = json.loads(line)
            except ValueError:
                continue
            data = event.get("item", {})
            if event.get("type") != "item.completed" or data.get("type") != "command_execution":
                continue
            if data.get("exit_code") != 0:
                continue
            for name in FILES:
                if name in data.get("command", ""):
                    references[name].append({"call_id": data.get("id"), "command": data["command"],
                        "returned_chars": len(data.get("aggregated_output", ""))})
        rows.append({"task_id": item["task_id"], "status": "audited", "trial": str(trials[0]),
            "prompt_bytes": prompt_path.stat().st_size, "guide_bytes": guide_path.stat().st_size,
            "guide_is_inline": bool(guide) and guide in prompt,
            "annotated_objects": len(annotated), "guide_objects": len(shown),
            "annotated_computations": len(computations), "guide_computations": len(displayed),
            "computation_source_paths": sorted({source_map[i]["path"] for c in computations for i in c["source_ids"]}),
            "guide_computation_source_paths": sorted({source_map[i]["path"] for c in displayed for i in c["source_ids"]}),
            "all_annotation_paths": dict(collections.Counter(o["path"] for o in annotated)),
            "guide_annotation_paths": dict(collections.Counter(o["path"] for o in shown)),
            "successful_artifact_reference_commands": references,
            "artifact_sha256": {str(p): digest(p) for p in required}})
    result = {"at": datetime.now(timezone.utc).isoformat(), "run_root": str(args.run_root),
        "implementation_revision": schedule.get("implementation_revision"),
        "selection": "Specified diagnostic cases" if args.tasks else "All finalized science attempts at capture",
        "interpretation_limit": "Inline delivery and successful commands referencing files do not prove full reading, understanding, scientific correctness, or causal benefit.",
        "records": rows}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    for row in rows:
        print(json.dumps({k: v for k, v in row.items() if k not in ("artifact_sha256", "trial", "successful_artifact_reference_commands")}))


if __name__ == "__main__":
    main()
