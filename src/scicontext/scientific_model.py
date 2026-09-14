"""Join scientific interpretation to existing computations, never invent program edges."""
from __future__ import annotations

import copy
import json
from pathlib import Path

from jsonschema import Draft202012Validator

from .io import digest_json

VERSION = "object-enrichment-2.0"
READING_VERSION = "scientific-reading-2.0"
MODEL_VERSION = "scientific-model-2.0"
MAX_GUIDE_CHARS = 9000
_RELATIONS = {"ARGUMENT", "RECEIVER", "REACHING_DEF", "CDG", "CONDITION", "TRUE_BODY",
              "FALSE_BODY", "REF", "CALL", "PARAMETER_LINK"}


def schema():
    return json.loads(Path(__file__).with_name("scientific-model.schema.json").read_text())


def reading_input(payload):
    """A shared entity/source index and code-owned callable views, not prose summaries.

    Source/analyzer namespaces remain distinct. A unique common definition site
    associates two views of a callable; names alone never establish identity.
    """
    if payload.get("schema_version") == READING_VERSION:
        return copy.deepcopy(payload)
    context = payload.get("context", payload)
    entities, sources, positions, definitions = {}, {}, {}, {}
    for record in context.get("scientific_passages", []) + context.get("code_passages", []):
        text = record.get("quote", record.get("text"))
        if record.get("id") and text:
            sources[record["id"]] = {k: record[k] for k in ("id", "path", "sha256", "start_line", "end_line", "language") if k in record}
            sources[record["id"]]["text"] = text
            sources[record["id"]]["kind"] = "document" if "quote" in record else "code"
    for obj in payload.get("objects", []):
        identifier = obj["id"]
        entities[identifier] = {"id": identifier, "kind": obj["kind"], "name": obj.get("symbol"),
            "properties": copy.deepcopy(obj.get("properties", {})),
            "source_ids": [s for s in obj.get("source_entry_ids", []) if s in sources]}
        positions[identifier] = (obj.get("path"), obj.get("scope"), obj.get("source_span", {}).get("start_line"))
        if obj["kind"] == "code_interface":
            definitions[identifier] = {"id": identifier, "name": obj.get("symbol") or obj.get("scope"),
                "source_ids": entities[identifier]["source_ids"], "entity_ids": [identifier]}
    for op in payload.get("operations", []):
        identifier = op["id"]
        entities[identifier] = {k: copy.deepcopy(op[k]) for k in
            ("id", "kind", "inputs", "output_ids", "properties", "assumptions", "documentation_url") if k in op}
        entities[identifier]["source_ids"] = [op["source_entry_id"]] if op.get("source_entry_id") in sources else []
        source = op.get("source", {})
        positions[identifier] = (source.get("path"), source.get("scope"), source.get("start_line"))
    interface_ids = list(definitions)
    for identifier, (path, scope, _) in positions.items():
        owners = [key for key in interface_ids if positions[key][0] == path and scope and positions[key][1]
                  and (scope == positions[key][1] or scope.startswith(positions[key][1] + "."))]
        if owners:
            owner = max(owners, key=lambda key: len(positions[key][1]))
            if identifier not in definitions[owner]["entity_ids"]:
                definitions[owner]["entity_ids"].append(identifier)
        elif "inputs" in entities[identifier]:
            definitions[identifier] = {"id": identifier, "name": entities[identifier]["kind"],
                "source_ids": entities[identifier]["source_ids"], "entity_ids": [identifier]}

    analyzer = [r for r in context.get("analysis_sources", []) if r.get("analyzer") == "joern"]
    method_ranges = []
    for node in analyzer:
        if node.get("kind") == "edge":
            continue
        identifier, props = node["id"], node.get("properties", {})
        entities[identifier] = {"id": identifier, "kind": node["kind"], "code": node.get("text", ""),
            "properties": {k: v for k, v in props.items() if k not in
                {"FILENAME", "LINE_NUMBER", "LINE_NUMBER_END", "COLUMN_NUMBER", "COLUMN_NUMBER_END"}},
            "source_ids": []}
        if node.get("dispatch"):
            entities[identifier]["dispatch"] = copy.deepcopy(node["dispatch"])
        if node.get("path") and not node["path"].startswith("analysis:") and node.get("start_line", 0) > 0:
            sources[identifier] = {k: node[k] for k in ("id", "path", "start_line", "end_line", "text", "language") if k in node}
            entities[identifier]["source_ids"] = [identifier]
            sources[identifier]["kind"] = "analyzer"
            entities[identifier].pop("code", None)  # Exact code occurs once in the source index.
            entities[identifier]["name"] = props.get("NAME")
        if node["kind"] == "METHOD" and identifier in sources and not props.get("IS_EXTERNAL"):
            path, start, end = node["path"], node["start_line"], props.get("LINE_NUMBER_END", node["end_line"])
            matches = [key for key in definitions if key in positions and
                       (positions[key][0], positions[key][2]) == (path, start) and
                       (positions[key][1] or "").split(".")[-1].split("@")[0] == props.get("NAME")]
            key = matches[0] if len(matches) == 1 else identifier
            if key not in definitions:
                definitions[key] = {"id": key, "name": props.get("FULL_NAME", props.get("NAME")),
                    "source_ids": [identifier], "entity_ids": [identifier]}
            method_ranges.append((path, start, end, key, props.get("FULL_NAME")))
    for node in analyzer:
        if node.get("kind") == "edge":
            continue
        owners = [(end - start, key) for path, start, end, key, scope in method_ranges
                  if node.get("path") == path and start <= node.get("start_line", 0) <= end]
        scoped = [(end - start, key) for path, start, end, key, scope in method_ranges
                  if node.get("scope") and scope == node["scope"] and node.get("path") == path]
        if scoped:
            owners = scoped
        if owners:
            narrowest = min(width for width, _ in owners)
            keys = {key for width, key in owners if width == narrowest}
            if len(keys) == 1:
                key = next(iter(keys))
                if node["id"] not in definitions[key]["entity_ids"]:
                    definitions[key]["entity_ids"].append(node["id"])

    relations, omitted = [], []
    for entity in entities.values():
        for operand in entity.get("inputs", []):
            if operand.get("object_id") is not None and operand["object_id"] not in entities:
                operand["unresolved_object_id"] = operand["object_id"]
                operand["object_id"] = None
        missing = [identifier for identifier in entity.get("output_ids", []) if identifier not in entities]
        if missing:
            entity["unresolved_output_ids"] = missing
            entity["output_ids"] = [identifier for identifier in entity["output_ids"] if identifier in entities]
    raw_links = list(payload.get("links", [])) + [r for r in analyzer if r.get("kind") == "edge" and r.get("relation") in _RELATIONS]
    for edge in raw_links:
        if edge.get("source") not in entities or edge.get("target") not in entities:
            omitted.append({"reason": "missing_endpoint", "source": edge.get("source"), "target": edge.get("target")})
            continue
        relation = {k: copy.deepcopy(edge[k]) for k in ("source", "target", "relation", "properties") if k in edge}
        relation["id"] = edge.get("id") or "rel_" + digest_json(relation)[:24]
        relations.append(relation)
    for definition in definitions.values():
        members = set(definition["entity_ids"])
        links = [r for r in relations if r["source"] in members or r["target"] in members]
        definition["relation_ids"] = [r["id"] for r in links]
        definition["boundary_ids"] = sorted({r[k] for r in links for k in ("source", "target")} - members)
    return {"schema_version": READING_VERSION, "computations": list(definitions.values()),
        "entities": list(entities.values()), "relations": relations, "sources": list(sources.values()),
        "observations": copy.deepcopy(context.get("observations", [])),
        "coverage": {"source_selection": payload.get("selection", {}),
            "source_analysis": payload.get("source_analysis_summary", {}), "omitted_relations": omitted,
            "unsupported": copy.deepcopy(payload.get("unsupported", [])),
            "projection": "Callable identity, operand/data dependencies and controlling conditions; AST/CFG detail remains in source-analysis.json."}}


def join(graph, response, context):
    """Validate IDs/citations, then join explanations to immutable code relationships."""
    result = copy.deepcopy(graph)
    report = {"applied_object_ids": [], "dropped": [], "version": VERSION}
    result["enrichment"] = report
    view = reading_input(context or {})
    definitions = {c["id"]: c for c in view["computations"]}
    entities = {o["id"]: o for o in view["entities"]}
    sources = {s["id"]: s for s in view["sources"]}
    validator = Draft202012Validator(schema())
    envelope = {**response, "computations": []} if isinstance(response, dict) else response
    if (not validator.is_valid(envelope) or not isinstance(response.get("computations"), list)
            or len(response["computations"]) > 6):
        report["dropped"].append({"reason": "invalid_scientific_model_envelope"})
        return result

    def grounded(claim):
        return all(identifier in sources for identifier in claim["source_ids"])

    purpose = response["purpose"] if grounded(response["purpose"]) else None
    if purpose is None:
        report["dropped"].append({"reason": "unanchored_purpose_citation"})
    accepted, seen = [], set()
    item_validator = Draft202012Validator({**schema()["$defs"]["computation"], "$defs": schema()["$defs"]})
    for index, item in enumerate(response["computations"]):
        identifier = item.get("computation_id") if isinstance(item, dict) else None
        definition = definitions.get(identifier)
        reason = ("invalid_computation_fields" if not item_validator.is_valid(item) else
                  "unknown_computation" if definition is None else
                  "duplicate_computation" if identifier in seen else None)
        if reason is None:
            claims = [item["meaning"], *item["conventions"], *(q["meaning"] for q in item["quantities"])]
            allowed = set(definition["entity_ids"] + definition["boundary_ids"])
            if not all(grounded(claim) for claim in claims):
                reason = "unknown_source_citation"
            elif any(q["object_id"] not in allowed for q in item["quantities"]):
                reason = "quantity_outside_computation"
            elif len({q["object_id"] for q in item["quantities"]}) != len(item["quantities"]):
                reason = "duplicate_quantity"
        if reason:
            report["dropped"].append({"index": index, "computation_id": identifier, "reason": reason})
            continue
        accepted.append({**copy.deepcopy(definition), "interpretation": copy.deepcopy(item)})
        seen.add(identifier)
        report["applied_object_ids"].append(identifier)
    member_ids = {identifier for c in accepted for identifier in c["entity_ids"] + c["boundary_ids"]}
    link_ids = {identifier for c in accepted for identifier in c["relation_ids"]}
    cited = set(purpose["source_ids"] if purpose else [])
    for c in accepted:
        cited.update(c["source_ids"])
        item = c["interpretation"]
        for claim in [item["meaning"], *item["conventions"], *(q["meaning"] for q in item["quantities"])]:
            cited.update(claim["source_ids"])
    for identifier in member_ids:
        cited.update(entities[identifier].get("source_ids", []))
    result["scientific_model"] = {"schema_version": MODEL_VERSION, "purpose": copy.deepcopy(purpose),
        "computations": accepted, "entities": [entities[i] for i in sorted(member_ids)],
        "relations": [r for r in view["relations"] if r["id"] in link_ids],
        "sources": [sources[i] for i in sorted(cited)], "observations": copy.deepcopy(view["observations"]),
        "coverage": view["coverage"], "validation": "IDs and citations checked; scientific entailment is not mechanically established."}
    return result


def render(model):
    """Render whole computation explanations, including conventions and assumptions."""
    sources = {s["id"]: s for s in model["sources"]}
    entities = {e["id"]: e for e in model["entities"]}

    def site(identifier):
        source = sources[identifier]
        return f"{source['path']}:{source.get('start_line', '?')}"

    def claim(item):
        return item["text"] + " [" + "; ".join(dict.fromkeys(site(s) for s in item["source_ids"])) + "]"

    lines = ["# Scientific working model", ""]
    if model.get("purpose"):
        lines += [claim(model["purpose"]), ""]
    omitted, displayed = [], 0
    for computation in model["computations"]:
        item = computation["interpretation"]
        section = [f"## {computation['name']}", "", claim(item["meaning"])]
        for quantity in item["quantities"]:
            entity = entities[quantity["object_id"]]
            name = entity.get("name") or entity.get("code") or entity.get("properties", {}).get("symbol") or quantity["object_id"]
            section.append(f"- {name}: {claim(quantity['meaning'])}")
        for convention in item["conventions"]:
            section.append("- Convention/condition: " + claim(convention))
        for assumption in item["assumptions"]:
            section.append("- Assumption: " + assumption)
        predicates = {}
        members = set(computation["entity_ids"])
        for identifier in computation["entity_ids"]:
            entity = entities[identifier]
            if entity["kind"] in {"source_comparison", "source_predicate"}:
                expression = entity.get("properties", {}).get("expression")
                if expression:
                    predicates.setdefault(expression, entity.get("source_ids", []))
        for relation in model["relations"]:
            if relation["relation"] == "CONDITION" and relation["source"] in members:
                condition = entities[relation["target"]]
                source_ids = condition.get("source_ids", [])
                expression = condition.get("code") or (sources[source_ids[0]]["text"] if source_ids else None)
                # Some frontends introduce loop/runtime predicates that are not
                # literal source code. Keep them in the model as analyzer facts,
                # not as source-level rules in the guide.
                literal = [s["id"] for s in model["sources"] if s.get("kind") == "code" and expression
                           and any(s["path"] == sources[i]["path"] and
                                   s["start_line"] <= sources[i]["start_line"] <= s["end_line"] for i in source_ids)
                           and " ".join(expression.split()) in " ".join(s["text"].split())]
                if expression and literal:
                    predicates.setdefault(expression, literal)
        for expression, source_ids in predicates.items():
            location = "; ".join(dict.fromkeys(site(s) for s in source_ids))
            section.append(f"- Code predicate: {expression}" + (f" [{location}]" if location else ""))
        # These links come from code, not from the interpretation's prose.
        interpreted = {q["object_id"] for q in item["quantities"]}
        relevant = [r for r in model["relations"] if r["id"] in computation["relation_ids"]
                    and (r["source"] in interpreted or r["target"] in interpreted)]
        if relevant:
            def label(identifier):
                entity = entities[identifier]
                return entity.get("name") or entity.get("code") or entity.get("properties", {}).get("operator") or entity.get("kind", identifier)
            section.append("Code relationships: " + "; ".join(
                f"{label(r['source'])} —{r['relation']}→ {label(r['target'])}" for r in relevant[:4]) + ".")
        section += [f"Computation: {computation['id']} (scientific-model.json).", ""]
        if displayed and len("\n".join(lines + section)) > MAX_GUIDE_CHARS - 400:
            omitted.append(computation["id"])
        else:
            lines.extend(section)
            displayed += 1  # Always show one complete computation; never a purpose-only treatment.
    if omitted:
        lines += [f"{len(omitted)} additional complete computation(s) are in scientific-model.json.", ""]
    lines.append("Use this model and its cited sources to understand the task; inspect the corresponding implementation when repairing. "
                 "Scientific-model.json contains the connected quantities, conditions and code relationships.")
    return "\n".join(lines) + "\n"
