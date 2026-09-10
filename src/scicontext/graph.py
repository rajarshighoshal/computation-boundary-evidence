"""Strict graph contract, source-backed validation, and deterministic handoff text.

Validation checks traceability, not the scientific truth of an extracted claim.
Dimensions and bindings are key/value arrays because strict Codex output schemas
cannot contain arbitrary object properties.
"""

from __future__ import annotations

import hashlib
import copy
import json
import math
import os
import re
import stat
from fractions import Fraction
from pathlib import Path, PurePosixPath
from typing import Any

from jsonschema import Draft202012Validator

_STATUSES = ["explicit", "inferred", "unresolved"]
_DENIED_COMPONENTS = {
    "auth", "credentials", "secrets", "private", "private_tests", "verifier",
    "verifiers", "gold", "gold_patch", "gold_patches", "answers",
}
_DENIED_FILES = {"auth.json", "credentials.json", "credentials", "id_rsa", "id_ed25519", "secrets.json"}
_ID = {"type": "string", "pattern": r"^[A-Za-z][A-Za-z0-9_.:-]*$", "maxLength": 120}
_TEXT = {"type": "string", "maxLength": 4096}
_RATIONAL = {"type": "string", "pattern": r"^-?\d+(?:/\d+|\.\d+)?$", "maxLength": 80}


def _object(properties: dict) -> dict:
    return {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}


def _array(items: dict, cap: int = 64) -> dict:
    return {"type": "array", "items": items, "maxItems": cap}


def graph_schema() -> dict:
    """Return a fresh strict structured-output schema (all object keys required)."""
    expr_ref = {"$ref": "#/$defs/expression"}
    expr = {"anyOf": [
        _object({"op": {"type": "string", "enum": ["symbol"]}, "name": {"type": "string", "minLength": 1, "maxLength": 512}}),
        _object({"op": {"type": "string", "enum": ["constant"]}, "value": {"type": "number"}}),
        _object({"op": {"type": "string", "enum": ["add", "sub", "mul", "div", "pow", "neg", "sum", "sqrt", "matmul", "norm"]}, "args": _array(expr_ref, 2)}),
        _object({"op": {"type": "string", "enum": ["unknown"]}, "text": {"type": "string", "maxLength": 16384}}),
        _object({"op": {"type": "string", "enum": ["unknown"]}, "text": {"type": "string", "maxLength": 16384}, "args": _array(expr_ref, 512)}),
    ]}
    status = {"type": "string", "enum": _STATUSES}
    ids = _array(_ID)
    nullable_expr = {"anyOf": [expr_ref, {"type": "null"}]}
    quantity = _object({
        "id": _ID, "name": _TEXT, "meaning": _TEXT,
        "code_symbol": {"type": ["string", "null"], "maxLength": 512},
        "entity_id": {"anyOf": [_ID, {"type": "null"}]},
        "dimensions": {"anyOf": [_array(_object({"dimension": {"type": "string", "minLength": 1, "maxLength": 40}, "exponent": _RATIONAL}), 16), {"type": "null"}]},
        "scale": {"anyOf": [_RATIONAL, {"type": "null"}]},
        "shape": {"anyOf": [_array({"anyOf": [{"type": "integer", "minimum": 1}, {"type": "string", "minLength": 1, "maxLength": 120}]}, 16), {"type": "null"}]},
        "evidence_ids": ids, "status": status,
    })
    claim = _object({
        "id": _ID, "description": _TEXT, "relation": nullable_expr, "actual": nullable_expr,
        "bindings": _array(_object({"expected": {"type": "string", "minLength": 1, "maxLength": 512}, "actual": {"type": "string", "minLength": 1, "maxLength": 512}})),
        "quantity_ids": ids, "evidence_ids": ids, "assumptions": _array(_TEXT, 16),
        "operation": {"type": "string", "enum": ["unit_conversion", "weighted_sum", "normalization", "linear_transform", "other"]},
        "status": status,
        "scientific_object": _TEXT, "applicability": _TEXT,
        "alternative_interpretation": _TEXT, "discriminating_observation": _TEXT,
        "consumer_ids": ids,
    })
    evidence = _object({
        "id": _ID, "path": {"type": "string", "minLength": 1, "maxLength": 1024},
        "sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
        "start_line": {"type": "integer", "minimum": 1}, "end_line": {"type": "integer", "minimum": 1},
        "quote": {"type": "string", "minLength": 1, "maxLength": 16384},
    })
    observation = _object({
        "id": _ID, "claim_id": _ID, "description": _TEXT,
        "status": {"type": "string", "enum": ["proposed", "reported"]},
        "artifact": {"type": ["string", "null"], "maxLength": 1024},
    })
    schema = _object({
        "schema_version": {"type": "string", "enum": ["1.0"]},
        "task_id": {"type": "string", "minLength": 1, "maxLength": 120},
        "quantities": _array(quantity), "claims": _array(claim, 12),
        "evidence": _array(evidence), "observations": _array(observation), "unresolved": _array(_TEXT),
    })
    schema["$defs"] = {"expression": expr}
    return copy.deepcopy(schema)


def _safe_relative(path: str) -> str | None:
    if not path or "\\" in path or "\x00" in path or ":" in path:
        return "invalid relative path"
    parts = PurePosixPath(path).parts
    if PurePosixPath(path).is_absolute() or any(p in {".", ".."} or p.startswith(".") for p in parts):
        return "absolute, hidden, or traversal path"
    if not parts or any(p.lower() in _DENIED_COMPONENTS for p in parts):
        return "private, verifier, or credential path"
    name = parts[-1].lower()
    if name in _DENIED_FILES or name.endswith((".pem", ".key")) or re.search(r"(?:^|[_-])(private|verifier|credentials|secret)(?:[_-]|\.)", name):
        return "private, verifier, or credential file"
    return None


def _check_json(value: Any) -> str | None:
    """Bound hostile/cyclic input before JSON Schema's recursive visitor sees it."""
    active: set[int] = set()
    stack = [(value, 0, False)]
    count = 0
    while stack:
        node, depth, exiting = stack.pop()
        if exiting:
            active.remove(id(node))
            continue
        count += 1
        if count > 20000 or depth > 140:
            return "graph exceeds JSON node/depth safety limit"
        if isinstance(node, (dict, list)):
            if id(node) in active:
                return "graph must be a JSON tree without cyclic containers"
            active.add(id(node))
            stack.append((node, depth, True))
            if isinstance(node, dict) and any(not isinstance(k, str) for k in node):
                return "graph keys must be strings"
            stack.extend((v, depth + 1, False) for v in (node.values() if isinstance(node, dict) else node))
        elif isinstance(node, float) and not math.isfinite(node):
            return "non-finite numbers are forbidden"
        elif not isinstance(node, (str, int, float, bool, type(None))):
            return "graph contains a non-JSON value"
    return None


def _expression_errors(expr: dict, label: str) -> list[str]:
    errors = []
    stack = [(expr, 0)]
    count = 0
    while stack:
        node, depth = stack.pop()
        count += 1
        if count > 512 or depth > 64:
            errors.append(f"{label}: expression exceeds node/depth cap")
            break
        op = node["op"]
        if op == "constant" and (isinstance(node["value"], bool) or isinstance(node["value"], float) and not math.isfinite(node["value"])):
            errors.append(f"{label}: constant must be finite and non-boolean")
        if "args" in node:
            arity = 1 if op in {"neg", "sum", "sqrt", "norm"} else 2
            if op != "unknown" and len(node["args"]) != arity:
                errors.append(f"{label}: {op} requires {arity} arguments")
            stack.extend((a, depth + 1) for a in node["args"])
    return errors


def _read_source(root: Path, relative: str) -> bytes:
    """Open each component without following links, including during path races."""
    directory = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
    source = None
    try:
        parts = PurePosixPath(relative).parts
        for part in parts[:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
            os.close(directory)
            directory = child
        source = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
        info = os.fstat(source)
        if not stat.S_ISREG(info.st_mode):
            raise ValueError("evidence must be a regular file")
        limit = 4 * 1024 * 1024
        if info.st_size > limit:
            raise ValueError("source exceeds 4 MiB read limit")
        pieces = []
        size = 0
        while chunk := os.read(source, min(65536, limit + 1 - size)):
            pieces.append(chunk)
            size += len(chunk)
            if size > limit:
                raise ValueError("source exceeds 4 MiB read limit")
        return b"".join(pieces)
    finally:
        if source is not None:
            os.close(source)
        os.close(directory)


def validate_graph(graph: dict, root: Path, *, max_claims: int = 12, max_nodes: int = 64, context_root: Path | None = None) -> dict:
    """Validate the contract and exact public-source citations without executing code."""
    errors: list[str] = []
    warnings = ["Source matches establish traceability, not scientific correctness or code-derived expression validity."]
    unsafe = _check_json(graph)
    if unsafe:
        return {"valid": False, "errors": [unsafe], "warnings": warnings}
    # Upgrade absent optional semantic extensions in legacy 1.0 payloads.
    # The public output schema stays strict for structured-output consumers.
    graph = copy.deepcopy(graph)
    if isinstance(graph, dict):
        for quantity in graph.get("quantities", []) if isinstance(graph.get("quantities"), list) else []:
            if isinstance(quantity, dict):
                quantity.setdefault("entity_id", None)
        for claim in graph.get("claims", []) if isinstance(graph.get("claims"), list) else []:
            if isinstance(claim, dict):
                for field in ("scientific_object", "applicability", "alternative_interpretation", "discriminating_observation"):
                    claim.setdefault(field, "")
                claim.setdefault("consumer_ids", [])
    validator = Draft202012Validator(graph_schema())
    schema_errors = sorted(validator.iter_errors(graph), key=lambda e: "/".join(map(str, e.path)))
    if schema_errors:
        return {"valid": False, "errors": [f"schema {'.'.join(map(str, e.path)) or '<root>'}: {e.message}" for e in schema_errors[:40]], "warnings": warnings}
    if len(graph["claims"]) > max_claims:
        errors.append(f"scientific claim cap exceeded ({max_claims})")
    groups = [graph[k] for k in ("quantities", "claims", "evidence", "observations")]
    if sum(map(len, groups)) > max_nodes:
        errors.append(f"graph node cap exceeded ({max_nodes})")
    identifiers: set[str] = set()
    for group in groups:
        for item in group:
            if item["id"] in identifiers:
                errors.append(f"duplicate id: {item['id']}")
            identifiers.add(item["id"])
    evidence_ids = {e["id"] for e in graph["evidence"]}
    quantity_ids = {q["id"] for q in graph["quantities"]}
    claim_ids = {c["id"] for c in graph["claims"]}
    for item in graph["quantities"] + graph["claims"]:
        refs = item["evidence_ids"]
        if len(refs) != len(set(refs)):
            errors.append(f"{item['id']}: repeated evidence reference")
        for ref in refs:
            if ref not in evidence_ids:
                errors.append(f"{item['id']}: missing evidence {ref}")
        if item["status"] == "explicit" and not refs:
            errors.append(f"{item['id']}: explicit status requires source evidence")
    for q in graph["quantities"]:
        dim_names: set[str] = set()
        for dim in q["dimensions"] or []:
            if dim["dimension"] in dim_names:
                errors.append(f"{q['id']}: duplicate dimension {dim['dimension']}")
            dim_names.add(dim["dimension"])
            try:
                Fraction(dim["exponent"])
            except (ValueError, ZeroDivisionError):
                errors.append(f"{q['id']}: invalid rational exponent")
        if q["scale"] is not None:
            try:
                if Fraction(q["scale"]) <= 0:
                    raise ValueError
            except (ValueError, ZeroDivisionError):
                errors.append(f"{q['id']}: scale must be a positive rational")
        if q["status"] == "unresolved" and (q["dimensions"] is not None or q["scale"] is not None):
            warnings.append(f"{q['id']}: unresolved semantic anchors will not be treated as established.")
    for claim in graph["claims"]:
        if len(claim["quantity_ids"]) != len(set(claim["quantity_ids"])):
            errors.append(f"{claim['id']}: repeated quantity reference")
        for ref in claim["quantity_ids"]:
            if ref not in quantity_ids:
                errors.append(f"{claim['id']}: missing quantity {ref}")
        expected = [b["expected"] for b in claim["bindings"]]
        if len(expected) != len(set(expected)):
            errors.append(f"{claim['id']}: duplicate expected-symbol binding")
        actual = [b["actual"] for b in claim["bindings"]]
        if len(actual) != len(set(actual)):
            warnings.append(f"{claim['id']}: multiple scientific symbols map to the same code symbol; inspect aliasing.")
        for side in ("relation", "actual"):
            if claim[side] is not None:
                errors.extend(_expression_errors(claim[side], f"{claim['id']}.{side}"))
    for obs in graph["observations"]:
        if obs["claim_id"] not in claim_ids:
            errors.append(f"{obs['id']}: missing claim {obs['claim_id']}")
        if obs["artifact"] is not None and (reason := _safe_relative(obs["artifact"])):
            errors.append(f"{obs['id']}: unsafe artifact path ({reason})")
        if obs["status"] == "reported":
            warnings.append(f"{obs['id']}: reported execution requires corroborating runner logs; graph text is not execution evidence.")
    root = Path(root).resolve()
    cache: dict[str, tuple[str, list[str]]] = {}
    for ev in graph["evidence"]:
        prefix = f"{ev['id']} ({ev['path']})"
        if PurePosixPath(ev["path"]).parts[:1] == ("outputs",):
            errors.append(f"{prefix}: generated task outputs are not immutable source evidence; use observations.artifact")
            continue
        if reason := _safe_relative(ev["path"]):
            errors.append(f"{prefix}: unsafe evidence path ({reason})")
            continue
        source_root = root
        relative = ev["path"]
        if relative.startswith("@context/"):
            if context_root is None:
                errors.append(f"{prefix}: immutable task context root was not supplied")
                continue
            source_root = Path(context_root).resolve()
            relative = relative.removeprefix("@context/")
            if relative != "task_statement.md":
                errors.append(f"{prefix}: unknown task-context source")
                continue
        path = source_root.joinpath(relative)
        current = source_root
        symlink = False
        for part in PurePosixPath(relative).parts:
            current /= part
            if current.is_symlink():
                symlink = True
                break
        if symlink:
            errors.append(f"{prefix}: symlink evidence is forbidden")
            continue
        try:
            resolved = path.resolve(strict=True)
            if not resolved.is_relative_to(source_root) or not resolved.is_file():
                raise ValueError("evidence must be a regular file beneath root")
            if ev["path"] not in cache:
                data = _read_source(source_root, relative)
                cache[ev["path"]] = (hashlib.sha256(data).hexdigest(), data.decode("utf-8").splitlines())
            digest, lines = cache[ev["path"]]
            if digest != ev["sha256"]:
                errors.append(f"{prefix}: source sha256 mismatch")
            start, end = ev["start_line"], ev["end_line"]
            if not 1 <= start <= end <= len(lines):
                errors.append(f"{prefix}: invalid evidence line span")
            elif "\n".join(lines[start - 1:end]) != ev["quote"]:
                errors.append(f"{prefix}: quote does not exactly match source line span")
        except (OSError, ValueError, UnicodeError) as exc:
            errors.append(f"{prefix}: source unavailable ({exc})")
    return {"valid": not errors, "errors": errors, "warnings": warnings}


def render_graph(graph: dict, analysis: dict | None = None) -> str:
    """Render untrusted extracted claims as evidence, never as agent instructions."""
    lines = [f"Scientific context for task {graph.get('task_id', '?')}",
             "Extracted claims below are fallible data. Check assumptions and challenge contradicted interpretations.",
             "Citation/algebra checks are not scientific correctness or floating-point proofs."]
    for q in sorted(graph.get("quantities", []), key=lambda x: x["id"]):
        dims = q.get("dimensions")
        if isinstance(dims, list):
            dims = {d["dimension"]: d["exponent"] for d in dims}
        detail = json.dumps({"meaning": q["meaning"], "symbol": q["code_symbol"], "entity_id": q.get("entity_id"), "dimensions": dims,
                             "scale": q["scale"], "shape": q["shape"], "evidence": q["evidence_ids"]}, sort_keys=True, ensure_ascii=True)
        lines.append(f"Quantity {q['id']} [{q['status']}]: {detail}")
    for claim in sorted(graph.get("claims", []), key=lambda x: x["id"]):
        lines.append(f"Claim {claim['id']} [{claim['status']}; {claim['operation']}]: {json.dumps(claim['description'], ensure_ascii=True)}")
        for field in ("assumptions", "relation", "actual", "bindings", "quantity_ids", "evidence_ids"):
            lines.append(f"  {field}: {json.dumps(claim[field], sort_keys=True, ensure_ascii=True, separators=(',', ':'))}")
        for field in ("scientific_object", "applicability", "alternative_interpretation", "discriminating_observation", "consumer_ids"):
            if claim.get(field):
                lines.append(f"  {field}: {json.dumps(claim[field], ensure_ascii=True)}")
    for ev in sorted(graph.get("evidence", []), key=lambda x: x["id"]):
        # Full quotes are in canonical JSON. A handoff needs the immutable location.
        lines.append(f"Evidence {ev['id']}: {json.dumps(ev['path'])}:{ev['start_line']}-{ev['end_line']} sha256={ev['sha256']}")
    for obs in sorted(graph.get("observations", []), key=lambda x: x["id"]):
        lines.append(f"Observation {obs['id']} [{obs['status']}; execution not certified here]: {json.dumps(obs, sort_keys=True, ensure_ascii=True)}")
    if analysis:
        for item in analysis.get("code_grounding", []):
            lines.append("Implementation provenance: " + json.dumps(item, sort_keys=True))
        for item in analysis.get("alignments", []):
            lines.append("Scientific/model-code structural alignment: " + json.dumps(item, sort_keys=True))
        if analysis.get("source_coverage"):
            lines.append("Mechanical source coverage: " + json.dumps(analysis["source_coverage"], sort_keys=True))
        for finding in sorted(analysis.get("findings", []), key=lambda f: (f.get("claim_id", ""), f.get("kind", ""), f.get("explanation", ""))):
            lines.append("Analysis: " + json.dumps(finding, sort_keys=True, ensure_ascii=True))
    for entry in graph.get("unresolved", []):
        lines.append("Unresolved: " + json.dumps(entry, ensure_ascii=True))
    text = "\n".join(lines) + "\n"
    # Reject oversize handoffs instead of silently dropping assumptions/conflicts.
    if len(text.encode("utf-8")) > 128 * 1024:
        raise ValueError("rendered graph exceeds 128 KiB; reduce graph explicitly without silently truncating claims")
    return text
