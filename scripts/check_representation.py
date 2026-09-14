"""Replay preserved public extraction evidence offline; never call a model or verifier."""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from scicontext.io import digest_file, write_json
from scicontext.object_context import enrichment_input
from scicontext.representation import reading_input, render_reading
from scicontext.packet import build_packet
from scicontext.scientific_objects import extract_objects
from scicontext.execution_seed import read_execution


def size(value):
    return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--public-originals", type=Path,
                        help="Optional preserved task_TTT/context_TTT directories for fresh static selection")
    parser.add_argument("--public-cache", type=Path, help="Pinned public workspaces created by check_task_retrieval.py --prepare-only")
    parser.add_argument("--execution-seeded", action="store_true")
    args = parser.parse_args()
    rows = []
    for directory in sorted(args.run.glob("jobs/task-*-science/*/agent")):
        start = time.monotonic()
        packet_file = directory / "extract-scratch/packet.json"
        graph_file = directory / "extract-scratch/scientific-objects.json"
        raw_file = directory / "source-analysis/evidence-input.json"
        before_file = directory / "source-analysis/input.json"
        packet, graph, raw, before = (json.loads(p.read_text()) for p in (packet_file, graph_file, raw_file, before_file))
        task = directory.parent.parent.name.removeprefix("task-").removesuffix("-science")
        refreshed = False
        root = args.public_originals / ("task_" + task) if args.public_originals else None
        context_dir = args.public_originals / ("context_" + task) if args.public_originals else None
        if args.public_cache:
            cached = list(args.public_cache.glob(task + "-*/receipt.json"))
            if len(cached) != 1:
                raise ValueError("Expected one pinned public workspace for " + task)
            root = cached[0].parent / "task"
            context_dir = args.output / task / "context"
            context_dir.mkdir(parents=True, exist_ok=True)
            (context_dir / "task_statement.md").write_bytes((Path("data/release/tasks") / ("task_" + task) / "instruction.md").read_bytes())
        if root and root.is_dir():
            # Refuse a repaired/different source snapshot before replaying selection.
            for entry in packet["entries"]:
                path = root / entry["path"]
                if path.is_file():
                    assert digest_file(path) == entry["sha256"], f"Source mismatch: {task}/{entry['path']}"
            documents, observations = packet["documents"], graph.get("dynamic", {})
            execution = read_execution(directory / "extract-scratch/trace") if args.execution_seeded else None
            packet = build_packet(root, context_dir, multilingual=True,
                                  seed=execution["functions"] if execution else None, execution=execution)
            graph = extract_objects(root, packet)
            graph["dynamic"] = observations
            refreshed = True
        payload = enrichment_input(graph, packet)
        payload["context"]["analysis_sources"] = raw["context"].get("analysis_sources", [])
        view = reading_input(payload)
        assert view == reading_input(payload), "Non-deterministic projection"
        ids = {item["id"] for item in view["entities"]}
        sources = {item["id"] for item in view["sources"]}
        templates = {item["id"] for item in view["templates"]}
        assert all(e["source"] in ids and e["target"] in ids for e in view["relations"])
        assert all(set(e["source_ids"]) <= sources for e in view["entities"])
        assert all(not e.get("template_id") or e["template_id"] in templates for e in view["entities"])
        assert all(b.get("definition_id") is None or b["definition_id"] in ids for e in view["entities"] for b in e.get("bindings", []))
        assert all(c.get("predicate_id") is None or c["predicate_id"] in ids for e in view["entities"] for c in e.get("condition_refs", []))
        write_json(args.output / task / "scientific-context-input.json", view)
        write_json(args.output / task / "packet.json", packet)
        reading = render_reading(view)
        assert all(f"[{r[k]}]" in reading for r in view["relations"] for k in ("source", "target"))
        (args.output / task / "scientific-reading.md").write_text(reading)
        row = {"task_id": task, "before_compact_json_bytes": size(before), "after_compact_json_bytes": size(view),
               "before_provider_payload_bytes": len(json.dumps(before, ensure_ascii=False).encode()),
               "reader_bytes": len(reading.encode()),
               "refreshed_static_selection": refreshed,
               "execution": view.get("execution"),
               "elapsed_seconds": time.monotonic() - start, "counts": {key: len(view[key]) for key in
                ("computations", "entities", "templates", "relations", "sources")}, "coverage": view["coverage"],
               "input_sha256": {str(p): digest_file(p) for p in (packet_file, graph_file, raw_file, before_file)}}
        rows.append(row)
        print(json.dumps({k: row[k] for k in ("task_id", "before_compact_json_bytes", "after_compact_json_bytes", "reader_bytes", "counts")}))
    write_json(args.output / "receipt.json", {"scope": "Offline representation replay, not automatic scientific interpretation or repair quality",
        "model_calls": 0, "rows": rows,
        "implementation_sha256": {str(p): digest_file(p) for p in sorted(Path("src/scicontext").glob("*.py"))},
        "script_sha256": digest_file(Path(__file__))})


if __name__ == "__main__":
    main()
