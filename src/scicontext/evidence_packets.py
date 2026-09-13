"""Task/workflow-anchored evidence bundles, built without executing repository code.

Traversal follows recorded data dependencies and candidate callee links. It does
not promote lexical retrieval to proven dispatch or observations to requirements.
"""
from __future__ import annotations

import ast
import copy
import hashlib
import json
import re
from collections import defaultdict, deque
from pathlib import Path

from . import evidence
from .callee_context import HelperRetriever, MAX_HELPER_DEPTH, MAX_HELPER_BODIES, MAX_HELPER_FILES
from .packet import _reproducer

MAX_PACKETS = 8
MAX_PACKET_NODES = 150
MAX_HOPS = 12
MAX_BODY_CHARS = 24000
_CANDIDATE = {"may_invoke_body", "possible_callee_interface", "possible_callee_body"}
_STOP = {"the", "and", "for", "with", "from", "return", "source", "code", "task", "this",
         "that", "is", "in", "of", "to", "a", "an", "def", "self", "true", "false", "none",
         "not", "path", "values", "value", "result", "results", "input", "output", "run",
         "public", "check", "use", "using", "must", "should", "without", "implementation"}


def _tokens(text):
    words = set(re.findall(r"[a-zA-Z_][a-zA-Z_0-9]*", text.casefold()))
    return (words | {part for word in words for part in word.split("_") if len(part) >= 3}) - _STOP


def _entry_tokens(entry):
    """Code identifiers/configuration literals, not prose in error messages."""
    symbols = list(entry.get("entity_symbols") or [])
    try:
        tree = ast.parse(entry.get("expression_text") or "", mode="eval")
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                symbols.append(node.id)
            elif isinstance(node, ast.Attribute):
                symbols.append(node.attr)
            elif isinstance(node, ast.keyword) and node.arg:
                symbols.append(node.arg)
            elif isinstance(node, ast.Constant) and isinstance(node.value, str) and re.fullmatch(r"[A-Za-z_]\w*", node.value):
                symbols.append(node.value)
    except (ValueError, SyntaxError):
        # Native source identifiers already supplied by its frontend.
        symbols.extend(dep.get("name", "") for dep in entry.get("local_dependencies", []))
    return _tokens(" ".join(symbols))


def _id(value):
    return "ep_" + hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()[:24]


class _Sources:
    def __init__(self, root, entries, references):
        self.root = Path(root).resolve() if root is not None else None
        self.entries, self.references, self.cache = entries, references, {}
        self.trees = {}

    def load(self, path):
        if self.root is None:
            return None, None, None, "source_root_unavailable"
        if path not in self.cache:
            problem = evidence._safe_file(self.root, path)[1]
            raw = None
            if problem is None:
                try:
                    raw = evidence._read_regular(self.root, path)
                    expected = {e.get("sha256") for e in self.entries if e["path"] == path}
                    if expected and expected != {hashlib.sha256(raw).hexdigest()}:
                        problem = "source_hash_mismatch"
                    text = raw.decode("utf-8")
                    tree = ast.parse(text) if path.endswith(".py") else None
                    if tree is not None and not evidence._ast_within_limits(tree):
                        problem = "source_ast_limit"
                    if tree is not None and not problem:
                        self.trees[path] = (tree, evidence._ScopeIndex(tree))
                    definitions = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))] if tree else []
                except (OSError, ValueError, SyntaxError, UnicodeError, RecursionError) as exc:
                    problem = type(exc).__name__
            self.cache[path] = (None, None, None, problem) if problem else (raw, text, definitions, None)
        return self.cache[path]

    def body(self, entry):
        path = entry["path"]
        raw, text, definitions, problem = self.load(path)
        if problem:
            return None, problem
        line = entry.get("start_line", 0)
        enclosing = [n for n in definitions if n.lineno <= line <= n.end_lineno]
        if enclosing:
            node = min(enclosing, key=lambda n: n.end_lineno - n.lineno)
            start, end, kind = node.lineno, node.end_lineno, "complete_function_body"
        else:
            refs = [r for r in self.references if r["path"] == path and r["start_line"] <= line <= r["end_line"]]
            if not refs:
                return None, "enclosing_function_not_recorded"
            ref = min(refs, key=lambda r: r["end_line"] - r["start_line"])
            start, end, kind = ref["start_line"], ref["end_line"], "recorded_function_region"
        body = "\n".join(text.splitlines()[start - 1:end])
        if len(body) > MAX_BODY_CHARS:
            return None, "function_body_exceeds_limit"
        digest = hashlib.sha256(raw).hexdigest()
        return {"id": _id([path, digest, start, end]), "path": path, "sha256": digest,
                "start_line": start, "end_line": end, "kind": kind, "text": body}, None


def build_connected_input(graph, packet, root=None, *, max_objects=300, max_bytes=1_500_000):
    """Return interpreter input with complete node records and explicit bundle gaps."""
    objects = {o["id"]: o for o in graph["objects"]}
    operations = {o["id"]: o for o in graph["operations"]}
    nodes = {**objects, **operations}
    entries = {e["id"]: e for e in packet.get("entries", [])}
    docs = packet.get("documents", [])
    links = graph.get("links", [])
    incoming, candidates, entry_nodes = defaultdict(set), defaultdict(set), defaultdict(set)
    for link in links:
        if link["relation"] in _CANDIDATE:
            candidates[link["source"]].add(link["target"])
        else:
            incoming[link["target"]].add(link["source"])
    for identifier, node in nodes.items():
        ids = node.get("source_entry_ids", []) if identifier in objects else [node.get("source_entry_id")]
        for eid in ids:
            if eid in entries:
                entry_nodes[eid].add(identifier)
    task_docs = [d for d in docs if d.get("path") == "@context/task_statement.md"]
    task_tokens = _tokens(" ".join(d.get("quote", "") for d in task_docs))
    seeds = []
    for eid, entry in entries.items():
        if not entry_nodes[eid] or entry["kind"] in {"import", "docstring"}:
            continue
        matches = sorted(task_tokens & _entry_tokens(entry))
        workflow = _reproducer(entry["path"])
        reason = ("workflow_comparison" if workflow and entry["kind"] == "comparison" else
                  "workflow_return" if workflow and entry["kind"] == "return" else
                  "task_reference" if matches and (entry_nodes[eid] & operations.keys() or
                                                   entry["kind"] in {"signature", "parameter"}) else None)
        if reason:
            seeds.append(((-len(matches), {"workflow_comparison": 0, "workflow_return": 1, "task_reference": 2}[reason],
                           entry["path"], entry["start_line"], eid), eid, reason, matches))
    if not seeds:
        for identifier, obj in objects.items():
            if obj.get("kind") == "code_interface":
                for eid in obj.get("source_entry_ids", []):
                    if eid in entries:
                        e = entries[eid]
                        seeds.append(((0, 3, e["path"], e["start_line"], eid), eid, "interface_fallback", []))
    sources = _Sources(root, list(entries.values()), packet.get("coverage", {}).get("workflow_retrieval", {}).get("references", []))
    helpers = HelperRetriever(sources)
    bundles, kept, body_records, selected_docs, omitted = [], set(), {}, {}, []
    helper_records, helper_issue_records = {}, {}
    for doc in task_docs:
        selected_docs[doc["id"]] = doc

    def payload():
        selected_entries = {eid for eid, ids in entry_nodes.items() if ids & kept}
        helper_calls = copy.deepcopy(list(helper_records.values()))
        for call in helper_calls:
            call["caller_operation_ids"] = [oid for oid in call["caller_operation_ids"] if oid in kept]
            call["caller_result_object_ids"] = [oid for oid in call["caller_result_object_ids"] if oid in kept]
        return {"objects": [copy.deepcopy(o) for k, o in objects.items() if k in kept],
                "operations": [copy.deepcopy(o) for k, o in operations.items() if k in kept],
                "links": [copy.deepcopy(l) for l in links if l["source"] in kept and l["target"] in kept],
                "unsupported": [copy.deepcopy(u) for u in graph.get("unsupported", []) if u.get("source_entry_id") in selected_entries],
                "context": {"scientific_passages": list(selected_docs.values()),
                            "code_passages": [copy.deepcopy(e) for eid, e in entries.items() if eid in selected_entries],
                            "function_bodies": list(body_records.values()), "helper_calls": helper_calls,
                            "helper_gaps": list(helper_issue_records.values()),
                            "analysis_sources": copy.deepcopy(packet.get("analysis_sources", []))},
                "evidence_packets": copy.deepcopy(bundles)}

    for _, eid, reason, matches in sorted(seeds):
        starts = entry_nodes[eid] & operations.keys() or entry_nodes[eid]
        if starts <= kept:
            continue
        if len(bundles) >= MAX_PACKETS:
            omitted.append({"seed_entry_id": eid, "reason": "packet_limit"})
            continue
        selected, expanded, gaps, pending = set(), set(), [], deque((n, 0) for n in sorted(starts))
        while pending:
            identifier, depth = pending.popleft()
            if identifier in expanded:
                continue
            expanded.add(identifier)
            if identifier not in nodes:
                gaps.append({"node_id": identifier, "reason": "graph_endpoint_missing"})
                continue
            required = {identifier}
            if identifier in operations:
                op = operations[identifier]
                required.update(v["object_id"] for v in op.get("inputs", []) if v.get("object_id") in objects)
                required.update(v for v in op.get("output_ids", []) if v in objects)
                for value in op.get("inputs", []):
                    if value.get("object_id") not in objects:
                        gaps.append({"operation_id": identifier, "role": value.get("role"), "reason": "unresolved_input"})
                for value in op.get("output_ids", []):
                    if value not in objects:
                        gaps.append({"operation_id": identifier, "node_id": value, "reason": "graph_endpoint_missing"})
            if len(selected | required) > MAX_PACKET_NODES:
                gaps.append({"node_id": identifier, "reason": "packet_node_limit"})
                continue
            selected.update(required)
            for neighbor in sorted((required - {identifier}) | incoming[identifier] | candidates[identifier]):
                if neighbor in expanded:
                    continue
                if depth >= MAX_HOPS and neighbor not in required:
                    gaps.append({"node_id": neighbor, "reason": "dependency_hop_limit"})
                else:
                    pending.append((neighbor, depth + 1))
        if not selected:
            omitted.append({"seed_entry_id": eid, "reason": "anchor_exceeds_packet_node_limit"})
            continue
        selected_entries = {key for key, ids in entry_nodes.items() if ids & selected}
        # Preserve findings anchored to the selected source region. This is a
        # source-location association, not a new dependency or validated rule.
        observation_ids = {oid for oid, obj in objects.items() if obj.get("kind") == "constraint_locus" and any(
            e["path"] == obj.get("path") and (not obj.get("source_span", {}).get("start_line") or
            e["start_line"] <= obj["source_span"]["start_line"] <= e["end_line"])
            for key, e in entries.items() if key in selected_entries)}
        selected.update(observation_ids)
        bodies = {}
        for key in sorted(selected_entries):
            body, problem = sources.body(entries[key])
            if body:
                bodies[body["id"]] = body
            elif entries[key]["kind"] in {"signature", "return", "call", "comparison"}:
                gaps.append({"source_entry_id": key, "reason": problem})
        bodies, helper_links, helper_gaps = helpers.expand(bodies)
        helper_gaps = [{**g, "id": _id(g)} for g in helper_gaps]
        helper_links = copy.deepcopy(helper_links)
        for link in helper_links:
            site = link["call_site"]
            call_ops = [op for op in operations.values() if
                        op.get("source", {}).get("path") == site["path"] and
                        op.get("call_site") == {"start_line": site["start_line"], "start_col": site["start_col"]}]
            link["caller_operation_ids"] = [op["id"] for op in call_ops]
            link["caller_result_object_ids"] = [oid for op in call_ops for oid in op.get("output_ids", [])]
            link["id"] = _id([link["caller_body_id"], link["callee_body_id"], site])
        query = task_tokens | _tokens(" ".join(entries[key].get("expression_text") or "" for key in selected_entries))
        linked_docs = sorted((d for d in docs if d.get("id") and d not in task_docs and
                              query & _tokens(d.get("quote", ""))),
                             key=lambda d: (-len(query & _tokens(d.get("quote", ""))), d["id"]))[:3]
        possible = [l for l in links if l["relation"] in _CANDIDATE and l["source"] in selected and l["target"] in selected]
        bundle = {"id": _id([eid, sorted(selected)]),
            "anchor": {"entry_id": eid, "reason": reason, "task_matches": matches,
                       "path": entries[eid]["path"], "line": entries[eid]["start_line"]},
            "object_ids": sorted(selected & objects.keys()), "operation_ids": sorted(selected & operations.keys()),
            "source_entry_ids": sorted(selected_entries), "function_body_ids": sorted(bodies),
            "observation_ids": sorted(observation_ids),
            "document_ids": [d["id"] for d in task_docs + linked_docs],
            "documentation_status": "lexical_retrieval_candidates_not_semantic_proof",
            "candidate_call_links": possible, "gaps": gaps,
            "helper_call_ids": [link["id"] for link in helper_links],
            "helper_gap_ids": [gap["id"] for gap in helper_gaps],
            "boundary_links": [l for l in links if (l["source"] in selected) != (l["target"] in selected)],
            "claim_scope": "Recorded structure and source regions; no new scientific requirements or proven dispatch."}
        old = kept, body_records.copy(), selected_docs.copy(), helper_records.copy(), helper_issue_records.copy()
        kept = kept | selected
        body_records.update(bodies)
        helper_records.update({link["id"]: link for link in helper_links})
        helper_issue_records.update({gap["id"]: gap for gap in helper_gaps})
        selected_docs.update({d["id"]: d for d in linked_docs})
        bundles.append(bundle)
        if len(kept & objects.keys()) > max_objects or len(json.dumps(payload(), ensure_ascii=False).encode()) > max_bytes - min(65536, max_bytes // 8):
            kept, body_records, selected_docs, helper_records, helper_issue_records = old
            bundles.pop()
            omitted.append({"seed_entry_id": eid, "reason": "whole_packet_exceeds_input_budget"})
    result = payload()
    result["selection"] = {"strategy": "connected_evidence_packets_v1", "total_objects": len(objects),
        "kept_objects": len(result["objects"]), "kept_operations": len(result["operations"]),
        "truncated": len(result["objects"]) < len(objects), "omitted_packets": omitted,
        "limits": {"objects": max_objects, "bytes": max_bytes, "packets": MAX_PACKETS,
                   "packet_nodes": MAX_PACKET_NODES, "hops": MAX_HOPS, "body_chars": MAX_BODY_CHARS,
                   "helper_depth": MAX_HELPER_DEPTH, "helper_bodies_per_packet": MAX_HELPER_BODIES,
                   "helper_files": MAX_HELPER_FILES}}
    if len(json.dumps(result, ensure_ascii=False).encode()) > max_bytes:
        raise ValueError("Input budget is too small for the task context and omission receipt")
    return result
