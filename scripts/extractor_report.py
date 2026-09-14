"""Summarize an extraction-only validation sweep (no model calls).

Reads runs/<name>/jobs/*/task_*/ receipts and exported science stores and
reports per-task graph quality: construction status, node/edge/finding
counts, reproduction classification, node grounding, and the in-container
self-check (query path, record/refuse, expansion).

Usage: python scripts/extractor_report.py runs/extractor-validation-30
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def load(path: Path):
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text())
    except ValueError:
        return None


def task_row(job: Path) -> dict:
    run = load(job / "run.json") or {}
    agent = job / "agent"
    prepare = next((s for s in run.get("stages", []) if s.get("name") == "prepare"), {})
    index = prepare.get("index") or {}
    graph = index.get("scientific_graph") or {}
    construction = prepare.get("construction") or {}
    store = load(agent / "science" / "state.json") or {}
    stored = store.get("scientific_graph") or {}
    nodes = stored.get("nodes") or []
    grounded = [n for n in nodes if n.get("source_ids")]
    citable = [n for n in nodes if n.get("computation_id")]
    self_check = load(agent / "self-check.json") or index.get("self_check") or {}
    steps = self_check.get("steps") or {}
    reproduction = stored.get("reproduction") or {}
    merged = load(agent / "science" / "scientific-objects.json") or {}
    loci = [item for item in (merged.get("objects") or []) if item.get("kind") == "constraint_locus"
            and (item.get("properties") or {}).get("status") == "violated"]
    signatures = merged.get("dependence_signatures") or []
    executed_keys = {(entry["func"][0], entry["func"][1]) for entry in signatures
                     if isinstance(entry.get("func"), list) and len(entry["func"]) == 3}
    node_keys = {(node.get("path"), node.get("name")) for node in nodes}
    boundary_targets = {ref.get("target", "").split(":")[0] for node in nodes for ref in node.get("boundary") or []}
    executed_seen = sum(1 for path, name in executed_keys
                        if (path, name) in node_keys or path in boundary_targets)
    return {
        "task": run.get("task_id") or job.parent.name.split("-")[1],
        "status": run.get("status"),
        "extraction": run.get("extraction_status"),
        "prepare_seconds": round(prepare.get("duration_seconds") or 0, 1),
        "traced": construction.get("traced"),
        "merged": construction.get("merged"),
        "classification": reproduction.get("classification"),
        "nodes": graph.get("nodes"),
        "edges": graph.get("edges"),
        "findings": graph.get("findings"),
        "grounded": f"{len(grounded)}/{len(nodes)}" if nodes else "0/0",
        "citable": len(citable),
        "loci": len(loci),
        "findings_kept": f"{graph.get('findings') or 0}/{len(loci)}" if loci else "0/0",
        "executed_seen": f"{executed_seen}/{len(executed_keys)}" if executed_keys else "-",
        "self_report": steps.get("record", {}).get("status"),
        "self_unseen": steps.get("unseen_citation", {}).get("status"),
        "expansion": (steps.get("expansion") or {}).get("compiled"),
    }


def main(argv):
    run_dir = Path(argv[1] if len(argv) > 1 else "runs/extractor-validation-30")
    rows = []
    for job in sorted(run_dir.glob("jobs/*/task_*")):
        if job.is_dir() and (job / "run.json").is_file():
            rows.append(task_row(job))
    if not rows:
        print("no completed jobs found in", run_dir)
        return 1
    columns = ["task", "status", "extraction", "prepare_seconds", "traced", "merged",
               "classification", "nodes", "edges", "loci", "findings_kept", "executed_seen",
               "grounded", "citable", "self_report", "self_unseen", "expansion"]
    widths = {column: max(len(column), *(len(str(row.get(column))) for row in rows)) for column in columns}
    print("  ".join(column.ljust(widths[column]) for column in columns))
    for row in rows:
        print("  ".join(str(row.get(column, "")).ljust(widths[column]) for column in columns))
    complete = sum(1 for row in rows if row["status"] == "completed")
    print(f"\n{complete}/{len(rows)} completed | "
          f"graphs {sum(1 for row in rows if row['nodes'])}/{len(rows)} | "
          f"recorded {sum(1 for row in rows if row['self_report'] == 'recorded')}/{len(rows)} | "
          f"unseen refused {sum(1 for row in rows if row['self_unseen'] == 'refused')}/"
          f"{sum(1 for row in rows if row['self_unseen'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
