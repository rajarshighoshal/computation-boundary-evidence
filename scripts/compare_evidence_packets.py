"""Save an offline before/after interpreter-input comparison from public source records."""
import argparse
import ast
from collections import Counter
import json
from pathlib import Path
from time import perf_counter
from textwrap import dedent

from scicontext.io import digest_file, read_json, write_json
from scicontext.object_context import enrichment_input
from scicontext.packet import _reproducer


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--previous-input", type=Path, help="Compare against a preserved connected input")
    parser.add_argument("--require-function", action="append", default=[], help="Offline acceptance check; not a retrieval rule")
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Preserve previous comparisons; choose a fresh output")
    graph, packet = read_json(args.graph), read_json(args.packet)
    before = read_json(args.previous_input) if args.previous_input else enrichment_input(graph, packet)
    start = perf_counter()
    after = enrichment_input(graph, packet, root=args.root, connected=True)
    elapsed = perf_counter() - start
    bodies = after["context"]["function_bodies"]
    functions = {node.name for b in bodies if b["path"].endswith(".py") and b["kind"] == "complete_function_body"
                 for node in ast.parse(dedent(b["text"])).body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    checks = {name: name in functions for name in args.require_function}
    body_names = {b["id"]: {node.name for node in ast.parse(dedent(b["text"])).body
                           if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
                  for b in bodies if b["path"].endswith(".py") and b["kind"] == "complete_function_body"}
    common_bundle = any(set(args.require_function) <= set().union(
        *(body_names.get(bid, set()) for bid in bundle["function_body_ids"])) for bundle in after["evidence_packets"])
    calls = after["context"].get("helper_calls", [])
    body_ids, call_ids = {b["id"] for b in bodies}, {c["id"] for c in calls}
    bindings_valid = all(c["caller_body_id"] in body_ids and c["callee_body_id"] in body_ids for c in calls)
    bindings_valid &= all(set(p.get("helper_call_ids", [])) <= call_ids for p in after["evidence_packets"])
    args.output.mkdir(parents=True)
    write_json(args.output / "before.json", before)
    write_json(args.output / "after.json", after)
    count = lambda x: {k: len(x[k]) for k in ("objects", "operations", "links")}
    receipt = {"input_graph": str(args.graph), "input_graph_sha256": digest_file(args.graph),
               "input_packet": str(args.packet), "input_packet_sha256": digest_file(args.packet),
               "source_root": str(args.root), "before": count(before), "after": count(after),
               "previous_input": str(args.previous_input) if args.previous_input else None,
               "previous_input_sha256": digest_file(args.previous_input) if args.previous_input else None,
               "connected_input_seconds": elapsed,
               "required_function_checks": checks,
               "required_functions_in_one_packet": common_bundle,
               "helper_endpoints_valid": bindings_valid,
               "helper_argument_binding_statuses": dict(Counter(c["binding_status"] for c in calls)),
               "helper_call_links": len(after["context"].get("helper_calls", [])),
               "unique_function_bodies": len({b["id"] for b in bodies}),
               "duplicate_function_body_records": len(bodies) - len({b["id"] for b in bodies}),
               "source_hashes": {b["path"]: b["sha256"] for b in bodies},
               "before_bytes": (args.output / "before.json").stat().st_size,
               "after_bytes": (args.output / "after.json").stat().st_size,
               "evidence_packets": len(after["evidence_packets"]),
               "complete_function_bodies": sum(b["kind"] == "complete_function_body" for b in after["context"]["function_bodies"]),
               "gaps": sorted({g["reason"] for p in after["evidence_packets"] for g in p["gaps"]} |
                              {g["reason"] for g in after["context"].get("helper_gaps", [])}),
               "omitted_packet_seeds": len(after["selection"]["omitted_packets"]),
               "omission_reasons": dict(Counter(p["reason"] for p in after["selection"]["omitted_packets"])),
               "model_calls": 0, "candidate_code_executed": False,
               "interpretation": "Structural input comparison only; not scientific correctness or repair benefit."}
    write_json(args.output / "receipt.json", receipt)
    lines = ["# Phase 1: interpreter input before/after", "", receipt["interpretation"], "",
             "| Measure | Before | After |", "|---|---:|---:|"]
    lines += [f"| {k} | {receipt['before'][k]} | {receipt['after'][k]} |" for k in receipt["before"]]
    lines += [f"| Saved JSON bytes | {receipt['before_bytes']} | {receipt['after_bytes']} |", "",
              f"Connected packets: {receipt['evidence_packets']}; complete function bodies: {receipt['complete_function_bodies']}.", "",
              "## Example source region", ""]
    example = next((b for b in after["context"]["function_bodies"] if not _reproducer(b["path"]) and b["kind"] == "complete_function_body"), None)
    if example:
        old = next((e for e in before["context"]["code_passages"] if e["path"] == example["path"] and e["start_line"] == example["start_line"]), None)
        lines += [f"Source: `{example['path']}:{example['start_line']}-{example['end_line']}`.", "",
                  "Before: the defining excerpt (other indexed fragments may occur elsewhere):", "```python",
                  (old or {}).get("text") or "not selected", "```", "",
                  "After: the full hash-checked body, associated with its packet's objects/operations:",
                  "```python", example["text"], "```", ""]
    lines += ["## Remaining gaps", "", *["- " + gap for gap in receipt["gaps"]], "",
              f"Omitted packet seeds: {receipt['omitted_packet_seeds']}; reasons: {receipt['omission_reasons']}. "
              "These are selection/budget omissions, not evidence that the excluded material is irrelevant.", "",
              "Candidate callee links retain their original status; they are not runtime dispatch proofs. "
              "No LLM interpretation, guide renderer, repair prompt or scientific rule changed in this phase.", ""]
    (args.output / "comparison.md").write_text("\n".join(lines))
    print(json.dumps(receipt, indent=2))
    if not all(checks.values()) or not common_bundle or not bindings_valid:
        raise SystemExit("Required implementation body missing; see preserved receipt")


if __name__ == "__main__":
    main()
