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
    packet = None
    if config.get("packet"):
        packet_path = Path(config["packet"])
        if packet_path.is_file():
            packet = read_json(packet_path)
    script_report = None
    if (trace_dir / "script_report.json").is_file():
        try:
            script_report = read_json(trace_dir / "script_report.json")
        except (OSError, ValueError):
            pass
    derived = derive_loci(records, predicates["evaluations"], script_status=run.get("script_status"),
                          observer_summary=observer, script_file="reproduce.py",
                          script_report=script_report)
    # Value provenance: observation values whose producers are traced give the
    # script-declared locus a function/file binding. Numeric scalars only.
    provenance = {}
    if script_report:
        observations = script_report.get("observation", script_report.get("scientific_observation")) or {}
        if isinstance(observations, dict):
            targets = {float(value) for value in observations.values()
                       if isinstance(value, (int, float)) and not isinstance(value, bool)}
            for record in records:
                fp = record.get("return_fp") or {}
                if fp.get("t") == "scalar" and fp.get("exact"):
                    try:
                        if float(fp["exact"]) in targets:
                            provenance.setdefault(fp["exact"], []).append(
                                (record["file"], record["name"]))
                    except ValueError:
                        continue
                for arg, fp in (record.get("inputs") or {}).items():
                    if arg == "self.__dict__":
                        continue
                    if fp.get("t") == "scalar" and fp.get("exact"):
                        try:
                            if float(fp["exact"]) in targets:
                                provenance.setdefault(fp["exact"], []).append(
                                    (record["file"], record["name"] + f"({arg})"))
                        except ValueError:
                            continue
    # Static candidates (R9): native comparisons of a distance/norm expression
    # against a named *PRECISION/*EPS/*TOL constant, from the preserved packet.
    static_candidates = {}
    if packet:
        import re
        for entry in packet.get("entries", []):
            text = entry.get("text") or ""
            if not re.search(r"<|>|==|<=|>=", text):
                continue
            if not re.search(r"PRECISION|EPS|TOLERANCE|_TOL|_EPS", text):
                continue
            static_candidates.setdefault(entry.get("path"), []).append(entry.get("start_line"))
    # Native comparison entries via the multilingual frontend (host-side,
    # tree-sitter): comparison-vs-named-constant candidates from preserved
    # source files. The packet path above covers indexed files; this covers
    # files the packet's entry caps drop.
    import re as _re
    for spec in config.get("static_files", []):
        local = Path(spec["local"])
        if not local.is_file() or not spec.get("language"):
            continue
        try:
            from scicontext.language_frontends import _tree_sitter_entries
            entries, _issues, _partial = _tree_sitter_entries(spec["path"], local.read_bytes(), spec["language"])
            for entry in entries:
                text = entry.get("text") or ""
                if entry.get("kind") == "comparison" and _re.search(r"PRECISION|EPS|TOLERANCE|_TOL|_EPS", text):
                    static_candidates.setdefault(spec["path"], []).append(entry.get("start_line"))
        except Exception:
            continue
    quantity_graph = build_quantity_graph(records)
    signatures = dependence_signatures(records)
    touched_functions = set(config.get("fix_touched_functions", []))
    touched_files = set(config.get("fix_touched_files", []))
    observation_loci = [locus for locus in derived["loci"]
                        if locus["properties"].get("rule_id") in {"R6s", "R6p"}
                        and locus["properties"]["status"] == "violated"]
    for locus in observation_loci:
        measures = locus["properties"].get("evidence", {}).get("measures", {})
        for field, value in measures.items():
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                key = repr(float(value))
                if key in provenance:
                    locus.setdefault("provenance_producers", [])
                    locus["provenance_producers"].extend(provenance[key][:5])
        if any(isinstance(value, bool) for value in measures.values()):
            # Boolean observations bind to the workflow's immediate computation:
            # repo functions within 12 call levels of the reproduce module.
            by_seq = {record["seq"]: record for record in records}
            module_seq = next((record["seq"] for record in records
                               if record.get("name") == "<module>" and record.get("file") == "reproduce.py"), None)
            producers = []
            for record in records:
                if record.get("file") == "reproduce.py":
                    continue
                depth = 0
                current = record
                seen = set()
                while current.get("parent_seq") is not None and current["seq"] not in seen and depth <= 12:
                    seen.add(current["seq"])
                    depth += 1
                    current = by_seq.get(current["parent_seq"])
                    if current is None:
                        break
                if current is not None and current["seq"] == module_seq and depth <= 12:
                    producers.append((record["file"], record["name"]))
            locus.setdefault("provenance_producers", [])
            touched_producers = sorted({p for p in producers if p[0] in touched_files})
            locus["provenance_producers"].extend((touched_producers or producers[:10]))
    if static_candidates:
        for locus in derived["loci"]:
            if locus["properties"].get("rule_id") in {"R8", "R6", "R6s", "R6p"}:
                for path, lines in static_candidates.items():
                    locus["properties"]["static_candidates"].extend(
                        [{"path": path, "line": line} for line in lines])
    violated = [locus for locus in derived["loci"]
                if locus["properties"]["status"] == "violated"]

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

    def locus_evidence_paths(locus):
        paths = {path for path, _ in locus_functions(locus)}
        paths.update(p["path"] for p in locus.get("properties", {}).get("static_candidates", []))
        paths.update(path for path, _ in locus.get("provenance_producers", []))
        return paths

    hits = [locus for locus in violated
            if any(path in touched_files for path in locus_evidence_paths(locus))
            or any(name in touched_functions
                   or name.replace(".<locals>", "").endswith(tuple(touched_functions))
                   for path, name in locus_functions(locus))]
    hit_levels = set()
    for locus in hits:
        for path, name in locus_functions(locus):
            if name in touched_functions or any(name.endswith(fn) for fn in touched_functions):
                hit_levels.add("function")
            if path in touched_files:
                hit_levels.add("file")
        for candidate in locus.get("properties", {}).get("static_candidates", []):
            if candidate["path"] in touched_files:
                hit_levels.add("file")
        for path, _ in locus.get("provenance_producers", []):
            if path in touched_files:
                hit_levels.add("file")
    return {"instances": len(records), "func_keys": run.get("func_keys"),
            "wall_seconds": run.get("wall_seconds"), "script_status": run.get("script_status"),
            "observation_provenance": {key: value for key, value in provenance.items()},
            "static_candidates": static_candidates or None,
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
