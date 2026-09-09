"""Offline helper interface exposed to extraction, executed in its task sandbox."""
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
    index = extract_evidence(root, paths) if paths else {"entries": [], "coverage": {}}
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
                   and align_expressions(claim["actual"], entry["expression"])["status"] == "match"]
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
    else:
        context = args.context_root or os.environ.get("SCICONTEXT_CONTEXT_ROOT")
        result = checkpoint(args.graph, args.root, args.output, Path(context) if context else None)
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    return 0 if args.command != "checkpoint" or result["saved"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
