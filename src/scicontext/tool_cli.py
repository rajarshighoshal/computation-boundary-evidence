"""Offline helper interface exposed to extraction in its task container."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .io import read_json, write_json


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="command", required=True)
    packet = subs.add_parser("packet")
    packet.add_argument("--root", type=Path, required=True)
    packet.add_argument("--context-root", type=Path, required=True)
    packet.add_argument("--task-id", required=True)
    packet.add_argument("--output", type=Path, required=True)
    packet.add_argument("--catalog", type=Path, required=True)
    packet.add_argument("--objects-output", type=Path)
    packet.add_argument("--enrichment-input", type=Path)
    trace = subs.add_parser("trace")
    trace.add_argument("--root", type=Path, required=True)
    trace.add_argument("--script", type=Path, required=True)
    trace.add_argument("--out", type=Path, required=True)
    trace.add_argument("--seconds", type=float, default=300.0)
    merge = subs.add_parser("merge-dynamic")
    merge.add_argument("--graph", type=Path, required=True)
    merge.add_argument("--packet", type=Path, required=True)
    merge.add_argument("--trace-out", type=Path, required=True)
    merge.add_argument("--output", type=Path, required=True)
    merge.add_argument("--enrichment-input", type=Path, required=True)
    objects = subs.add_parser("assemble-objects")
    objects.add_argument("--graph", type=Path, required=True)
    objects.add_argument("--annotations", type=Path, required=True)
    objects.add_argument("--context-input", type=Path, required=True)
    objects.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "packet":
        from .packet import build_packet, render_catalog
        value = build_packet(args.root, args.context_root, multilingual=bool(args.objects_output))
        value["task_id"] = args.task_id
        write_json(args.output, value)
        args.catalog.parent.mkdir(parents=True, exist_ok=True)
        args.catalog.write_text(render_catalog(value))
        result = {"status": "ready", "entries": len(value["entries"]),
                  "documents": len(value["documents"]), "coverage": value["coverage"]}
        if args.objects_output:
            from .scientific_objects import extract_objects
            from .object_context import enrichment_input
            graph = extract_objects(args.root, value)
            graph["task_id"] = args.task_id
            write_json(args.objects_output, graph)
            if args.enrichment_input:
                write_json(args.enrichment_input, enrichment_input(graph, value))
            result["scientific_object_coverage"] = graph["coverage"]
    elif args.command == "trace":
        from .trace_runtime import _Tracer
        tracer = _Tracer(args.root.resolve(), args.script.resolve(), args.out.resolve(), observe=False)
        tracer.run(args.seconds)
        result = {"status": "completed", "out": str(args.out)}
    elif args.command == "merge-dynamic":
        from .dynamic_binding import build_quantity_graph, dependence_signatures
        from .object_context import enrichment_input
        from .relations import derive_loci, load_trace
        graph = read_json(args.graph)
        packet = read_json(args.packet)
        records = load_trace(args.trace_out / "trace.jsonl.gz")
        predicates = read_json(args.trace_out / "script_predicates.json")
        run = read_json(args.trace_out / "run.json")
        observer = None
        try:
            observer = read_json(args.trace_out / "observer_summary.json")
        except (OSError, ValueError):
            pass
        derived = derive_loci(records, predicates["evaluations"], script_status=run.get("script_status"),
                              observer_summary=observer, script_file="reproduce.py")
        quantity_graph = build_quantity_graph(records)
        signatures = dependence_signatures(records)
        graph["objects"] = [obj for obj in graph.get("objects", []) if obj.get("kind") != "constraint_locus"]
        graph["objects"].extend(derived["loci"])
        graph["dynamic"] = derived["dynamic"]
        graph["quantity_graph"] = {"quantities": len(quantity_graph["quantities"]),
                                   "transitions": len(quantity_graph["transitions"])}
        graph["dependence_signatures"] = signatures
        write_json(args.output, graph)
        write_json(args.enrichment_input, enrichment_input(graph, packet))
        result = {"status": "merged", "loci": derived["dynamic"]["loci"],
                  "quantities": len(quantity_graph["quantities"]),
                  "signatures": len(signatures)}
    else:
        from .object_context import object_bundle
        graph = read_json(args.graph)
        try:
            response = read_json(args.annotations)
        except (OSError, ValueError):
            response = None
        bundle = object_bundle(graph, response, read_json(args.context_input))
        write_json(args.output, bundle)
        result = {"status": bundle["assembly"]["status"], "usable": bundle["assembly"]["usable"],
                  "assembly": bundle["assembly"], "graph_sha256": bundle["graph_sha256"], "probes": []}
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
