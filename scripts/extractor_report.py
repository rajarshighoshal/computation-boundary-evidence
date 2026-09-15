"""Audit prepared graph snapshots from extraction or paired runs (no model calls).

Reads runs/<name>/jobs/*/task_*/ receipts and exported science stores and
reports per-task construction/grounding: construction status, node/edge/finding
counts, reproduction classification, node grounding, and the in-container
self-check (query path, record/refuse, expansion).

Usage: python scripts/extractor_report.py runs/extractor-validation-30
"""
from __future__ import annotations

import argparse
import hashlib
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
    bundle = load(job / "graph-bundle.json") or {}
    initial = (load(agent / "science-initial-state.json") or {}).get("scientific_graph")
    bundled = bundle.get("graph") if isinstance((bundle.get("graph") or {}).get("nodes"), list) else None
    stored = initial or bundled or store.get("scientific_graph") or {}
    nodes = stored.get("nodes") or []
    snapshot = "pre_repair_state" if initial else "pre_repair_bundle" if bundled else "exported_store"
    snapshot_file = agent / "science-initial-state.json"
    expected_snapshot = bundle.get("initial_state_sha256")
    snapshot_valid = (hashlib.sha256(snapshot_file.read_bytes()).hexdigest() == expected_snapshot
                      if expected_snapshot and snapshot_file.is_file() else None)
    packet = load(agent / "science" / "packet.json")
    known_sources = {item["id"] for field in ("entries", "documents")
                     for item in (packet or {}).get(field, []) if item.get("id")}
    referenced = {identifier for node in nodes for identifier in node.get("source_ids", [])}
    node_ids = {node["id"] for node in nodes}
    dangling_edges = [edge for edge in stored.get("edges", [])
                      if edge.get("from") not in node_ids or edge.get("to") not in node_ids]
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
    exact_functions = sum(1 for key in executed_keys if key in node_keys)
    return {
        "task": run.get("task_id") or job.parent.name.split("-")[1],
        "status": run.get("status"),
        "extraction": run.get("extraction_status"),
        "prepare_seconds": round(prepare.get("duration_seconds") or 0, 1),
        "traced": construction.get("traced"),
        "merged": construction.get("merged"),
        "classification": reproduction.get("classification"),
        "graph_snapshot": snapshot,
        "initial_snapshot_hash_valid": snapshot_valid,
        "prepare_status": prepare.get("status"),
        "nodes": len(nodes),
        "edges": len(stored.get("edges", [])),
        "findings": sum(len(node.get("findings", [])) for node in nodes),
        "dangling_edges": len(dangling_edges),
        "unmatched_packet_source_ids": sorted(referenced - known_sources) if packet else None,
        "implementation_paths": sorted({node.get("path") for node in nodes
                                        if node.get("kind") == "implementation" and node.get("path")}),
        "grounded": f"{len(grounded)}/{len(nodes)}" if nodes else "0/0",
        "citable": len(citable),
        "loci": len(loci),
        "findings_kept": f"{graph.get('findings') or 0}/{len(loci)}" if loci else "0/0",
        "executed_seen": f"{executed_seen}/{len(executed_keys)}" if executed_keys else "-",
        "executed_exact_functions": f"{exact_functions}/{len(executed_keys)}" if executed_keys else "-",
        "boundary_file_only": executed_seen - exact_functions,
        "self_report": steps.get("record", {}).get("status"),
        "self_unseen": steps.get("unseen_citation", {}).get("status"),
        "expansion": (steps.get("expansion") or {}).get("compiled"),
    }


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path, nargs="?", default=Path("runs/extractor-validation-30"))
    parser.add_argument("--output", type=Path, help="Save the same audit rows as JSON")
    args = parser.parse_args(argv[1:])
    run_dir = args.run_dir
    rows = []
    for job in sorted(run_dir.glob("jobs/*/task_*")):
        if job.is_dir() and (load(job / "run.json") or {}).get("condition") == "science":
            rows.append(task_row(job))
    if not rows:
        print("no completed jobs found in", run_dir)
        return 1
    columns = ["task", "status", "extraction", "prepare_seconds", "traced", "merged",
               "classification", "nodes", "edges", "loci", "findings_kept", "executed_exact_functions", "boundary_file_only",
               "grounded", "citable", "self_report", "self_unseen", "expansion"]
    widths = {column: max(len(column), *(len(str(row.get(column))) for row in rows)) for column in columns}
    print("  ".join(column.ljust(widths[column]) for column in columns))
    for row in rows:
        print("  ".join(str(row.get(column, "")).ljust(widths[column]) for column in columns))
    complete = sum(1 for row in rows if row["status"] == "completed")
    if args.output:
        schedule = load(run_dir / "schedule.json") or {}
        tasks = (schedule.get("config") or {}).get("task_ids", [])
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps({"task_ids": tasks, "rows": rows,
            "missing_task_ids": sorted(set(tasks) - {row["task"] for row in rows}),
            "scope": "Initial pre-repair graphs when available. Construction/source references are not scientific relevance or correctness. No model calls.",
            "implementation_revision": schedule.get("implementation_revision")}, indent=2) + "\n")
    print(f"\n{complete}/{len(rows)} completed | "
          f"graphs {sum(1 for row in rows if row['nodes'])}/{len(rows)} | "
          f"recorded {sum(1 for row in rows if row['self_report'] == 'recorded')}/{len(rows)} | "
          f"unseen refused {sum(1 for row in rows if row['self_unseen'] == 'refused')}/"
          f"{sum(1 for row in rows if row['self_unseen'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
