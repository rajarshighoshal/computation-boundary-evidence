"""Build the compact scientific graph from existing extraction pipeline outputs.

The extraction pipeline (trace + objects + enrichment) already produced
everything needed. This module filters it to the task-relevant subset:
constraint loci + their implementations + the LLM's scientific annotations.

No source file reads, no Joern re-invocation — just filtering the graph
that already exists in scientific-objects.json + annotations.
"""
from __future__ import annotations

import json
from pathlib import Path

MAX_NODES = 12


def build_graph(graph_path: Path, annotations_path: Path) -> dict:
    """Filter the full extraction graph to the compact scientific view.

    Args:
        graph_path: scientific-objects.json from the extraction pipeline
        annotations_path: extract_draft-annotations.json from the enrichment LLM

    Returns: 5-20 nodes with scientific meaning, source locations, and findings.
    """
    graph = json.loads(graph_path.read_text())
    annotations_raw = json.loads(annotations_path.read_text()) \
        if annotations_path.is_file() else {"annotations": []}
    annotation_map = {a.get("object_id"): a for a in annotations_raw.get("annotations", [])
                     if isinstance(a, dict) and a.get("object_id")}

    # Collect all constraint loci (the scientific findings)
    loci = [obj for obj in graph.get("objects", [])
            if obj.get("kind") == "constraint_locus"
            and obj.get("properties", {}).get("status") == "violated"]

    # Collect code interfaces on implementation files (not reproduce.py)
    interfaces = [obj for obj in graph.get("objects", [])
                  if obj.get("kind") == "code_interface"
                  and obj.get("path", "") != "reproduce.py"]

    # Collect transition instances (executed functions from the trace)
    transitions = [obj for obj in graph.get("objects", [])
                   if obj.get("kind") == "transition_instance"
                   and obj.get("path", "") != "reproduce.py"]

    # Identify the scientific paths: files where loci point or their static candidates
    scientific_paths = set()
    for locus in loci:
        path = locus.get("path", "")
        if path and path != "reproduce.py":
            scientific_paths.add(path)
        for candidate in locus.get("properties", {}).get("static_candidates", []):
            if candidate.get("path"):
                scientific_paths.add(candidate["path"])

    # Also include paths from the dynamic summary (workflow-retrieved functions)
    dynamic = graph.get("dynamic", {})
    for func in dynamic.get("nondeterministic_funcs", []):
        if len(func) >= 1 and func[0]:
            scientific_paths.add(func[0])

    # Build node candidates: loci + interfaces on scientific paths + annotated objects
    candidates = []

    # 1. Constraint loci as nodes (the findings themselves)
    for locus in loci:
        props = locus.get("properties", {})
        annotation = annotation_map.get(locus.get("id"), {})
        static = props.get("static_candidates", [])
        # Point the locus at the implementation code, not reproduce.py
        primary_path = static[0]["path"] if static else locus.get("path", "")
        primary_line = static[0]["line"] if static else locus.get("source_span", {}).get("start_line", 0)
        # Build the finding description from measures
        measures = props.get("evidence", {}).get("measures", {})
        measure_text = "; ".join(f"{k}={v}" for k, v in measures.items() if v is not None)
        candidates.append({
            "priority": 0,
            "id": locus.get("id"),
            "name": f"FINDING: {props.get('constraint_type', 'constraint')} — {measure_text}"[:120],
            "path": primary_path,
            "line": primary_line,
            "language": _language(primary_path),
            "meaning": str(annotation.get("meaning", ""))[:200],
            "conventions": [],
            "findings": [{
                "rule": props.get("rule_id"),
                "type": props.get("constraint_type"),
                "measures": measures,
                "static_candidates": static[:3],
            }],
            "source": "",
        })

    # 2. Interfaces on scientific paths
    for interface in interfaces:
        path = interface.get("path", "")
        if path not in scientific_paths:
            continue
        props = interface.get("properties", {})
        annotation = annotation_map.get(interface.get("id"), {})
        candidates.append({
            "priority": 1,  # after loci
            "id": interface.get("id"),
            "name": (props.get("signature") or interface.get("symbol")
                     or path.split("/")[-1] + ":" + str(interface.get("source_span", {}).get("start_line", "?")))[:120],
            "path": path,
            "line": interface.get("source_span", {}).get("start_line", 0),
            "language": _language(path),
            "meaning": str(annotation.get("meaning", ""))[:200],
            "conventions": annotation.get("conventions", []),
            "findings": [],
            "source": "",
        })

    # 3. Annotated objects on any implementation path (even non-scientific-path)
    for obj_id, annotation in annotation_map.items():
        if annotation.get("meaning") and any(
                obj.get("id") == obj_id for obj in graph.get("objects", [])
                if obj.get("path", "") != "reproduce.py"
                and obj.get("kind") in ("code_interface", "quantity", "operation")):
            obj = next(o for o in graph.get("objects", []) if o.get("id") == obj_id)
            path = obj.get("path", "")
            if path and path != "reproduce.py":
                candidates.append({
                    "priority": 2,  # after interfaces
                    "id": obj_id,
                    "name": obj.get("symbol") or obj.get("kind", ""),
                    "path": path,
                    "line": obj.get("source_span", {}).get("start_line", 0),
                    "language": _language(path),
                    "meaning": str(annotation.get("meaning", ""))[:200],
                    "conventions": annotation.get("conventions", []),
                    "findings": [],
                    "source": "",
                })

    # Sort by priority, then path/line; deduplicate by id; cap at MAX_NODES
    candidates.sort(key=lambda c: (c["priority"], c["path"], c["line"]))
    seen = set()
    nodes = []
    for candidate in candidates:
        if candidate["id"] in seen or not candidate["id"]:
            continue
        seen.add(candidate["id"])
        nodes.append(candidate)
        if len(nodes) >= MAX_NODES:
            break

    # Preserve existing dependency edges from the extraction graph
    # (REACHING_DEF, CDG, CALL, PARAMETER_LINK — the real data flow)
    edges = []
    node_ids = {n["id"] for n in nodes}
    for link in graph.get("links", []):
        source, target = link.get("source", ""), link.get("target", "")
        if source in node_ids and target in node_ids:
            edges.append({"from": source, "to": target,
                          "relation": link.get("relation", "depends_on")})
    # Static candidate edges (loci → implementation files)
    for node in nodes:
        for finding in node.get("findings", []):
            for candidate in finding.get("static_candidates", []):
                target_path = candidate.get("path", "")
                for other in nodes:
                    if other["path"] == target_path and other["id"] != node["id"]:
                        edges.append({"from": node["id"], "to": other["id"],
                                      "relation": "investigates"})

    # Deduplicate edges
    seen_edges = set()
    unique_edges = []
    for edge in edges:
        key = (edge["from"], edge["to"], edge["relation"])
        if key not in seen_edges and edge["from"] != edge["to"]:
            seen_edges.add(key)
            unique_edges.append(edge)

    result = {
        "schema_version": "scientific-graph-1.0",
        "nodes": [{k: v for k, v in node.items() if k != "priority"} for node in nodes],
        "edges": unique_edges,
        "summary": {
            "total_loci": len(loci),
            "total_interfaces": len(interfaces),
            "annotated_implementation_objects": sum(1 for c in candidates if c["priority"] == 2),
            "scientific_paths": sorted(scientific_paths)[:5],
        },
    }
    result["serialized_bytes"] = len(json.dumps(result, ensure_ascii=False).encode())
    return result


def _language(path: str) -> str:
    from pathlib import Path as P
    suffix = P(path).suffix.lower()
    return {".py": "python", ".cpp": "cpp", ".c": "c", ".h": "cpp", ".hpp": "cpp",
            ".f90": "fortran", ".f": "fortran", ".m": "matlab", ".pyx": "cython",
            ".js": "javascript", ".java": "java", ".rs": "rust", ".go": "go",
            ".cc": "cpp", ".cxx": "cpp"}.get(suffix, "unknown")
