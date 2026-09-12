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
    trace.add_argument("--observe", action="store_true")
    trace.add_argument("--shims-dir", type=Path, default=None)
    merge = subs.add_parser("merge-dynamic")
    merge.add_argument("--root", type=Path, required=True)
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
        tracer = _Tracer(args.root.resolve(), args.script.resolve(), args.out.resolve(),
                         observe=args.observe, shims_dir=args.shims_dir)
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
        script_report = None
        try:
            script_report = read_json(args.trace_out / "script_report.json")
        except (OSError, ValueError):
            pass
        derived = derive_loci(records, predicates["evaluations"], script_status=run.get("script_status"),
                              observer_summary=observer, script_file="reproduce.py",
                              script_report=script_report)
        # R9: attach native tolerance-comparison candidates to completion loci.
        # Scan the native sources directly (the packet's entry caps can exclude
        # the relevant file); bounded to 200 files / 2 MB each.
        import re as _re
        candidates = {}
        for entry in packet.get("entries", []):
            text = entry.get("text") or ""
            if entry.get("kind") == "comparison" and _re.search(r"PRECISION|EPS|TOLERANCE|_TOL|_EPS", text):
                candidates.setdefault(entry.get("path"), []).append(entry.get("start_line"))
        native_suffixes = (".cpp", ".cc", ".cxx", ".c", ".h", ".hpp", ".f90", ".f95", ".f03", ".m")
        scanned = 0
        for path in sorted(args.root.rglob("*")):
            if scanned >= 200:
                break
            if not path.is_file() or path.suffix.lower() not in native_suffixes:
                continue
            try:
                if path.stat().st_size > 2 * 1024 * 1024:
                    continue
                text = path.read_text(errors="replace")
            except OSError:
                continue
            scanned += 1
            relative = path.relative_to(args.root).as_posix()
            for line_number, line in enumerate(text.splitlines(), start=1):
                if _re.search(r"<|>|==|<=|>=", line) and _re.search(r"PRECISION|EPS|TOLERANCE|_TOL|_EPS", line):
                    candidates.setdefault(relative, []).append(line_number)
        if candidates:
            for locus in derived["loci"]:
                if locus["properties"].get("rule_id") in {"R6", "R6s", "R6p", "R8"}:
                    for path, lines in candidates.items():
                        locus["properties"]["static_candidates"].extend(
                            [{"path": path, "line": line} for line in lines])
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
