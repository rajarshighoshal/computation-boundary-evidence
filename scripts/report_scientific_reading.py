#!/usr/bin/env python3
"""Report anchored scientific-reading artifacts and costs, not repair effectiveness."""
import argparse
import json
from datetime import datetime
from pathlib import Path

from report_comparison import number, read, table
from report_task_local_extractor import collect
from scicontext.io import digest_file


def summarize_graph(graph):
    if not isinstance(graph, dict) or graph.get("schema_version") != "scientific-objects-1.0":
        return None
    objects = graph["objects"]
    interfaces = [o for o in objects if o["kind"] == "code_interface"]
    model = graph.get("scientific_model", {})
    interpreted = {o["id"] for o in objects if o.get("interpretation") and "id" in o}
    interpreted.update(c["id"] for c in model.get("computations", []))
    interpreted.update(q["object_id"] for c in model.get("computations", []) for q in c["interpretation"]["quantities"])
    model_sources = {s["id"]: s for s in model.get("sources", [])}
    model_paths = {model_sources[s]["path"] for c in model.get("computations", [])
                   for s in c["source_ids"] if s in model_sources}
    annotated = lambda obj: bool(obj.get("interpretation")) or obj.get("id") in interpreted
    return {"objects": len(objects), "interpreted_objects": sum(annotated(o) for o in objects),
            "interfaces": len(interfaces), "interpreted_interfaces": sum(annotated(o) for o in interfaces),
            "interpreted_computations": len(model.get("computations", [])),
            "interpretation_version": model.get("schema_version", "object-enrichment-1.0"),
            "source_paths": sorted({o["path"] for o in objects}),
            "interpreted_source_paths": sorted({o["path"] for o in objects if annotated(o)} | model_paths),
            "coverage": graph.get("coverage"), "enrichment": graph.get("enrichment")}


def report(root):
    result = collect(root)  # Reuse existing graph, stage, selection and token audits.
    if result["schedule"]["config"].get("extractor") != "scientific_objects":
        raise ValueError("This report requires scientific-object mode")
    for record in result["records"]:
        trial = root / record["trial_path"] if record.get("trial_path") else None
        path = trial / "graph-bundle.json" if trial else None
        bundle = read(path) if path and path.is_file() else {}
        record["scientific_objects"] = summarize_graph(bundle.get("graph"))
        record["interpretation_status"] = bundle.get("assembly", {}).get("interpretation_status", "unavailable")
        if len(record.get("model_calls") or []) > 1:
            raise ValueError("Scientific reading protocol permits one model call per task")
    result["token_totals"] = {k: sum(r["tokens"][k] for r in result["records"])
        if all(type(r["tokens"].get(k)) is int for r in result["records"]) else None
        for k in ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens", "total_tokens")}
    schedule = result["schedule"]
    result["schedule_wall_seconds"] = ((datetime.fromisoformat(schedule["finished_at"]) -
        datetime.fromisoformat(schedule["started_at"])).total_seconds() if schedule.get("finished_at") and schedule.get("started_at") else None)
    result["public_review_source_hashes"] = {str(p.relative_to(root)): digest_file(p)
        for p in sorted((root / "public-review").rglob("*")) if p.is_file()}
    return result


def render(result):
    lines = ["# Scientific-reading development checks", "",
        "Full public task workspaces; one scientific-reading call per task. No repair or verifier runs. "
        "Annotation counts measure delivery and anchoring, not scientific correctness or repair benefit.", "",
        f"Schedule: {result['schedule'].get('status')}. Implementation: `{result['schedule'].get('implementation_revision')}`.", "",
        f"Schedule wall time, including preparation: {number(result.get('schedule_wall_seconds'))} seconds.", ""]
    records = result["records"]
    def metric(record, name):
        value = record.get("scientific_objects")
        return value.get(name) if value else None
    table(lines, ["Task", "Call status", "Interpretation", "Objects", "Annotated", "Interfaces", "Annotated interfaces", "Total seconds"],
        [(r["task_id"], r["stage_status"], r["interpretation_status"], metric(r, "objects"), metric(r, "interpreted_objects"),
          metric(r, "interfaces"), metric(r, "interpreted_interfaces"), number(r["seconds"])) for r in records])
    lines += ["", "## Token accounting", ""]
    table(lines, ["Task", "Input", "Cached input (subset)", "Output", "Reasoning (output subset)", "Total"],
        [(r["task_id"], *(number(r["tokens"][k], 0) for k in
          ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens", "total_tokens"))) for r in records] +
          [("All tasks", *(number(result["token_totals"][k], 0) for k in
            ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens", "total_tokens")))])
    lines += ["", "Total is input plus output. Cached input and reasoning are already included. "
              "Missing or incomplete call costs remain unknown; no subscription-to-dollar estimate is made.", ""]
    for r in records:
        lines += [f"## Task {r['task_id']}", ""]
        obj = r.get("scientific_objects")
        lines += ["Interpreted source paths: " + (", ".join(f"`{p}`" for p in obj["interpreted_source_paths"]) if obj else "unavailable") + ".", ""]
        table(lines, ["Phase", "Status", "Allowance seconds", "Elapsed seconds"],
            [(p.get("name"), p.get("status"), number(p.get("allowance_seconds")), number(p.get("duration_seconds"))) for p in r.get("phases") or []])
        table(lines, ["Call", "Status", "Model cap seconds", "Call elapsed seconds"],
            [(c["name"], c.get("status"), number(c.get("timeout_seconds")), number(c.get("duration_seconds"))) for c in r.get("model_calls") or []])
        lines += ["Raw trial: `" + str(r.get("trial_path")) + "`.", ""]
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--json-output", type=Path, required=True)
    parser.add_argument("--markdown-output", type=Path, required=True)
    args = parser.parse_args()
    result = report(args.run_root)
    for path, content in [(args.json_output, json.dumps(result, indent=2, sort_keys=True)),
                          (args.markdown_output, render(result))]:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content.rstrip() + "\n")


if __name__ == "__main__":
    main()
