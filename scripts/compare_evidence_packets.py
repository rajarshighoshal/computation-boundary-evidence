"""Save an offline before/after interpreter-input comparison from public source records."""
import argparse
from collections import Counter
import json
from pathlib import Path

from scicontext.io import digest_file, read_json, write_json
from scicontext.object_context import enrichment_input
from scicontext.packet import _reproducer


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Preserve previous comparisons; choose a fresh output")
    graph, packet = read_json(args.graph), read_json(args.packet)
    before = enrichment_input(graph, packet)
    after = enrichment_input(graph, packet, root=args.root, connected=True)
    args.output.mkdir(parents=True)
    write_json(args.output / "before.json", before)
    write_json(args.output / "after.json", after)
    count = lambda x: {k: len(x[k]) for k in ("objects", "operations", "links")}
    receipt = {"input_graph": str(args.graph), "input_graph_sha256": digest_file(args.graph),
               "input_packet": str(args.packet), "input_packet_sha256": digest_file(args.packet),
               "source_root": str(args.root), "before": count(before), "after": count(after),
               "before_bytes": (args.output / "before.json").stat().st_size,
               "after_bytes": (args.output / "after.json").stat().st_size,
               "evidence_packets": len(after["evidence_packets"]),
               "complete_function_bodies": sum(b["kind"] == "complete_function_body" for b in after["context"]["function_bodies"]),
               "gaps": sorted({g["reason"] for p in after["evidence_packets"] for g in p["gaps"]}),
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


if __name__ == "__main__":
    main()
