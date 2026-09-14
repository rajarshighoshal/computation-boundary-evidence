"""Join scientific interpretation to existing computations, never invent program edges."""
from __future__ import annotations

import copy
import json
from pathlib import Path

from jsonschema import Draft202012Validator

from .representation import reading_input

VERSION = "object-enrichment-2.0"
MODEL_VERSION = "scientific-model-2.0"
MAX_GUIDE_CHARS = 9000


def schema():
    return json.loads(Path(__file__).with_name("scientific-model.schema.json").read_text())


def join(graph, response, context):
    """Validate IDs/citations, then join explanations to immutable code relationships."""
    result = copy.deepcopy(graph)
    report = {"applied_object_ids": [], "dropped": [], "version": VERSION}
    result["enrichment"] = report
    view = reading_input(context or {})
    definitions = {c["id"]: c for c in view["computations"]}
    entities = {o["id"]: o for o in view["entities"]}
    sources = {s["id"]: s for s in view["sources"]}

    def operation_definition(identifier):
        entity = entities.get(identifier, {})
        if entity.get("kind") != "source_computation":
            return None
        links = [r for r in view["relations"] if identifier in {r["source"], r["target"]}]
        return {"id": identifier, "name": entity["name"], "source_ids": entity["source_ids"],
                "entity_ids": [identifier], "relation_ids": [r["id"] for r in links],
                "boundary_ids": sorted({r[k] for r in links for k in ("source", "target")} - {identifier})}
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
        if not item_validator.is_valid(item):
            report["dropped"].append({"index": index, "reason": "invalid_computation_fields"})
            continue
        identifier = item.get("computation_id") if isinstance(item, dict) else None
        definition = definitions.get(identifier) or operation_definition(identifier)
        reason = ("unknown_computation" if definition is None else
                  "duplicate_computation" if identifier in seen else None)
        if reason is None:
            claims = [item["meaning"], *item["conventions"], *(q["meaning"] for q in item["quantities"])]
            allowed = set(definition["entity_ids"] + definition["boundary_ids"])
            if not all(grounded(claim) for claim in claims):
                reason = "unknown_source_citation"
            elif any(q["object_id"] not in allowed for q in item["quantities"]):
                reason = "quantity_outside_computation"
            elif any(i not in allowed or entities[i].get("kind") != "source_computation" for i in item.get("expression_ids", [])):
                reason = "expression_outside_computation"
            elif len({q["object_id"] for q in item["quantities"]}) != len(item["quantities"]):
                reason = "duplicate_quantity"
        if reason:
            report["dropped"].append({"index": index, "computation_id": identifier, "reason": reason})
            continue
        accepted.append({**copy.deepcopy(definition), "interpretation": copy.deepcopy(item)})
        seen.add(identifier)
        report["applied_object_ids"].append(identifier)
    for computation in accepted:
        members = set(computation["entity_ids"] + computation["boundary_ids"])
        pending = list(members)
        while pending:
            entity = entities[pending.pop()]
            dependencies = [b.get("definition_id") for b in entity.get("bindings", [])]
            dependencies += [c.get("predicate_id") for c in entity.get("condition_refs", [])]
            for identifier in dependencies:
                if identifier in entities and identifier not in members:
                    members.add(identifier)
                    pending.append(identifier)
        computation["boundary_ids"] = sorted(members - set(computation["entity_ids"]))
        computation["relation_ids"] = [r["id"] for r in view["relations"]
                                       if r["source"] in members and r["target"] in members]
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
        "templates": [t for t in view.get("templates", []) if t["id"] in
                      {entities[i].get("template_id") for i in member_ids}],
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
        expression_ids = item.get("expression_ids") or [i for i in computation["entity_ids"]
                          if entities[i].get("kind") == "source_computation"]
        if expression_ids:
            section.append("Code computation:")
        for identifier in expression_ids:
            entity = entities[identifier]
            for source_id in entity.get("source_ids", []):
                section.append(f"- {sources[source_id]['text']} [{site(source_id)}]")
            if entity.get("conditions"):
                section.append("  Source conditions: " + json.dumps(entity["conditions"], ensure_ascii=False))
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
            if entity.get("statement_kind") in {"comparison", "predicate", "condition"}:
                for source_id in entity.get("source_ids", []):
                    predicates.setdefault(sources[source_id]["text"], [source_id])
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
