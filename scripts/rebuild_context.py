"""Recheck graph changes on saved public evidence, without Docker or model calls."""
from __future__ import annotations

import argparse
import copy
import json
import shutil
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from scicontext.dynamic_binding import dependence_signatures
from scicontext.execution_seed import read_execution
from scicontext.io import digest_file, read_json, write_json
from scicontext.object_context import enrichment_input
from scicontext.packet import build_packet
from scicontext.relations import derive_loci, load_trace
from scicontext.representation import reading_input
from scicontext.science_tools import NODE_SOURCE_PAGE, ScienceStore
from scicontext.scientific_graph import admit_selected_sources, build_graph
from scicontext.scientific_objects import extract_objects


def optional(path):
    return read_json(path) if path.is_file() else {}


def rebuild(store: Path, output: Path, source_root=None, instruction=None):
    started = time.monotonic()
    packet = read_json(store / "packet.json")
    original = read_json(store / "scientific-objects.json")
    initial = store.parent / 'science-initial-state.json'
    before_path = initial if initial.is_file() else store / 'state.json'
    before = (optional(before_path).get("scientific_graph") or {})
    graph = copy.deepcopy(original)
    trace = store / "trace"
    records = load_trace(trace / "trace.jsonl.gz")
    packet_path = store / "packet.json"
    if source_root is not None:
        context_dir = output / "context"
        context_dir.mkdir(parents=True)
        shutil.copyfile(instruction, context_dir / "task_statement.md")
        expected = {d["sha256"] for d in packet["documents"] if d["path"] == "@context/task_statement.md"}
        if expected and digest_file(context_dir / "task_statement.md") not in expected:
            raise ValueError("Task instruction differs from the original preparation")
        execution = read_execution(trace)
        packet = build_packet(source_root, context_dir, multilingual=True,
                              seed=execution["functions"], execution=execution)
        graph = extract_objects(source_root, packet)
        packet_path = output / "packet.json"
        write_json(packet_path, packet)
    predicates = optional(trace / "script_predicates.json")
    derived = derive_loci(records, predicates.get("evaluations", []),
        script_status=optional(trace / "run.json").get("script_status"),
        observer_summary=optional(trace / "observer_summary.json"), script_file="reproduce.py",
        script_report=optional(trace / "script_report.json"))
    # Native location candidates are previously derived source evidence; no
    # candidate repository is executed or re-scanned by this offline check.
    old_loci = {o["id"]: o for o in original["objects"] if o.get("kind") == "constraint_locus"}
    for locus in derived["loci"]:
        old = old_loci.get(locus["id"], {})
        locus["properties"]["static_candidates"] = (old.get("properties") or {}).get("static_candidates", [])
    graph["objects"] = [o for o in graph["objects"] if o.get("kind") != "constraint_locus"] + derived["loci"]
    graph["dynamic"] = derived["dynamic"]
    graph["dependence_signatures"] = dependence_signatures(records)
    graph_path = output / "objects.json"
    write_json(graph_path, graph)
    after = build_graph(graph_path, packet_path, trace)
    write_json(output / "graph.json", after)
    payload = enrichment_input(graph, packet)
    admit_selected_sources(payload, packet)
    compiled = reading_input(payload)
    context = {"sources": {s["id"]: s for s in packet["entries"]},
               "documents": {s["id"]: s for s in packet["documents"]},
               "entities": {e["id"]: e for e in compiled["entities"]}}
    previews = [{"node": node["id"], "path": node["path"], "name": node["name"],
                 "calculation": node.get('calculation'),
                 "documented_context": [s for identifier in node.get('documentation_ids', [])
                     if (s := ScienceStore._source_excerpt(context, identifier))],
                 "conditions": node.get("conditions"), "findings": node.get("findings"),
                 "observations": node.get("observations"),
                 "sources": [s for identifier in node.get("source_ids", [])[:NODE_SOURCE_PAGE]
                             if (s := ScienceStore._source_excerpt(context, identifier))]}
                for node in after["nodes"]]
    write_json(output / "first-pages.json", {"nodes": previews})
    def metrics(value):
        nodes = value.get("nodes", [])
        return {"nodes": len(nodes), "grounded_nodes": sum(bool(n.get("source_ids")) for n in nodes),
                "findings": sum(len(n.get("findings") or []) for n in nodes),
                "observations": sum(len(n.get("observations") or []) for n in nodes)}
    return {"input_store": str(store), "before": metrics(before), "after": metrics(after),
            "before_snapshot":str(before_path), "before_snapshot_sha256":digest_file(before_path),
            "elapsed_seconds":time.monotonic() - started,
            "source_root": str(source_root) if source_root else None,
            "rebuilt_packet_sha256": digest_file(packet_path),
            "guarded_sources_on_first_pages": sum(bool(s.get("guards")) for n in previews for s in n["sources"]),
            "input_sha256": {name: digest_file(store / name) for name in
                ("packet.json", "scientific-objects.json", "trace/trace.jsonl.gz")}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--tasks", nargs="*")
    parser.add_argument('--jobs', type=int, default=1, help='Independent offline task rebuild processes')
    parser.add_argument("--source-root", type=Path, help="Optional directory of pristine public task-ID source snapshots")
    parser.add_argument("--release-receipt", type=Path,
                        default=Path(__file__).resolve().parents[1] / "data/full-119-release.json")
    args = parser.parse_args()
    if args.jobs < 1:
        parser.error('--jobs must be positive')
    if args.output.exists():
        raise FileExistsError("Choose a fresh output; original and prior derived artifacts stay intact")
    rows = {}
    release = read_json(args.release_receipt) if args.source_root else None
    with ProcessPoolExecutor(max_workers=args.jobs) as pool:
        pending = {}
        for store in sorted(args.run.glob("jobs/task-*-science/task_*/agent/science")):
            task_id = store.parents[2].name.split("-")[1]
            if args.tasks and task_id not in args.tasks:
                continue
            pending[pool.submit(rebuild, store, args.output / task_id,
                args.source_root / task_id if args.source_root else None,
                Path(release["selection_path"]) / f"task_{task_id}" / "instruction.md" if release else None)] = task_id
        for future in as_completed(pending):
            task_id = pending[future]
            try:
                rows[task_id] = future.result()
            except (OSError, ValueError, KeyError) as error:
                rows[task_id] = {"error": f"{type(error).__name__}: {error}"}
            print(task_id, json.dumps(rows[task_id].get("after", rows[task_id])), flush=True)
    source_root = Path(__file__).resolve().parents[1] / "src/scicontext"
    report = {"tasks": rows, 'script_sha256':digest_file(Path(__file__)),
              "source_sha256": {p.name: digest_file(p) for p in source_root.glob("*.py")},
              "scope": "Saved-public-evidence recheck; grounding counts do not establish scientific relevance."}
    write_json(args.output / "summary.json", report)
    return 1 if any("error" in row for row in rows.values()) or not rows else 0


if __name__ == "__main__":
    raise SystemExit(main())
