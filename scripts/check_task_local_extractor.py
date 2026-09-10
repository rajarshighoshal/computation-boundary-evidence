#!/usr/bin/env python3
"""No-model development checks on preserved original public source and old packets."""
from __future__ import annotations

import argparse
import ast
import json
import subprocess
import time
from pathlib import Path

import scicontext
from scicontext.annotations import assemble_annotations, annotation_references
from scicontext.io import digest_file, read_json, write_json
from scicontext.packet import build_packet, expand_packet


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    originals = workspace / "runs/task-local-development/originals"
    cases = [
        ("091", "source/src/pymatgen/io/common.py", "reader",
         "runs/random-five-v1/jobs/task-091-science/task_091__Pf5SuUn/agent/extract-scratch/packet.json"),
        ("009", "source/desc/stability/terpsichore/vacuum.py", "projection_call",
         "runs/random-five-medium-v1/jobs/task-009-science/task_009__hedEtB2/agent/extract-scratch/packet.json"),
    ]
    args.output.mkdir(parents=True, exist_ok=True)
    source_dir = Path(scicontext.__file__).resolve().parent
    receipt = {"kind": "deterministic_development_check", "model_calls": 0, "cases": [],
               "implementation_revision": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
               "source_hashes": {p.name: digest_file(p) for p in sorted(source_dir.glob("*.py"))},
               "script_sha256": digest_file(Path(__file__)),
               "original_source_receipt": read_json(workspace / "runs/task-local-development/durable-source-receipt.json")}
    packets = {}
    for task, path, focus, baseline_path in cases:
        root, context = originals / f"task_{task}", originals / f"context_{task}"
        tree = ast.parse((root / path).read_text())
        candidates = [node for node in ast.walk(tree) if
                      (focus == "reader" and isinstance(node, ast.FunctionDef) and node.name == "from_cube") or
                      (focus == "projection_call" and isinstance(node, ast.Assign)
                       and isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name)
                       and node.value.func.id == "build_projection_wall")]
        if len(candidates) != 1:
            raise ValueError(f"Development source checklist is ambiguous: {task}/{focus}")
        node = candidates[0]
        baseline = read_json(workspace / baseline_path)
        context_refs = [d for d in baseline["documents"] if d["path"] == "@context/task_statement.md"]
        assert context_refs and all(d["sha256"] == digest_file(context / "task_statement.md") for d in context_refs)
        start = time.monotonic()
        packet = build_packet(root, context)
        elapsed = time.monotonic() - start
        packet["task_id"] = task
        packets[task] = packet
        def selected(value):
            return [entry["id"] for entry in value["entries"] if entry["path"] == path
                    and node.lineno <= entry["start_line"] and entry["end_line"] <= node.end_lineno]
        before, after = selected(baseline), selected(packet)
        assert after and len(packet["entries"]) <= packet["coverage"]["limits"]["entries"]
        write_json(args.output / f"packet-{task}.json", packet)
        receipt["cases"].append({"task_id": task, "focus": focus, "path": path,
            "source_sha256": digest_file(root / path), "start_line": node.lineno, "end_line": node.end_lineno,
            "context_sha256": digest_file(context / "task_statement.md"),
            "baseline_packet_sha256": digest_file(workspace / baseline_path),
            "baseline_focus_entries": before, "new_focus_entries": after,
            "baseline_entry_count": len(baseline["entries"]), "new_entry_count": len(packet["entries"]),
            "new_local_build_seconds": elapsed})

    # Handcrafted NEW-SCHEMA fixture: this tests the interface, not LLM quality.
    packet, root, context = packets["009"], originals / "task_009", originals / "context_009"
    path = cases[1][1]
    volume = [e for e in packet["entries"] if e["path"] == path and e.get("expression_text") == "-float(np.sum(bjac_i))"]
    assert len(volume) == 1
    ref = {k: volume[0][k] for k in ("path", "start_line", "end_line", "scope")}
    annotations = {"schema_version": "annotations-1.0", "quantities": [
        {"id": "q_J", "meaning": "Source operand; scientific units intentionally unresolved.",
         "status": "unresolved", "code_ref": {**ref, "symbol": "bjac_i"}}], "claims": [
        {"id": "c_syntax", "description": "Handcrafted relation-syntax development fixture, not an established physical law.",
         "formula": "V = -sum(J)", "implementation_ref": ref, "quantities": ["q_J"],
         "bindings": {"J": "bjac_i"}, "status": "unresolved", "evidence": [{k: ref[k] for k in ("path", "start_line", "end_line")}]}]}
    # Deliberately remove the occurrence to exercise post-annotation recovery.
    partial_packet = {**packet, "entries": [e for e in packet["entries"] if e["id"] != volume[0]["id"]]}
    references, keep_ids = annotation_references(annotations)
    expanded = expand_packet(root, partial_packet, references, keep_ids=keep_ids)
    assert any(e["id"] == volume[0]["id"] for e in expanded["entries"])
    bundle = assemble_annotations(annotations, expanded, root, context)
    actual = bundle["graph"]["claims"][0]["actual"]
    assert actual["op"] == "neg" and actual["args"][0]["op"] == "unknown"
    assert actual["args"][0]["args"][0]["op"] == "sum"
    assert bundle["assembly"]["relations"][0]["target"] == "V"
    assert bundle["analysis"]["code_grounding"][0]["status"] == "source_matched"
    assert bundle["analysis"]["alignments"][0]["status"] == "unknown"
    quantity = bundle["graph"]["quantities"][0]
    assert quantity["status"] == "unresolved" and all(quantity[k] is None for k in ("dimensions", "scale", "shape"))
    write_json(args.output / "handcrafted-annotations-009.json", annotations)
    write_json(args.output / "handcrafted-bundle-009.json", bundle)
    receipt["handcrafted_fixture"] = {"task_id": "009", "relations": bundle["assembly"]["relations"],
        "code_bindings": bundle["assembly"]["code_bindings"], "scientific_alignment": "unknown",
        "scientific_properties": "unresolved", "cast_subtree_retained": True,
        "missing_entry_restored": True}
    write_json(args.output / "verification.json", receipt)
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
