"""Offline loci evaluation over the five development tasks.

Reads the predeclared configs/loci-eval-v1.json, derives the constraint
structure from each task's preserved trace, and reports hit/precision per
task against the fix-touched sets plus the workflow status. Flip tests are
run separately in containers and recorded under flip_status.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from scicontext.dynamic_binding import build_quantity_graph, dependence_signatures
from scicontext.io import read_json, write_json
from scicontext.relations import derive_loci, load_trace


def evaluate_task(trace_dir: Path, config: dict) -> dict:
    records = load_trace(trace_dir / "trace.jsonl.gz")
    predicates = read_json(trace_dir / "script_predicates.json")
    run = read_json(trace_dir / "run.json")
    observer = None
    if (trace_dir / "observer_summary.json").is_file():
        observer = read_json(trace_dir / "observer_summary.json")
    script_report = None
    if (trace_dir / "script_report.json").is_file():
        try:
            script_report = read_json(trace_dir / "script_report.json")
        except (OSError, ValueError):
            pass
    derived = derive_loci(records, predicates["evaluations"], script_status=run.get("script_status"),
                          observer_summary=observer, script_file="reproduce.py",
                          script_report=script_report)
    quantity_graph = build_quantity_graph(records)
    signatures = dependence_signatures(records)
    violated = [locus for locus in derived["loci"]
                if locus["properties"]["status"] == "violated"]
    touched_functions = set(config.get("fix_touched_functions", []))
    touched_files = set(config.get("fix_touched_files", []))

    def locus_functions(locus):
        functions = set()
        transitions = locus["properties"].get("locus_transitions") or []
        for seq in transitions:
            record = next((r for r in records if r["seq"] == seq), None)
            if record:
                functions.add((record["file"], record["name"]))
        if not functions:
            functions.add((locus.get("path"), locus.get("symbol", "").split("@")[-1]))
        return functions

    hits = [locus for locus in violated
            if any(path in touched_files or name in touched_functions
                   or name.replace(".<locals>", "").endswith(tuple(touched_functions))
                   for path, name in locus_functions(locus))]
    hit_levels = set()
    for locus in hits:
        for path, name in locus_functions(locus):
            if name in touched_functions or any(name.endswith(fn) for fn in touched_functions):
                hit_levels.add("function")
            if path in touched_files:
                hit_levels.add("file")
    return {"instances": len(records), "func_keys": run.get("func_keys"),
            "wall_seconds": run.get("wall_seconds"), "script_status": run.get("script_status"),
            "loci_total": len(derived["loci"]), "loci_violated": len(violated),
            "hit": bool(hits), "hit_level": sorted(hit_levels) if hits else None,
            "hit_loci": [{"id": locus["id"], "symbol": locus["symbol"],
                          "rule": locus["properties"]["rule_id"],
                          "path": locus.get("path")} for locus in hits],
            "precision": len(hits) / len(violated) if violated else None,
            "quantities": len(quantity_graph["quantities"]),
            "transitions": len(quantity_graph["transitions"]),
            "signatures": len(signatures),
            "no_effect_arguments": [
                {"func": sig["func"][1], "args": [arg for arg, kind in sig["arguments"].items() if kind == "no_effect"]}
                for sig in signatures
                if any(kind == "no_effect" for kind in sig["arguments"].values())],
            "nondeterministic": len(derived["dynamic"]["nondeterministic_funcs"]),
            "observer": {"processes": len((observer or {}).get("processes", [])),
                         "files": len((observer or {}).get("files", [])),
                         "stall": (observer or {}).get("stall")} if observer else None,
            "flip_status": config.get("flip_status", "not_run")}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/loci-eval-v1.json"))
    parser.add_argument("--output", type=Path, default=Path("results/loci-eval-v1.json"))
    args = parser.parse_args()
    config = read_json(args.config)
    results = {"config": str(args.config), "stop_rules": config.get("stop_rules"),
               "tasks": {}}
    for task_id, task_config in config["tasks"].items():
        trace_dir = Path(task_config["trace_dir"])
        if not trace_dir.is_dir():
            results["tasks"][task_id] = {"error": f"missing trace dir {trace_dir}"}
            continue
        results["tasks"][task_id] = evaluate_task(trace_dir, task_config)
    write_json(args.output, results)
    hits = [tid for tid, record in results["tasks"].items()
            if isinstance(record, dict) and record.get("hit")]
    print(json.dumps({"tasks": {tid: {"hit": r.get("hit"), "hit_level": r.get("hit_level"),
                                     "loci_violated": r.get("loci_violated"),
                                     "precision": r.get("precision"),
                                     "script_status": r.get("script_status")}
                               for tid, r in results["tasks"].items()},
                      "function_or_file_hits": hits}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
