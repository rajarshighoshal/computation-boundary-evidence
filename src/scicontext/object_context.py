"""Scientific context for code-owned objects; model annotations do not own structure."""
from __future__ import annotations

import copy
import json
from collections import deque
from pathlib import Path

from jsonschema import Draft202012Validator

# Bounded slice of the object graph handed to the enrichment model. The full
# graph stays in the objects artifact; these caps only limit the model input.
ENRICHMENT_MAX_OBJECTS = 300
ENRICHMENT_MIN_OBJECTS = 25
ENRICHMENT_MAX_BYTES = 1_500_000
ENRICHMENT_MAX_UNSUPPORTED = 200
ENRICHMENT_LINK_DEPTH = 3

_CODE_PASSAGE_KEYS = ("id", "path", "sha256", "start_line", "end_line", "scope",
                      "text", "language", "native")
_OBJECT_KIND_PRIORITY = {"constraint_locus": 0, "transition_instance": 1, "state_quantity": 1,
                         "code_interface": 2, "quantity": 3, "graph": 3, "integral": 3,
                         "linear_system_solution": 3, "component_partition": 3,
                         "array": 4, "literal": 5}


def enrichment_schema() -> dict:
    return json.loads(Path(__file__).with_name("object-enrichment.schema.json").read_text())


def _selection_plan(graph: dict) -> dict:
    """BFS distances from workflow-retrieved interfaces and linked call sites."""
    adjacency = {}
    for link in graph.get("links", []):
        adjacency.setdefault(link["source"], []).append(link["target"])
        adjacency.setdefault(link["target"], []).append(link["source"])
    roots = [obj["id"] for obj in graph["objects"] if obj.get("kind") == "code_interface"]
    roots.extend(op["id"] for op in graph["operations"]
                 if op.get("properties", {}).get("retrieved_targets"))
    distance = {}
    frontier = deque((root, 0) for root in roots)
    while frontier:
        identifier, depth = frontier.popleft()
        if depth > ENRICHMENT_LINK_DEPTH or distance.get(identifier, ENRICHMENT_LINK_DEPTH + 1) <= depth:
            continue
        distance[identifier] = depth
        for neighbor in adjacency.get(identifier, []):
            if neighbor not in distance:
                frontier.append((neighbor, depth + 1))
    return distance


def _object_priority(identifier, object_map, distance):
    obj = object_map.get(identifier)
    depth = distance.get(identifier, ENRICHMENT_LINK_DEPTH + 1)
    if obj is None:
        return (depth, 4, 0, identifier)
    return (depth, _OBJECT_KIND_PRIORITY.get(obj.get("kind"), 2), -len(obj.get("roles", [])), identifier)


def enrichment_input(graph: dict, packet: dict) -> dict:
    """Supply scientific source material alongside the actual object relationships.

    The input is a bounded selection, not a graph dump: workflow-retrieved
    interfaces and their dataflow neighborhood are kept first, then everything
    else up to fixed object/byte budgets. A ``selection`` receipt records every
    drop as a structure-budget decision, not a scientific-relevance verdict.
    """
    payload = {key: copy.deepcopy(graph[key]) for key in ("objects", "operations", "links", "unsupported")}
    objects, operations, links, unsupported = (payload["objects"], payload["operations"],
                                               payload["links"], payload["unsupported"])
    distance = _selection_plan(graph)
    object_map = {obj["id"]: obj for obj in objects}
    ordered = sorted(objects, key=lambda obj: _object_priority(obj["id"], object_map, distance))

    def kept_operation(op, kept):
        if op["id"] in kept:
            return True
        if any(o in kept for o in op.get("output_ids", [])):
            return True
        if any(item.get("object_id") in kept for item in op.get("inputs", [])):
            return True
        return any(rt.get("object_id") in kept for rt in op.get("properties", {}).get("retrieved_targets", []))

    def assemble(kept):
        op_ids = {op["id"] for op in operations if kept_operation(op, kept)}
        entry_ids = {eid for obj in objects if obj["id"] in kept for eid in obj["source_entry_ids"]}
        entry_ids.update(op["source_entry_id"] for op in operations if op["id"] in op_ids)
        scopes = {(obj["path"], obj["scope"]) for obj in objects if obj["id"] in kept}
        source_paths = {obj["path"] for obj in objects if obj["id"] in kept}
        code_passages = [{key: entry.get(key) for key in _CODE_PASSAGE_KEYS}
                         for entry in packet.get("entries", [])
                         if entry["id"] in entry_ids
                         or entry["kind"] == "docstring" and entry["path"] in source_paths
                         or entry["kind"] == "signature" and (entry["path"], entry["scope"]) in scopes]
        selected_unsupported = [item for item in unsupported
                                if item.get("source_entry_id") in entry_ids
                                or item.get("source_entry_id") is None  # file-level parse/omission records
                                or item.get("path") in source_paths]
        selected_unsupported = selected_unsupported[:ENRICHMENT_MAX_UNSUPPORTED]
        selected_links = [link for link in links
                          if link["source"] in kept | op_ids and link["target"] in kept | op_ids]
        return {"objects": [obj for obj in objects if obj["id"] in kept],
                "operations": [op for op in operations if op["id"] in op_ids],
                "links": selected_links,
                "unsupported": selected_unsupported,
                "context": {"scientific_passages": copy.deepcopy(packet.get("documents", [])),
                            "code_passages": code_passages}}

    kept = {obj["id"] for obj in ordered[:ENRICHMENT_MAX_OBJECTS]}
    selected = assemble(kept)
    truncated = False
    for _ in range(max(0, len(kept) - ENRICHMENT_MIN_OBJECTS) + 1):
        if len(json.dumps(selected, ensure_ascii=False).encode()) <= ENRICHMENT_MAX_BYTES or len(kept) <= ENRICHMENT_MIN_OBJECTS:
            break
        truncated = True
        kept.remove(next(obj for obj in reversed(ordered) if obj["id"] in kept)["id"])
        selected = assemble(kept)
    documents_trimmed = False
    while (len(json.dumps(selected, ensure_ascii=False).encode()) > ENRICHMENT_MAX_BYTES
           and selected["context"]["scientific_passages"]):
        passages = selected["context"]["scientific_passages"]
        passages.pop(max(range(len(passages)), key=lambda i: len(json.dumps(passages[i]))))
        documents_trimmed = True
        truncated = True
    # Any budget that forced a drop counts as truncation, including the object,
    # unsupported-item and link caps, not only the byte loop.
    truncated = truncated or (len(kept) < len(objects)
                              or len(selected["unsupported"]) < len(unsupported)
                              or len(selected["links"]) < len(links))
    selection = {"total_objects": len(objects), "kept_objects": len(kept),
                 "total_operations": len(operations), "kept_operations": len(selected["operations"]),
                 "total_links": len(links), "kept_links": len(selected["links"]),
                 "total_unsupported": len(unsupported), "kept_unsupported": len(selected["unsupported"]),
                 "workflow_roots": sum(1 for d in distance.values() if d == 0),
                 "workflow_reachable": sum(1 for d in distance.values() if d <= ENRICHMENT_LINK_DEPTH),
                 "limits": {"max_objects": ENRICHMENT_MAX_OBJECTS, "min_objects": ENRICHMENT_MIN_OBJECTS,
                            "max_bytes": ENRICHMENT_MAX_BYTES, "max_unsupported": ENRICHMENT_MAX_UNSUPPORTED,
                            "link_depth": ENRICHMENT_LINK_DEPTH},
                 "truncated": truncated, "documents_trimmed": documents_trimmed,
                 "note": "Bounded context slice for the enrichment model; the full graph remains in the objects artifact. Drops record structure-budget decisions, not scientific irrelevance."}
    selected["selection"] = selection
    selection["serialized_bytes"] = len(json.dumps(selected, ensure_ascii=False).encode())
    return selected


def enrich_objects(graph: dict, response: object) -> dict:
    """Join only anchored meaning/conventions/assumptions; preserve every code fact."""
    result = copy.deepcopy(graph)
    objects = {obj["id"]: obj for obj in result["objects"]}
    report = {"applied_object_ids": [], "dropped": []}
    result["enrichment"] = report
    schema = enrichment_schema()
    normalized = False
    if isinstance(response, dict) and isinstance(response.get("annotations"), list):
        annotations = []
        for annotation in response["annotations"]:
            if not isinstance(annotation, dict):
                continue
            for field in ("conventions", "assumptions"):
                if isinstance(annotation.get(field), str):
                    annotation = {**annotation, field: [annotation[field]]}
                    normalized = True
            annotations.append(annotation)
        if "schema_version" not in response:
            response = {**response, "schema_version": "object-enrichment-1.0"}
            normalized = True
        response = {**response, "annotations": annotations}
    if normalized:
        report["normalized"] = "coerced string conventions/assumptions to arrays; assumed schema_version"
    envelope = {**response, "annotations": []} if isinstance(response, dict) and isinstance(
        response.get("annotations"), list) else response
    errors = list(Draft202012Validator(schema).iter_errors(envelope))
    if errors:
        report["dropped"].append({"reason": "invalid_enrichment_envelope", "errors": len(errors)})
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
            "handoff": render_guide(combined) if usable else "",
            "context": copy.deepcopy(context),
            "assembly": {"usable": usable, "status": "scientific_objects" if usable else "no_objects",
                         "interpretation_status": "enriched" if combined["enrichment"]["applied_object_ids"] else "code_only",
                         "enrichment": combined["enrichment"]},
            "analysis": {"coverage": combined.get("coverage", {}).get("totals", {})},
            "validation": {"valid": True, "scope": "code_owned_structure_and_anchored_annotation_fields"}}


MAX_GUIDE_FINDINGS = 5
MAX_GUIDE_ANNOTATIONS = 8
_RULE_STRENGTH = {"R1": 0, "R2": 1, "R6s": 2, "R6": 3, "R6p": 4, "R4": 5, "R5": 6, "R8": 7}


def _finding_statement(locus: dict) -> str:
    properties = locus.get("properties", {})
    evidence = properties.get("evidence", {})
    rule = properties.get("rule_id")
    symbol = locus.get("symbol")
    path = locus.get("path")
    line = locus.get("source_span", {}).get("start_line")
    site = f"{symbol} ({path}:{line})" if line else f"{symbol} ({path})"
    pairs = evidence.get("pairs", [])
    measures = evidence.get("measures", {})
    if rule == "R1":
        delta = next((p.get("delta_param") for p in pairs if p.get("delta_param")), None)
        if delta:
            return (f"changing {delta['name']} from {delta['a']} to {delta['b']} leaves the output "
                    f"of {site} identical across {len(pairs)} observed pair(s)")
    if rule == "R2":
        return f"related inputs (relabeled or reversed) produce different outputs at {site}"
    if rule == "R4":
        return f"distinct inputs produce identical outputs at {site} ({len(pairs)} observed pair(s))"
    if rule in {"R6", "R6s", "R6p"}:
        measure_text = ", ".join(f"{field} = {value}" for field, value in measures.items())
        kind = properties.get("constraint_type")
        statement = (f"the workflow reports {measure_text} ({kind} violated)" if measure_text
                     else f"the workflow fails its {kind} check")
        candidates = properties.get("static_candidates", [])
        if candidates:
            sites = "; ".join(f"{item['path']}:{item['line']}" for item in candidates[:4])
            statement += f"; tolerance-style comparisons in the native source: {sites}"
        return statement
    if rule == "R5":
        return f"computed quantities at {site} contain nan/inf values"
    return f"{properties.get('constraint_type')} finding at {site}"


def render_guide(graph: dict) -> str:
    """Readable guide: the strongest executed findings, stated as measurements."""
    lines = ["# Scientific working model", ""]
    loci = [obj for obj in graph.get("objects", []) if obj.get("kind") == "constraint_locus"
            and obj.get("properties", {}).get("status") == "violated"]
    loci.sort(key=lambda locus: (_RULE_STRENGTH.get(locus["properties"].get("rule_id"), 9),
                                 -len(locus["properties"].get("evidence", {}).get("pairs", [])),
                                 locus["id"]))
    if loci:
        lines += ["## Executed evidence from the public reproducer", ""]
        for locus in loci[:MAX_GUIDE_FINDINGS]:
            lines.append("- " + _finding_statement(locus))
        lines.append("")
    lines += ["Interpretations are anchored to object IDs and public source passages; "
              "the complete object graph is in scientific-graph.json.", ""]
    loci_paths = {locus.get("path") for locus in loci[:MAX_GUIDE_FINDINGS]}
    annotated = [obj for obj in graph["objects"] if obj.get("interpretation")]
    if loci_paths:
        annotated.sort(key=lambda obj: (obj.get("path") not in loci_paths,
                                        obj.get("kind") != "code_interface",
                                        obj["id"]))
    else:
        annotated.sort(key=lambda obj: (obj.get("kind") != "code_interface", obj["id"]))
    for obj in annotated[:MAX_GUIDE_ANNOTATIONS]:
        interpretation = obj.get("interpretation")
        if not interpretation:
            continue
        span = obj.get("source_span", {})
        lines += [f"## {obj['id']} — {obj.get('symbol') or obj['kind']}",
                  f"Source: {obj['path']}:{span.get('start_line', '?')}-{span.get('end_line', '?')}; scope: {obj['scope']}",
                  "Computational roles: " + ", ".join(obj.get("roles", []))]
        if interpretation.get("meaning"):
            lines.append("Scientific meaning: " + interpretation["meaning"])
        for field in ("conventions", "assumptions"):
            for statement in interpretation.get(field, []):
                lines.append(f"- {field}: {statement}")
        lines.append("")
    if not annotated:
        lines += ["No scientific annotations were accepted. The graph contains code structure only.", ""]
    lines += ["## Coverage (not scientific correctness)",
              json.dumps(graph.get("coverage", {}).get("totals", {}), sort_keys=True),
              "Unsupported structures and dropped annotations are recorded in the full graph."]
    return "\n".join(lines) + "\n"
