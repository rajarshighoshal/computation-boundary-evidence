#!/usr/bin/env python3
"""Auditable before/after extraction comparison; no repair or scientific-accuracy score."""
import argparse
import json
from pathlib import Path

from report_comparison import number, read, table
from report_scientific_reading import report


def source_annotations(root, record):
    if not record.get("trial_path"):
        return None
    path = root / record["trial_path"] / "graph-bundle.json"
    if not path.is_file():
        return None
    graph = read(path)["graph"]
    return [{"object_id": o["id"], "kind": o["kind"], "path": o["path"], "scope": o["scope"],
             "source_span": o["source_span"], "symbol": o.get("symbol"),
             "declaration_only": bool(o.get("properties", {}).get("interface", {}).get("declaration_only")),
             "interpretation": o["interpretation"]} for o in graph["objects"] if o.get("interpretation")]


def compare(before_root, after_root):
    before, after = report(before_root), report(after_root)
    if before["task_ids"] != after["task_ids"]:
        raise ValueError("Before/after task order differs")
    matched_fields = ("model", "reasoning_effort", "codex_version", "pier_version", "release_commit",
                      "dataset_revision", "extraction_model_seconds", "extraction_seconds", "total_seconds", "attempts", "concurrency")
    if any(before["schedule"]["config"].get(k) != after["schedule"]["config"].get(k) for k in matched_fields):
        raise ValueError("Before/after model, environment or budget settings differ")
    if before["schedule"].get("selection_sha256") != after["schedule"].get("selection_sha256"):
        raise ValueError("Before/after materialized task selection differs")
    if before["schedule"].get("prompt_sha256", {}).get("prompts/enrich_objects.md") != after["schedule"].get("prompt_sha256", {}).get("prompts/enrich_objects.md"):
        raise ValueError("Before/after scientific-reading prompt differs")
    rows = []
    for old, new in zip(before["records"], after["records"]):
        row = {"task_id": old["task_id"]}
        for label, root, record in [("before", before_root, old), ("after", after_root, new)]:
            annotations = source_annotations(root, record)
            source = [o for o in annotations if o["path"].startswith("source/")] if annotations is not None else None
            row[label] = {"status": record["stage_status"], "interpretation_status": record["interpretation_status"],
                "seconds": record["seconds"], "tokens": record["tokens"], "trial_path": record["trial_path"],
                "annotations": annotations, "annotated_repository_objects": len(source) if source is not None else None,
                "annotated_repository_paths": sorted({o["path"] for o in source}) if source is not None else None,
                "annotated_declaration_interfaces": sum(o["declaration_only"] for o in source) if source is not None else None}
        a, b = row["before"]["tokens"]["total_tokens"], row["after"]["tokens"]["total_tokens"]
        row["token_change_fraction"] = b / a - 1 if isinstance(a, int) and a > 0 and isinstance(b, int) else None
        rows.append(row)
    return {"kind": "development_scientific_context_before_after", "before_root": str(before_root),
        "after_root": str(after_root), "rows": rows,
        "before_implementation": before["schedule"]["implementation_revision"],
        "after_implementation": after["schedule"]["implementation_revision"],
        "matched_protocol_fields": list(matched_fields), "before_tokens": before["token_totals"],
        "after_tokens": after["token_totals"],
        "total_token_change_fraction": (after["token_totals"]["total_tokens"] / before["token_totals"]["total_tokens"] - 1
            if before["token_totals"].get("total_tokens") and isinstance(after["token_totals"].get("total_tokens"), int) else None),
        "scope": "Source-path annotation counts are structural diagnostics, not scientific quality or repair effectiveness. These development tasks informed the revision; this is not held-out evidence."}


def render(result):
    lines = ["# Scientific context: before and after workflow retrieval", "", result["scope"], "",
        f"Before implementation: `{result['before_implementation']}`. After run-control revision: `{result['after_implementation']}`.", ""]
    table(lines, ["Task", "Repository annotations before", "After", "Tokens before", "After", "Token change"],
        [(r["task_id"], r["before"]["annotated_repository_objects"], r["after"]["annotated_repository_objects"],
          number(r["before"]["tokens"]["total_tokens"], 0), number(r["after"]["tokens"]["total_tokens"], 0),
          number(r["token_change_fraction"] * 100) + "%" if r["token_change_fraction"] is not None else "unknown") for r in result["rows"]])
    for row in result["rows"]:
        lines += ["", f"## Task {row['task_id']}", ""]
        for label in ("before", "after"):
            item = row[label]
            paths = item["annotated_repository_paths"]
            lines += [f"{label.title()} repository paths: " + (", ".join(f"`{p}`" for p in paths) if paths else "none or unavailable") + ".", ""]
    lines += ["The JSON comparison includes the exact annotated objects and interpretation text for qualitative review. "
              "Cached-input and reasoning counts are preserved as subsets; they are not added twice. "
              "No efficacy or causal claim follows from these counts."]
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", type=Path, required=True)
    parser.add_argument("--after", type=Path, required=True)
    parser.add_argument("--json-output", type=Path, required=True)
    parser.add_argument("--markdown-output", type=Path, required=True)
    args = parser.parse_args()
    result = compare(args.before, args.after)
    for path, text in [(args.json_output, json.dumps(result, indent=2, sort_keys=True)), (args.markdown_output, render(result))]:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text.rstrip() + "\n")


if __name__ == "__main__":
    main()
