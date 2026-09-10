"""Assemble compact semantic annotations using code-owned source evidence.

Annotations are fallible interpretations. Source citations, syntax checks and
probe execution receipts establish neither scientific truth nor repair success.
"""

from __future__ import annotations

import copy
import hashlib
from fractions import Fraction
from pathlib import Path, PurePosixPath

from jsonschema import Draft202012Validator

from .evidence import _has_unknown, _read_regular, _safe_file
from .expressions import parse_expression
from .graph import _check_json, _safe_relative, graph_schema, render_graph, validate_graph
from .io import digest_json
from .tool_cli import analyze_grounded

MAX_CLAIMS = 5
MAX_QUANTITIES = 12
MAX_PROBES = 2


def _object(properties: dict, required: list[str]) -> dict:
    return {"type": "object", "properties": properties, "required": required,
            "additionalProperties": False}


def _array(items: dict, cap: int = 64) -> dict:
    return {"type": "array", "items": items, "maxItems": cap}


def annotation_schema() -> dict:
    """Return the bounded annotation contract, with genuinely optional fields."""
    graph = graph_schema()["properties"]
    quantity = graph["quantities"]["items"]["properties"]
    claim = graph["claims"]["items"]["properties"]
    identifier = quantity["id"]
    text = quantity["meaning"]
    reference = {"anyOf": [identifier, _object({
        "path": graph["evidence"]["items"]["properties"]["path"],
        "start_line": {"type": "integer", "minimum": 1},
        "end_line": {"type": "integer", "minimum": 1},
    }, ["path", "start_line", "end_line"])]}
    rational = {"type": "string", "pattern": r"^-?\d+(?:/\d+|\.\d+)?$", "maxLength": 80}
    dimensions = {"type": ["object", "null"], "maxProperties": 16,
                  "propertyNames": {"type": "string", "minLength": 1, "maxLength": 40},
                  "additionalProperties": {"anyOf": [{"type": "integer"}, rational]}}
    status = {**quantity["status"], "default": "inferred"}
    schema = _object({
        "schema_version": {"type": "string", "const": "annotations-1.0"},
        "quantities": _array(_object({
            "id": identifier, "meaning": text, "symbol": quantity["code_symbol"],
            "name": quantity["name"], "dimensions": dimensions,
            "scale": quantity["scale"], "shape": quantity["shape"],
            "status": status, "evidence": _array(reference),
        }, ["id", "meaning"]), MAX_QUANTITIES),
        "claims": _array(_object({
            "id": identifier, "description": text,
            "formula": {"type": ["string", "null"], "maxLength": 16384},
            "implementation_id": {"anyOf": [identifier, {"type": "null"}]},
            "quantities": _array(identifier, MAX_QUANTITIES),
            "bindings": {"type": "object", "maxProperties": 64,
                         "propertyNames": {"type": "string", "minLength": 1, "maxLength": 512},
                         "additionalProperties": {"type": "string", "minLength": 1, "maxLength": 512}},
            "operation": {**claim["operation"], "default": "other"},
            "status": status, "assumptions": claim["assumptions"],
            "evidence": _array(reference),
        }, ["id", "description"]), MAX_CLAIMS),
        "probes": _array(_object({
            "id": {"type": "string", "pattern": "^[A-Za-z0-9_-]{1,64}$"}, "claim_ids": {**_array(identifier, MAX_CLAIMS), "minItems": 1},
            "script": {"type": "string", "minLength": 1, "maxLength": 1024, "pattern": r"\.py$"},
            "description": text,
        }, ["id", "claim_ids", "script", "description"]), MAX_PROBES),
        "unresolved": _array(text),
    }, ["schema_version", "quantities", "claims"])
    return copy.deepcopy(schema)


def _schema_errors(value: object, schema: dict) -> list[str]:
    return [f"{'.'.join(map(str, error.path)) or '<item>'}: {error.message}"
            for error in Draft202012Validator(schema).iter_errors(value)][:8]


def _scratch_path_problem(path: str, suffix: str) -> str | None:
    if any(not part or part.startswith(".") for part in path.split("/")):
        return "empty, hidden, or traversal path component"
    return _safe_relative(path) or (None if PurePosixPath(path).suffix == suffix else f"expected {suffix} path")


class _Sources:
    """Resolve packet references, rereading immutable source through existing guards."""

    def __init__(self, packet: dict, root: Path, context_root: Path | None):
        self.root = Path(root).resolve()
        self.context_root = Path(context_root).resolve() if context_root is not None else None
        self.references: dict[str, dict | None] = {}
        self.entries: dict[str, dict] = {}
        self.cache: dict[str, tuple[str, list[str]]] = {}
        for group in ("entries", "documents"):
            for record in packet.get(group, []):
                if not isinstance(record, dict) or not isinstance(record.get("id"), str):
                    continue
                identifier = record["id"]
                if identifier in self.references:
                    self.references[identifier] = None
                    self.entries.pop(identifier, None)
                else:
                    self.references[identifier] = record
                    if group == "entries":
                        self.entries[identifier] = record

    def resolve(self, reference: str | dict) -> dict:
        snapshot = None
        if isinstance(reference, str):
            snapshot = self.references.get(reference)
            if snapshot is None:
                raise ValueError(f"unknown or ambiguous packet reference {reference!r}")
            reference = snapshot
        path = reference.get("path")
        start, end = reference.get("start_line"), reference.get("end_line")
        if not isinstance(path, str) or (reason := _safe_relative(path)):
            raise ValueError(f"unsafe evidence path: {path!r}")
        if type(start) is not int or type(end) is not int or not 1 <= start <= end:
            raise ValueError(f"invalid line span for {path!r}")
        source_root, relative = self.root, path
        if path.startswith("@context/"):
            if self.context_root is None or path != "@context/task_statement.md":
                raise ValueError("unknown or unavailable immutable task context")
            source_root, relative = self.context_root, "task_statement.md"
        if path not in self.cache:
            _, problem = _safe_file(source_root, relative)
            if problem:
                raise ValueError(f"source {path!r}: {problem}")
            raw = _read_regular(source_root, relative)
            self.cache[path] = hashlib.sha256(raw).hexdigest(), raw.decode("utf-8").splitlines()
        digest, lines = self.cache[path]
        if snapshot is not None and snapshot.get("sha256") != digest:
            raise ValueError(f"stale packet source hash for {path!r}")
        if end > len(lines):
            raise ValueError(f"evidence span exceeds source {path!r}")
        quote = "\n".join(lines[start - 1:end])
        if not quote or len(quote) > 16384:
            raise ValueError(f"empty or oversized quote for {path!r}")
        return {"id": "e_" + digest_json([path, digest, start, end])[:24],
                "path": path, "sha256": digest, "start_line": start, "end_line": end,
                "quote": quote}


def assemble_annotations(
    annotations: dict, packet: dict, root: Path, context_root: Path | None = None,
    probe_results: list[dict] | None = None,
) -> dict:
    """Resolve annotations without executing scripts or trusting model-made evidence.

    Malformed dependent items are rejected individually. Unsupported syntax and
    missing implementation correspondence remain unknown. The caller supplies
    probe receipts from its runner; this function never infers scientific truth
    from their exit codes. Script existence/symlinks require the runner's scratch
    root and are checked there, after these lexical path checks.
    """
    graph = {"schema_version": "1.0", "task_id": packet.get("task_id", Path(root).name),
             "quantities": [], "claims": [], "evidence": [], "observations": [], "unresolved": []}
    assembly = {"schema_version": "assembly-1.0", "accepted_claim_ids": [],
                "accepted_quantity_ids": [], "accepted_probe_ids": [], "rejected": [],
                "unresolved": [], "packet_coverage": copy.deepcopy(packet.get("coverage", {}))}
    schema = annotation_schema()
    sources = _Sources(packet, root, context_root)

    def note(message: str) -> None:
        if message not in assembly["unresolved"]:
            assembly["unresolved"].append(message)

    def reject(kind: str, item: object, reason: str) -> None:
        identifier = item.get("id") if isinstance(item, dict) else None
        assembly["rejected"].append({"kind": kind, "id": identifier, "reason": reason})
        note(f"Rejected {kind} {identifier or '<unnamed>'}: {reason}")

    unsafe = _check_json(annotations)
    envelope = (dict(annotations) if isinstance(annotations, dict) and not unsafe else {})
    # Item validation below can preserve independent claims from a partial artifact.
    for field in ("quantities", "claims", "probes", "unresolved"):
        if isinstance(envelope.get(field), list):
            envelope[field] = []
    errors = [unsafe] if unsafe else _schema_errors(envelope, schema)
    if errors:
        reject("annotations", annotations, "; ".join(errors))
        annotations = {"quantities": [], "claims": []}

    def items(field: str, kind: str, cap: int) -> list[dict]:
        accepted = []
        seen = set()
        for index, item in enumerate(annotations.get(field, [])):
            if index >= cap:
                reject(kind, item, f"{field} cap exceeded ({cap})")
                continue
            problems = _schema_errors(item, schema["properties"][field]["items"])
            if problems:
                reject(kind, item, "; ".join(problems))
            elif item["id"] in seen:
                reject(kind, item, "duplicate annotation id")
            else:
                seen.add(item["id"])
                accepted.append(item)
        return accepted

    def citations(item: dict) -> list[dict]:
        resolved = {}
        for reference in item.get("evidence", []):
            try:
                evidence = sources.resolve(reference)
                resolved[evidence["id"]] = evidence
            except (OSError, ValueError, UnicodeError) as exc:
                note(f"{item['id']}: unresolved evidence: {exc}")
        return list(resolved.values())

    def append(group: str, node: dict, evidence: list[dict]) -> bool:
        candidate = copy.deepcopy(graph)
        candidate[group].append(node)
        known = {entry["id"] for entry in candidate["evidence"]}
        candidate["evidence"].extend(entry for entry in evidence if entry["id"] not in known)
        validation = validate_graph(candidate, root, max_claims=MAX_CLAIMS, context_root=context_root)
        if not validation["valid"]:
            reject({"quantities": "quantity", "claims": "claim", "observations": "probe_result"}[group],
                   node, "; ".join(validation["errors"]))
            return False
        graph.update(candidate)
        return True

    for item in items("quantities", "quantity", MAX_QUANTITIES):
        evidence = citations(item)
        try:
            dimensions = item.get("dimensions")
            dimensions = ([{"dimension": name, "exponent": str(Fraction(exponent))}
                           for name, exponent in dimensions.items()] if dimensions is not None else None)
            scale = str(Fraction(item["scale"])) if item.get("scale") is not None else None
        except (ValueError, ZeroDivisionError) as exc:
            reject("quantity", item, f"invalid rational: {exc}")
            continue
        node = {"id": item["id"], "name": item.get("name", item.get("symbol") or item["id"]),
                "meaning": item["meaning"], "code_symbol": item.get("symbol"),
                "dimensions": dimensions, "scale": scale, "shape": item.get("shape"),
                "status": item.get("status", "inferred"), "evidence_ids": [e["id"] for e in evidence]}
        if append("quantities", node, evidence):
            assembly["accepted_quantity_ids"].append(node["id"])

    for item in items("claims", "claim", MAX_CLAIMS):
        missing = set(item.get("quantities", [])) - set(assembly["accepted_quantity_ids"])
        if missing:
            reject("claim", item, f"unknown or rejected quantities: {', '.join(sorted(missing))}")
            continue
        evidence = {e["id"]: e for e in citations(item)}
        actual = None
        implementation_id = item.get("implementation_id")
        if implementation_id is not None:
            entry = sources.entries.get(implementation_id)
            if entry is None:
                note(f"{item['id']}: implementation reference {implementation_id!r} is unknown or not a source entry")
            else:
                try:
                    citation = sources.resolve(implementation_id)
                    evidence[citation["id"]] = citation
                    if entry.get("kind") != "augmented_assignment":
                        actual = copy.deepcopy(entry.get("expression"))
                    if actual is None or _has_unknown(actual):
                        note(f"{item['id']}: implementation correspondence contains unsupported or unresolved syntax")
                except (OSError, ValueError, UnicodeError) as exc:
                    note(f"{item['id']}: unresolved implementation reference: {exc}")
        else:
            note(f"{item['id']}: no implementation reference; correspondence remains unknown")
        if not evidence:
            reject("claim", item, "every accepted claim requires source evidence")
            continue
        relation = parse_expression(item["formula"]) if item.get("formula") is not None else None
        if relation is not None and _has_unknown(relation):
            note(f"{item['id']}: scientific formula contains unsupported or unresolved syntax")
        node = {"id": item["id"], "description": item["description"], "relation": relation,
                "actual": actual, "bindings": [{"expected": key, "actual": value}
                                               for key, value in item.get("bindings", {}).items()],
                "quantity_ids": list(dict.fromkeys(item.get("quantities", []))),
                "evidence_ids": list(evidence), "assumptions": item.get("assumptions", []),
                "operation": item.get("operation", "other"), "status": item.get("status", "inferred")}
        if append("claims", node, list(evidence.values())):
            assembly["accepted_claim_ids"].append(node["id"])

    probes = []
    for item in items("probes", "probe", MAX_PROBES):
        problem = _scratch_path_problem(item["script"], ".py")
        claim_ids = [identifier for identifier in dict.fromkeys(item["claim_ids"])
                     if identifier in assembly["accepted_claim_ids"]]
        if problem or not claim_ids:
            reject("probe", item, problem or "probe has no accepted claim references")
            continue
        if len(claim_ids) != len(set(item["claim_ids"])):
            note(f"{item['id']}: probe references to unknown or rejected claims were removed")
        probes.append({**item, "claim_ids": claim_ids})
        assembly["accepted_probe_ids"].append(item["id"])

    raw_results = [] if probe_results is None else copy.deepcopy(probe_results)
    receipt_schema = _object({
        "id": schema["properties"]["probes"]["items"]["properties"]["id"],
        "claim_ids": schema["properties"]["probes"]["items"]["properties"]["claim_ids"],
        "description": {"type": "string", "maxLength": 4096},
        "status": {"type": "string", "minLength": 1, "maxLength": 120},
        "exit_code": {"type": ["integer", "null"]},
        "duration_seconds": {"type": "number", "minimum": 0},
        "script_sha256": {"type": ["string", "null"], "pattern": "^[0-9a-f]{64}$"},
        "artifact": {"type": "string", "minLength": 1, "maxLength": 1024},
    }, ["id", "claim_ids", "description", "status", "exit_code", "duration_seconds", "script_sha256", "artifact"])
    # Runner-specific timing/error fields remain in the raw receipt, not graph nodes.
    receipt_schema["additionalProperties"] = True
    if not isinstance(raw_results, list) or (problem := _check_json(raw_results)):
        reject("probe_result", {}, "probe results must be a bounded JSON list")
        raw_results = []
    seen_results = set()
    specifications = {spec["id"]: spec for spec in probes}
    for result in raw_results:
        problems = _schema_errors(result, receipt_schema)
        if problems:
            reject("probe_result", result, "; ".join(problems))
            continue
        identifier = result["id"]
        specification = specifications.get(identifier)
        problem = _scratch_path_problem(result["artifact"], ".json")
        if specification is None or identifier in seen_results or problem:
            reject("probe_result", result, problem or "unknown, rejected, or duplicate probe receipt")
            continue
        seen_results.add(identifier)
        for claim_id in dict.fromkeys(result["claim_ids"]):
            if claim_id not in specification["claim_ids"]:
                note(f"{identifier}: receipt reference {claim_id!r} does not belong to the accepted probe")
                continue
            description = (f"Probe {identifier}: status={result['status']}, exit_code={result['exit_code']}, "
                           f"duration_seconds={result['duration_seconds']}. "
                           "Execution success is not scientific proof; failure does not disprove an intended requirement.\n"
                           f"Proposed purpose: {specification['description'][:500]}\n"
                           f"stdout: {str(result.get('stdout_excerpt', ''))[:1420]}\n"
                           f"stderr: {str(result.get('stderr_excerpt', ''))[:920]}")
            node = {"id": "o_" + digest_json([identifier, claim_id, result["artifact"]])[:24],
                    "claim_id": claim_id, "description": description,
                    "status": "reported", "artifact": result["artifact"]}
            append("observations", node, [])

    for unresolved in annotations.get("unresolved", []):
        if _schema_errors(unresolved, schema["properties"]["unresolved"]["items"]):
            reject("unresolved", {}, "unresolved entries must be strings of at most 4096 characters")
        else:
            note(unresolved)
    if not graph["claims"]:
        note("Abstained: no source-backed scientific claims were accepted.")
    graph["unresolved"] = [message[:4096] for message in assembly["unresolved"][:64]]
    if len(assembly["unresolved"]) > 64:
        graph["unresolved"][-1] = "Additional unresolved reasons are preserved in assembly diagnostics."
    validation = validate_graph(graph, root, max_claims=MAX_CLAIMS, context_root=context_root)
    analysis = analyze_grounded(graph, root) if validation["valid"] else {}
    analysis["probe_results"] = raw_results
    analysis["probe_policy"] = ("Observations summarize supplied runner receipts. Exit zero is execution success, "
                                "not scientific proof; nonzero exit does not disprove an intended requirement.")
    usable = validation["valid"] and bool(graph["claims"])
    handoff = ""
    if usable:
        try:
            handoff = render_graph(graph, analysis)
        except ValueError as exc:
            note(f"Scientific handoff unavailable: {exc}")
            usable = False
    assembly.update(usable=usable, abstained=not bool(graph["claims"]),
                    status="assembled" if usable else "abstained" if not graph["claims"] else "invalid")
    return {"graph": graph, "validation": validation, "analysis": analysis,
            "graph_sha256": digest_json(graph), "handoff": handoff,
            "assembly": assembly, "probes": probes}
