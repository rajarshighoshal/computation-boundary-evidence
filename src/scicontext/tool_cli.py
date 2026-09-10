"""Offline helper interface exposed to extraction in its task container."""
from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path

from .evidence import extract_evidence
from .expressions import align_expressions, parse_expression
from .io import digest_file, digest_json, read_json, write_json


def analyze_grounded(graph: dict, root: Path) -> dict:
    """Check code-expression provenance independently of the LLM's actual tree."""
    from .semantics import analyze_graph

    evidence = {e["id"]: e for e in graph["evidence"]}
    paths = sorted({e["path"] for e in graph["evidence"] if e["path"].endswith(".py") and not e["path"].startswith("@context/")})
    source_refs = [e for e in graph["evidence"] if e["path"] in paths]
    index = extract_evidence(root, paths, references=source_refs) if paths else {"entries": [], "coverage": {}}
    checked = copy.deepcopy(graph)
    grounding = []
    for claim in checked["claims"]:
        if claim["actual"] is None:
            grounding.append({"claim_id": claim["id"], "status": "unresolved", "reason": "No implementation expression supplied"})
            continue
        refs = [evidence[eid] for eid in claim["evidence_ids"] if eid in evidence]
        matches = [entry for entry in index["entries"]
                   if entry.get("expression") is not None and entry.get("kind") != "augmented_assignment"
                   and any(ref["path"] == entry["path"] and ref["sha256"] == entry["sha256"]
                           and ref["start_line"] <= (entry.get("expression_span") or entry)["start_line"]
                           and ref["end_line"] >= (entry.get("expression_span") or entry)["end_line"] for ref in refs)
                   and (claim["actual"] == entry["expression"] or
                        align_expressions(claim["actual"], entry["expression"])["status"] == "match")]
        if len(matches) == 1:
            grounding.append({"claim_id": claim["id"], "status": "source_matched", "entry_ids": [e["id"] for e in matches],
                              "locations": [{k: e.get(k) for k in ("path", "scope", "branch", "expression_span")} for e in matches],
                              "limitations": "Source syntax matched; runtime meaning, types, and applicability remain conditional."})
        else:
            # Keep raw graph untouched; do not analyze uncorroborated text as if it came from code.
            claim["actual"] = None
            grounding.append({"claim_id": claim["id"], "status": "unresolved", "reason": "Actual expression was not uniquely corroborated by cited indexed source; excluded from code-derived analysis", "matching_entries": len(matches)})
    analysis = analyze_graph(checked)
    analysis["alignments"] = []
    for claim in checked["claims"]:
        bindings = {b["expected"]: b["actual"] for b in claim["bindings"]}
        alignment = (align_expressions(claim["relation"], claim["actual"], bindings)
                     if claim["relation"] is not None and claim["actual"] is not None
                     else {"status": "unknown", "reason": "Both a scientific relation and a corroborated implementation expression are required"})
        analysis["alignments"].append({"claim_id": claim["id"], **alignment})
    analysis["code_grounding"] = grounding
    analysis["source_coverage"] = index["coverage"]
    analysis["probe_policy"] = "Graph observations are reported claims; execution must be corroborated from the separate Codex command log."
    return analysis


def checkpoint(graph_path: Path, root: Path, output: Path, context_root: Path | None = None) -> dict:
    from .graph import render_graph, validate_graph

    graph = read_json(graph_path)
    validation = validate_graph(graph, root, context_root=context_root)
    if not validation["valid"]:
        return {"saved": False, "validation": validation}
    analysis = analyze_grounded(graph, root)
    identity = digest_json(graph)
    bundle = {"graph": graph, "validation": validation, "analysis": analysis,
              "graph_sha256": identity, "handoff": render_graph(graph, analysis)}
    output.mkdir(parents=True, exist_ok=True)
    write_json(output / f"{identity}.json", bundle)
    return {"saved": True, "checkpoint": f"{identity}.json", "analysis": analysis, "validation": validation}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="command", required=True)
    idx = subs.add_parser("index")
    idx.add_argument("--root", type=Path, required=True)
    idx.add_argument("paths", nargs="*")
    idx.add_argument("--output", type=Path)
    idx.add_argument("--max-entries", type=int, default=200)
    expr = subs.add_parser("expression")
    expr.add_argument("text")
    cite = subs.add_parser("cite")
    cite.add_argument("--root", type=Path, required=True)
    cite.add_argument("path")
    cite.add_argument("start", type=int)
    cite.add_argument("end", type=int)
    cite.add_argument("--context-root", type=Path)
    check = subs.add_parser("checkpoint")
    check.add_argument("--root", type=Path, required=True)
    check.add_argument("--graph", type=Path, required=True)
    check.add_argument("--output", type=Path, required=True)
    check.add_argument("--context-root", type=Path)
    packet = subs.add_parser("packet")
    packet.add_argument("--root", type=Path, required=True)
    packet.add_argument("--context-root", type=Path, required=True)
    packet.add_argument("--task-id", required=True)
    packet.add_argument("--output", type=Path, required=True)
    packet.add_argument("--catalog", type=Path, required=True)
    packet.add_argument("--objects-output", type=Path)
    packet.add_argument("--enrichment-input", type=Path)
    objects = subs.add_parser("assemble-objects")
    objects.add_argument("--graph", type=Path, required=True)
    objects.add_argument("--annotations", type=Path, required=True)
    objects.add_argument("--context-input", type=Path, required=True)
    objects.add_argument("--output", type=Path, required=True)
    assemble = subs.add_parser("assemble")
    assemble.add_argument("--root", type=Path, required=True)
    assemble.add_argument("--context-root", type=Path, required=True)
    assemble.add_argument("--packet", type=Path, required=True)
    assemble.add_argument("--annotations", type=Path, required=True)
    assemble.add_argument("--probe-results", type=Path)
    assemble.add_argument("--output", type=Path, required=True)
    probes = subs.add_parser("run-probes")
    probes.add_argument("--root", type=Path, required=True)
    probes.add_argument("--scratch", type=Path, required=True)
    probes.add_argument("--specs", type=Path, required=True)
    probes.add_argument("--seconds", type=float, required=True)
    probes.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "index":
        result = extract_evidence(args.root, args.paths or None, max_entries=args.max_entries)
        if args.output:
            write_json(args.output, result)
    elif args.command == "expression":
        result = parse_expression(args.text)
    elif args.command == "cite":
        root = args.root.resolve()
        original_path = args.path
        if Path(args.path).parts[:1] == ("outputs",):
            raise ValueError("Generated task outputs are observations, not immutable source evidence")
        if args.path.startswith("@context/"):
            context = args.context_root or os.environ.get("SCICONTEXT_CONTEXT_ROOT")
            if not context or args.path != "@context/task_statement.md":
                raise ValueError("Unknown or unavailable immutable task context")
            root = Path(context).resolve()
            args.path = "task_statement.md"
        path = root / args.path
        if path.is_symlink() or not path.resolve().is_relative_to(root) or any(p.startswith(".") or p in {"private_tests", "auth.json"} for p in Path(args.path).parts):
            raise ValueError("Evidence path is outside allowed public source")
        if path.stat().st_size > 2_000_000 or args.start < 1 or args.end < args.start or args.end - args.start > 200:
            raise ValueError("Evidence span exceeds limits")
        lines = path.read_text(encoding="utf-8").splitlines()
        if args.end > len(lines):
            raise ValueError("Evidence span exceeds source")
        result = {"id": "e_" + digest_json([args.path, digest_file(path), args.start, args.end])[:16],
                  "path": original_path, "sha256": digest_file(path), "start_line": args.start,
                  "end_line": args.end, "quote": "\n".join(lines[args.start - 1:args.end])}
    elif args.command == "checkpoint":
        context = args.context_root or os.environ.get("SCICONTEXT_CONTEXT_ROOT")
        result = checkpoint(args.graph, args.root, args.output, Path(context) if context else None)
    elif args.command == "packet":
        from .packet import build_packet, render_catalog
        value = build_packet(args.root, args.context_root)
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
    elif args.command == "assemble-objects":
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
    elif args.command == "assemble":
        from .annotations import annotation_references, assemble_annotations
        from .packet import expand_packet
        try:
            if args.annotations.stat().st_size > 65536:
                raise ValueError("Compact annotations exceed 64 KiB")
            annotations = read_json(args.annotations)
            packet_value = read_json(args.packet)
            references, keep_ids = annotation_references(annotations)
            expansion_identity = digest_json([references, keep_ids])
            if references and packet_value.get("annotation_expansion_sha256") != expansion_identity:
                packet_value = expand_packet(args.root, packet_value, references, keep_ids=keep_ids)
                packet_value["annotation_expansion_sha256"] = expansion_identity
                write_json(args.packet, packet_value)
            outcomes = read_json(args.probe_results)["results"] if args.probe_results else None
            bundle = assemble_annotations(annotations, packet_value, args.root, args.context_root, outcomes)
            write_json(args.output, bundle)
            usable = bundle["assembly"]["usable"]
            result = {"status": "usable_graph" if usable else "abstained",
                      "usable": usable, "graph_sha256": bundle.get("graph_sha256"),
                      "accepted_claim_ids": bundle["assembly"]["accepted_claim_ids"],
                      "probes": bundle["probes"], "assembly": bundle["assembly"]}
        except (OSError, ValueError, KeyError, TypeError) as error:
            result = {"status": "invalid_or_missing_annotations", "usable": False,
                      "error": f"{type(error).__name__}: {error}", "probes": []}
            write_json(args.output, {"assembly": result, "graph": None})
    else:
        from .probes import run_probes
        specs = read_json(args.specs)["probes"]
        results = run_probes(specs, args.root, args.scratch, args.seconds)
        write_json(args.output, {"results": results})
        result = {"status": "completed", "results": results}
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    return 0 if args.command != "checkpoint" or result["saved"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
