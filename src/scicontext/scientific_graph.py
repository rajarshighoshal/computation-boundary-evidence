"""Compact connected scientific graph built from prepared, code-derived evidence.

Built before any model call from the extraction pipeline's own outputs: the
observed public workflow (execution trace), implementation computations and
their real dependencies (objects/operations/links), and execution-derived
constraint findings (violated loci). Model annotations are neither read nor
required; the repair agent's interpretation is joined later by record_model.

Node identity is (path, normalized scope): one node per observed function or
finding site, not one per variable. Every violated locus is preserved, and
dependency links that leave the selected node set are reported on the node as
boundary references instead of being silently dropped.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

from .execution_seed import read_execution_edges
from .io import digest_json
from .object_context import enrichment_input
from .representation import reading_input

MAX_NODES = 20
MAX_SOURCE_IDS = 6
MAX_ENTITY_IDS = 8
MAX_QUANTITIES = 5
MAX_BOUNDARY = 5
MAX_DOCUMENTS = 12
GRAPH_SCHEMA = "scientific-graph-2.0"

_LINE_SUFFIX = re.compile(r"@\d+")


def _load(path):
    if path is None:
        return None
    path = Path(path)
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def _scope_key(scope):
    """Normalize a scope string to its source identity name."""
    raw = str(scope or "").strip()
    if "::" in raw:
        # Joern-style C/C++ scopes: keep the innermost Class::method tail.
        stripped = re.sub(r"@\d+(?::\d+)?", "", raw)
        parts = stripped.rstrip(":.").split("::")
        head = parts[-2].split(".")[-1] if len(parts) >= 2 else ""
        return f"{head}::{parts[-1]}" if head else parts[-1]
    if "namespace_definition:" in raw:
        # Keep the innermost namespace segment with its block offset so distinct
        # namespace definitions in one file do not merge into a single node.
        tail = re.sub(r":\d+$", "", raw.rsplit("namespace_definition:", 1)[-1]).strip(":.")
        return tail or "<module>"
    scope = re.sub(r"@\d+(?::\d+)?", "", raw).strip()
    if scope.startswith("<module>."):
        scope = scope[len("<module>."):]
    if ":" in scope:  # Joern leaves `namespace:name` fragments
        scope = scope.rsplit(":", 1)[-1]
    return scope if scope and scope != "<script>" else "<module>"


def _entity_site(item):
    """(path, line) for an object or operation record."""
    source = item.get("source") or {}
    path = source.get("path") or item.get("path")
    line = source.get("start_line") or (item.get("source_span") or {}).get("start_line") or 0
    return path, line


def admit_selected_sources(payload, packet) -> None:
    """Admit the packet's selected public sources into the reading selection.

    reading_input keeps only passages inside analysis_regions; for tasks without
    execution regions (compiled languages) that silently dropped every selected
    source. The packet's own selection is the relevance evidence, so its paths
    become regions here.
    """
    coverage = packet.get("coverage") or {}
    paths = {path for path in coverage.get("selected_source_paths") or [] if isinstance(path, str)}
    if not paths:
        return
    ends = {}
    for entry in packet.get("entries") or []:
        path = entry.get("path")
        if path in paths:
            ends[path] = max(ends.get(path, 0), entry.get("end_line") or 0)
    regions = payload["context"].setdefault("analysis_regions", [])
    existing = {region.get("path") for region in regions}
    for path in sorted(paths - existing):
        end = ends.get(path) or 0
        regions.append({"path": path, "start_line": 1, "end_line": max(end, 1)})


def build_graph(graph_path, packet_path=None, trace_dir=None) -> dict:
    """Filter prepared extraction outputs to a compact, connected task graph."""
    graph = _load(graph_path) or {"objects": [], "operations": [], "links": []}
    packet = _load(packet_path) or {"entries": [], "documents": []}
    payload = enrichment_input(graph, packet)
    if isinstance(payload, dict) and isinstance(payload.get("context"), dict):
        admit_selected_sources(payload, packet if isinstance(packet, dict) else {})
    compiled = reading_input(payload)
    source_by_id = {s["id"]: s for s in compiled["sources"]}
    entity_by_id = {e["id"]: e for e in compiled["entities"]}

    operations = graph.get("operations") or []
    objects = graph.get("objects") or []
    links = graph.get("links") or []
    signatures = graph.get("dependence_signatures") or []
    loci = [o for o in objects if o.get("kind") == "constraint_locus"
            and (o.get("properties") or {}).get("status") == "violated"]

    operations_by_key = defaultdict(list)
    for operation in operations:
        source = operation.get("source") or {}
        path = source.get("path")
        if path:
            operations_by_key[(path, _scope_key(source.get("scope")))].append(operation)
    objects_by_key = defaultdict(list)
    for item in objects:
        source = item.get("source") or {}
        path = source.get("path") or item.get("path")
        if path:
            objects_by_key[(path, _scope_key(source.get("scope") or item.get("scope")))].append(item)

    signature_by_key = {}
    for signature in signatures:
        func = signature.get("func") or []
        if len(func) != 3:
            continue
        key = (func[0], _scope_key(func[1]))
        entry = {"line": func[2], "instances": signature.get("instances"),
                 "arguments": signature.get("arguments") or {}}
        known = signature_by_key.get(key)
        if known is None or (entry["instances"] or 0) > (known["instances"] or 0):
            signature_by_key[key] = entry

    computation_by_key = {}
    for computation in compiled["computations"]:
        site = source_by_id.get((computation.get("source_ids") or [None])[0])
        if site:
            key = (site["path"], _scope_key(computation.get("name")))
            computation_by_key.setdefault(key, computation)

    findings_by_key = defaultdict(list)
    for locus in loci:
        properties = locus.get("properties") or {}
        key = (locus.get("path"), _scope_key(locus.get("scope") or locus.get("symbol")))
        candidates = [{"path": c.get("path"), "line": c.get("line")}
                      for c in properties.get("static_candidates") or [] if c.get("path")]
        findings_by_key[key].append({
            "rule": properties.get("rule_id"),
            "type": properties.get("constraint_type"),
            "status": "violated",
            "declared_by": properties.get("predicate_source"),
            "measures": (properties.get("evidence") or {}).get("measures", {}),
            "candidate_count": len(candidates),
            "static_candidates": candidates,
        })
    candidate_paths = {c["path"] for findings in findings_by_key.values()
                       for finding in findings for c in finding["static_candidates"]}

    trace_edges = read_execution_edges(trace_dir) if trace_dir else []
    call_edges = {}
    call_sites = {}
    parents = defaultdict(set)
    for edge in trace_edges:
        caller = (edge["caller"]["file"], _scope_key(edge["caller"]["name"]))
        callee = (edge["callee"]["file"], _scope_key(edge["callee"]["name"]))
        if caller == callee:
            continue
        call_edges[(caller, callee)] = call_edges.get((caller, callee), 0) + edge.get("count", 1)
        call_sites[(caller, callee)] = {
            "caller": {"path": edge["caller"]["file"], "line": edge["caller"]["line"]},
            "callee": {"path": edge["callee"]["file"], "line": edge["callee"]["line"]}}
        parents[callee].add(caller)

    site_by_id = {}
    for operation in operations:
        path, line = _entity_site(operation)
        site_by_id[operation.get("id")] = f"{path}:{line}" if path else None
    for item in objects:
        path, line = _entity_site(item)
        site_by_id[item.get("id")] = f"{path}:{line}" if path else None

    selected = {}

    def add_node(key, mandatory=False):
        if key in selected or (not mandatory and len(selected) >= MAX_NODES):
            return
        path, name = key
        signature = signature_by_key.get(key) or {}
        computation = computation_by_key.get(key)
        operations_here = operations_by_key.get(key) or []
        objects_here = objects_by_key.get(key) or []
        source_ids = [operation["source_entry_id"] for operation in operations_here
                      if operation.get("source_entry_id")]
        for item in objects_here:
            source_ids.extend(item.get("source_entry_ids") or [])
        source_ids = [s for s in dict.fromkeys(source_ids) if s in source_by_id][:MAX_SOURCE_IDS]
        entity_ids = [computation["id"]] if computation else []
        for item in objects_here:
            if item.get("kind") in {"computational_value", "literal", "array",
                                    "source_predicate", "code_interface", "source_statement"}:
                entity_ids.append(item["id"])
        entity_ids = [e for e in dict.fromkeys(entity_ids) if e in entity_by_id][:MAX_ENTITY_IDS]
        interface = next((item for item in objects_here if item.get("kind") == "code_interface"), None)
        locus_line = min((item.get("source_span") or {}).get("start_line") or 0
                         for item in objects_here if item.get("kind") == "constraint_locus") \
            if any(item.get("kind") == "constraint_locus" for item in objects_here) else 0
        computation_line = 0
        if computation:
            computation_site = source_by_id.get((computation.get("source_ids") or [None])[0]) or {}
            computation_line = computation_site.get("start_line") or 0
        content_lines = [line for line in
                         (_entity_site(item)[1] for item in (*operations_here, *objects_here)) if line]
        line = signature.get("line") or computation_line or locus_line \
            or (interface or {}).get("source_span", {}).get("start_line") \
            or (min(content_lines) if content_lines else 1)
        operations_summary = defaultdict(int)
        for operation in operations_here:
            operations_summary[operation.get("kind")] += 1
        conditions = [item.get("symbol") for item in objects_here
                      if item.get("kind") == "source_predicate" and item.get("symbol")][:3]
        if operations_summary.get("source_comparison"):
            conditions.append(f"{operations_summary['source_comparison']} comparison(s)")
        selected[key] = {
            "id": "g_" + digest_json([path, name])[:16],
            "name": name,
            "path": path,
            "line": line,
            "kind": "workflow" if path == "reproduce.py" else "implementation",
            "instances": signature.get("instances"),
            "arguments": signature.get("arguments") or None,
            "signature": (interface or {}).get("properties", {}).get("signature"),
            "computation_id": computation["id"] if computation else None,
            "entity_ids": entity_ids,
            "source_ids": source_ids,
            "quantities": [{"id": item["id"], "name": item.get("symbol")} for item in objects_here
                           if item.get("kind") == "computational_value" and item.get("symbol")][:MAX_QUANTITIES],
            "conditions": conditions or None,
            "operations": dict(operations_summary) or None,
            "findings": findings_by_key.get(key, []),
            "boundary": [],
        }

    for key in findings_by_key:
        add_node(key, mandatory=True)

    order, frontier, seen = [], [key for key in findings_by_key], set(findings_by_key)
    while frontier:
        following = []
        for key in sorted(frontier):
            order.append(key)
            for parent in sorted(parents.get(key, ())):
                if parent not in seen:
                    seen.add(parent)
                    following.append(parent)
        frontier = following
    for key in order:
        add_node(key)

    def noisy(name):
        tail = name.split(".")[-1]
        return tail.startswith("__") or any(marker in name for marker in
                                            ("<locals>", "<genexpr>", "<dictcomp>", "<lambda>"))

    if len(selected) < MAX_NODES:
        adjacency = defaultdict(int)
        for caller, callee in call_edges:
            if caller in selected:
                adjacency[callee] += 1
            if callee in selected:
                adjacency[caller] += 1
        known = set(signature_by_key) | set(computation_by_key) | set(objects_by_key) | set(operations_by_key)
        ranked = sorted(known, key=lambda key: (
            0 if key[0] in candidate_paths else 1,
            0 if adjacency.get(key) else 1,
            1 if noisy(key[1]) else 0,
            -(signature_by_key.get(key, {}).get("instances") or 0),
            -len(operations_by_key.get(key) or []),
            key[0], key[1]))
        for key in ranked:
            if len(selected) >= MAX_NODES:
                break
            add_node(key)

    edges = []
    seen_edges = set()
    for (caller, callee), count in sorted(call_edges.items()):
        if caller in selected and callee in selected:
            edge = (selected[caller]["id"], selected[callee]["id"], "calls")
            if edge not in seen_edges:
                seen_edges.add(edge)
                edges.append({"from": edge[0], "to": edge[1], "relation": "calls", "count": count})

    # Finding candidates are real navigation evidence: connect each finding to
    # the nearest selected node in the candidate's file.
    by_path = defaultdict(list)
    for key in selected:
        by_path[key[0]].append(key)
    for node_key, findings in findings_by_key.items():
        if node_key not in selected:
            continue
        for finding in findings:
            for candidate in finding["static_candidates"]:
                path = candidate["path"]
                if path not in by_path or path == node_key[0]:
                    continue
                same_path = sorted(by_path[path], key=lambda key: selected[key]["line"])
                line = candidate.get("line") or 0
                at_or_before = [key for key in same_path if selected[key]["line"] <= line]
                target = at_or_before[-1] if at_or_before else same_path[0]
                edge = (selected[node_key]["id"], selected[target]["id"], "candidate")
                if edge not in seen_edges:
                    seen_edges.add(edge)
                    edges.append({"from": edge[0], "to": edge[1], "relation": "candidate"})

    owner_by_entity = {}
    for key in selected:
        for operation in operations_by_key.get(key, ()):
            owner_by_entity[operation.get("id")] = key
        for item in objects_by_key.get(key, ()):
            owner_by_entity[item.get("id")] = key

    for link in links:
        relation = (link.get("relation") or "depends_on").split(":")[0]
        source_key = owner_by_entity.get(link.get("source"))
        target_key = owner_by_entity.get(link.get("target"))
        if source_key in selected and target_key in selected and source_key != target_key:
            edge = (selected[source_key]["id"], selected[target_key]["id"], relation)
            if edge not in seen_edges:
                seen_edges.add(edge)
                edges.append({"from": edge[0], "to": edge[1], "relation": relation})
        elif source_key in selected or target_key in selected:
            node_key = source_key if source_key in selected else target_key
            other = link.get("target") if node_key is source_key else link.get("source")
            site = site_by_id.get(other)
            reference = {"target": site, "relation": relation}
            if site and reference not in selected[node_key]["boundary"] \
                    and len(selected[node_key]["boundary"]) < MAX_BOUNDARY:
                selected[node_key]["boundary"].append(reference)

    # Observed calls that leave the selected set stay visible as boundary
    # references instead of disappearing with the cut edge.
    for (caller, callee), sites in sorted(call_sites.items()):
        if caller in selected and callee not in selected:
            reference = {"target": f"{sites['callee']['path']}:{sites['callee']['line']}", "relation": "calls"}
            if reference not in selected[caller]["boundary"] and \
                    len(selected[caller]["boundary"]) < MAX_BOUNDARY:
                selected[caller]["boundary"].append(reference)
        elif callee in selected and caller not in selected:
            reference = {"target": f"{sites['caller']['path']}:{sites['caller']['line']}", "relation": "calls"}
            if reference not in selected[callee]["boundary"] and \
                    len(selected[callee]["boundary"]) < MAX_BOUNDARY:
                selected[callee]["boundary"].append(reference)

    documents = {}
    for document in packet.get("documents") or []:
        path = document.get("path")
        if path:
            documents[path] = documents.get(path, 0) + 1
    nodes = list(selected.values())
    if not isinstance(graph, dict):
        graph = {"objects": [], "operations": [], "links": []}
    dynamic_value = graph.get("dynamic")
    dynamic = dynamic_value if isinstance(dynamic_value, dict) else {}
    reproduction = dynamic.get("reproduction")
    result = {
        "schema_version": GRAPH_SCHEMA,
        "nodes": nodes,
        "edges": edges,
        "documents": [{"path": path, "passages": count}
                      for path, count in sorted(documents.items())[:MAX_DOCUMENTS]],
        "summary": {
            "workflow_nodes": sum(1 for node in nodes if node["kind"] == "workflow"),
            "implementation_nodes": sum(1 for node in nodes if node["kind"] == "implementation"),
            "findings": sum(len(node["findings"]) for node in nodes),
            "observed_call_pairs": len(call_edges),
            "calls_edges": sum(1 for edge in edges if edge["relation"] == "calls"),
            "edges": len(edges),
        },
    }
    if reproduction:
        result["reproduction"] = reproduction
        result["summary"]["reproduction_classification"] = reproduction.get("classification")
    result["serialized_bytes"] = len(json.dumps(result, ensure_ascii=False).encode())
    return result
