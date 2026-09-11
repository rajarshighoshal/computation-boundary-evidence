"""Scientific context for code-owned objects; model annotations do not own structure."""
from __future__ import annotations

import copy
import json
from pathlib import Path

from jsonschema import Draft202012Validator


def enrichment_schema() -> dict:
    return json.loads(Path(__file__).with_name("object-enrichment.schema.json").read_text())


def enrichment_input(graph: dict, packet: dict) -> dict:
    """Supply scientific source material alongside the actual object relationships."""
    payload = {key: copy.deepcopy(graph[key]) for key in ("objects", "operations", "links", "unsupported")}
    ids = {identifier for obj in graph["objects"] for identifier in obj["source_entry_ids"]}
    ids.update(op["source_entry_id"] for op in graph["operations"])
    scopes = {(obj["path"], obj["scope"]) for obj in graph["objects"]}
    source_paths = {obj["path"] for obj in graph["objects"]}
    payload["context"] = {
        "scientific_passages": copy.deepcopy(packet.get("documents", [])),
        "code_passages": [{key: entry.get(key) for key in
            ("id", "path", "sha256", "start_line", "end_line", "scope", "text", "language", "native")}
            for entry in packet.get("entries", []) if entry["id"] in ids or
            entry["kind"] == "docstring" and entry["path"] in source_paths or
            entry["kind"] == "signature" and (entry["path"], entry["scope"]) in scopes],
    }
    return payload


def enrich_objects(graph: dict, response: object) -> dict:
    """Join only anchored meaning/conventions/assumptions; preserve every code fact."""
    result = copy.deepcopy(graph)
    objects = {obj["id"]: obj for obj in result["objects"]}
    report = {"applied_object_ids": [], "dropped": []}
    result["enrichment"] = report
    schema = enrichment_schema()
    envelope = {**response, "annotations": []} if isinstance(response, dict) and isinstance(
        response.get("annotations"), list) else response
    errors = list(Draft202012Validator(schema).iter_errors(envelope))
    if errors:
        report["dropped"].append({"reason": "invalid_enrichment_envelope"})
        return result
    item_schema = {**schema["$defs"]["annotation"], "$defs": schema["$defs"]}
    validator = Draft202012Validator(item_schema)
    for index, annotation in enumerate(response["annotations"]):
        identifier = annotation.get("object_id") if isinstance(annotation, dict) else None
        reason = ("invalid_annotation_fields" if not validator.is_valid(annotation) else
                  "unanchored_object_id" if identifier not in objects else
                  "duplicate_object_id" if identifier in report["applied_object_ids"] else None)
        if reason:
            report["dropped"].append({"index": index, "object_id": identifier, "reason": reason})
            continue
        objects[identifier]["interpretation"] = {
            **{key: copy.deepcopy(annotation[key]) for key in ("meaning", "conventions", "assumptions")
               if key in annotation},
            "status": "contextual_interpretation_not_code_fact",
        }
        report["applied_object_ids"].append(identifier)
    return result


def render_objects(graph: dict) -> str:
    """An inspectable scientific working model, not a list of required patches."""
    lines = ["# Scientific working model", "",
        "Code-derived objects and relationships are below. Contextual meanings are interpretations "
        "of the supplied scientific material, not mandatory repair rules. Read stated scope and unknowns.", ""]
    for obj in graph["objects"]:
        lines.append(f"- {obj['id']} — {obj.get('symbol') or obj['kind']} ({obj['kind']})")
        span = obj.get("source_span", {})
        lines.append(f"  Source: {obj['path']}:{span.get('start_line', '?')}-{span.get('end_line', '?')}; scope: {obj['scope']}")
        lines.append("  Computational roles: " + ", ".join(obj.get("roles", [])))
        lines.append("  Code-derived properties: " + json.dumps(obj["properties"], sort_keys=True))
        interpretation = obj.get("interpretation", {})
        if interpretation.get("meaning"):
            lines.append("  Scientific meaning: " + interpretation["meaning"])
        for field in ("conventions", "assumptions"):
            for statement in interpretation.get(field, []):
                lines.append(f"  {field}: {statement}")
    lines += ["", "## Computational relationships", ""]
    for op in graph["operations"]:
        operands = ", ".join(f"{item['role']}={item.get('object_id') or 'unknown'}" for item in op["inputs"])
        lines.append(f"- {op['id']} {op['kind']}: {operands} -> {', '.join(op['output_ids'])}")
        source = op.get("source", {})
        lines.append(f"  Source: {source.get('path', '?')}:{source.get('start_line', '?')}-{source.get('end_line', '?')}")
        lines.append("  Parameters/contract: " + json.dumps(op.get("properties", {}), sort_keys=True))
        for assumption in op.get("assumptions", []):
            lines.append("  Applies under: " + assumption)
        if op.get("documentation_url"):
            lines.append("  API source: " + op["documentation_url"])
    lines += ["", "## Dataflow and interface links", ""]
    for link in graph.get("links", []):
        lines.append(f"- {link['source']} --{link['relation']}--> {link['target']}")
    lines += ["", "## Unresolved structure and interpretation omissions", ""]
    for issue in [*graph.get("unsupported", []), *graph.get("enrichment", {}).get("dropped", [])]:
        lines.append("- " + json.dumps(issue, sort_keys=True))
    coverage = graph.get("coverage", {})
    lines += ["", "## Extraction coverage (not scientific correctness)", "",
              json.dumps(coverage.get("totals", {}), sort_keys=True)]
    for row in coverage.get("per_file", []):
        lines.append("- " + json.dumps(row, sort_keys=True))
    return "\n".join(lines) + "\n"


def object_bundle(graph: dict, response: object, context: dict | None = None) -> dict:
    from .io import digest_json
    combined = enrich_objects(graph, response)
    usable = bool(combined["objects"])
    return {"graph": combined, "graph_sha256": digest_json(combined),
            "handoff": render_objects(combined) if usable else "",
            "context": copy.deepcopy(context),
            "assembly": {"usable": usable, "status": "scientific_objects" if usable else "no_objects",
                         "interpretation_status": "enriched" if combined["enrichment"]["applied_object_ids"] else "code_only",
                         "enrichment": combined["enrichment"]},
            "analysis": {"coverage": combined.get("coverage", {}).get("totals", {})},
            "validation": {"valid": True, "scope": "code_owned_structure_and_anchored_annotation_fields"}}
