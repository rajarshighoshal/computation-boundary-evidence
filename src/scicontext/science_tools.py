"""Queryable public scientific evidence. No model calls or candidate-code execution."""
from __future__ import annotations

import argparse
import ast
import base64
import copy
import json
import hashlib
import os
import re
from pathlib import Path
from jsonschema import Draft202012Validator

from . import evidence
from .io import digest_json, read_json, write_json
from .language_frontends import extract_native_evidence, source_language
from .object_context import enrichment_input, object_bundle
from .representation import reading_input
from .scientific_graph import build_graph
from .scientific_model import VERSION, schema
from .scientific_objects import extract_objects

MAX_FILES = 20000
PAGE_SIZE = 6
MAX_FIND_RESULTS = 12
PREPARED_SOURCE = "<prepared>"


def tool_definition():
    model = schema()
    model["required"] = ["purpose", "computations", "expected_change", "preserve"]
    definitions = model.pop("$defs")
    model.pop("$schema", None)
    return {"type": "function", "function": {
        "name": "science", "description": (
            "Find and inspect public scientific evidence. A prepared graph connects the observed workflow to "
            "implementation computations, findings and dependencies: inspect target '#graph' for its nodes, then "
            "inspect node IDs for quantities, conditions, edges and citable source IDs. record_model saves your "
            "source-linked scientific understanding and unlocks ordinary repair tools. No action executes candidate code."),
        "parameters": {"type": "object", "properties": {
            "action": {"type": "string", "enum": ["find", "inspect", "record_model"]},
            "query": {"type": "string", "description": "Symbol, scientific phrase, or path to find."},
            "target": {"type": "string", "description": "Returned target/ID, relative path, path:line, or path#symbol."},
            "view": {"type": "string", "enum": ["relationships", "definitions", "source"]},
            "offset": {"type": "integer", "minimum": 0}, "model": model},
            "required": ["action"], "additionalProperties": False, "$defs": definitions}}}


class ScienceStore:
    def __init__(self, root, store):
        self.root, self.store = Path(root).resolve(), Path(store).resolve()
        self.store.mkdir(parents=True, exist_ok=True)
        self.path = self.store / "state.json"
        self.state = read_json(self.path) if self.path.exists() else {
            "schema_version": "science-store-1.0", "files": [], "payloads": {}, "targets": {},
            "visible_entities": [], "visible_sources": [], "model_recorded": False}

    def save(self):
        write_json(self.path, self.state)

    def prepare(self):
        files, truncated = [], False
        for directory, dirs, names in os.walk(self.root, followlinks=False):
            relative = Path(directory).relative_to(self.root)
            dirs[:] = sorted(d for d in dirs if not evidence._blocked(relative / d)
                             and not (Path(directory) / d).is_symlink()
                             and d not in {"outputs", "__pycache__", ".science_bench_build"})
            for name in sorted(names):
                path = (relative / name).as_posix()
                if evidence._safe_file(self.root, path)[1] is None:
                    files.append(path)
                if len(files) >= MAX_FILES:
                    truncated = True
                    break
            if truncated:
                break
        self.state.update(files=files, index_truncated=truncated)
        self.save()
        self._populate_graph()
        graph = self.state.get("scientific_graph") or {}
        graph_stats = ({"nodes": len(graph["nodes"]), "edges": len(graph.get("edges") or []),
                        "findings": (graph.get("summary") or {}).get("findings"),
                        "bytes": graph.get("serialized_bytes")}
                       if graph.get("nodes") else None)
        top = [p for p in files if "/" not in p and Path(p).suffix.lower() in {".md", ".txt", ".py"}]
        return {"status": "prepared", "files_indexed": len(files), "index_truncated": truncated,
                "task_map": top[:12], "scientific_graph": graph_stats,
                "note": "A prepared scientific graph connects the observed workflow to implementation "
                        "computations and findings: inspect target '#graph' for its nodes, then inspect "
                        "node IDs or returned targets."}

    def _populate_graph(self):
        """Build the compact scientific graph from prepared extraction outputs.

        The extraction pipeline writes scientific-objects.json (static objects,
        operations, links, execution-derived loci), packet.json and the observed
        trace during preparation. Nothing here calls a model.
        """
        graph_path = self.store / "scientific-objects.json"
        if not graph_path.is_file():
            self.state["scientific_graph"] = None
            return
        packet_path = self.store / "packet.json"
        try:
            graph = build_graph(graph_path, packet_path, self.store / "trace")
        except Exception as error:
            self.state["scientific_graph"] = {"error": f"{type(error).__name__}: {error}"}
            return
        self.state["scientific_graph"] = graph
        # Record the prepared representation so record_model joins against the
        # same graph the queries returned.
        try:
            raw_graph = read_json(graph_path)
            packet = read_json(packet_path) if packet_path.is_file() else {"entries": [], "documents": []}
            payload = enrichment_input(raw_graph, packet)
            key = digest_json(payload)
            write_json(self.store / "views" / (key + ".json"), payload)
            self.state["payloads"][key] = {"path": PREPARED_SOURCE, "prepared": True}
        except (OSError, ValueError, TypeError):
            pass
        self.save()

    def read(self, path):
        _, problem = evidence._safe_file(self.root, path)
        if problem:
            raise ValueError(problem)
        raw = evidence._read_regular(self.root, path)
        if len(raw) > evidence.MAX_FILE_BYTES:
            raise ValueError("File exceeds the parser read limit; no complete-file hash or coverage is claimed")
        if b"\x00" in raw:
            raise ValueError("Binary input: inspect its public interface/metadata, or use normal tools after recording the initial model.")
        return raw, raw.decode("utf-8")

    def find(self, query, offset=0):
        if not isinstance(query, str) or not query.strip():
            raise ValueError("Supply a symbol, scientific phrase or path")
        words = set(re.findall(r"[^\W_]+", query.casefold())) - {"the", "and", "of", "for", "in"}
        hits = []
        # Search prepared graph nodes first: node IDs are the citable targets.
        graph = self.state.get("scientific_graph") or {}
        for node in graph.get("nodes", []):
            searchable = " ".join(filter(None, [
                node.get("name", ""), node.get("signature", ""), node.get("path", ""),
                " ".join(node.get("quantities") or []), " ".join(node.get("conditions") or []),
                " ".join(f.get("type", "") for f in node.get("findings", []))]))
            terms = set(re.findall(r"[^\W_]+", searchable.casefold()))
            overlap = len(words & terms)
            if overlap > 0 or query.casefold() in searchable.casefold():
                findings = "; ".join(f"{f.get('rule')} {f.get('type')}"
                                     for f in node.get("findings", []))
                excerpt = f"{node.get('name', '')} @ {node.get('path', '')}:{node.get('line', 0)}"
                if findings:
                    excerpt += f" — findings: {findings}"
                hits.append((overlap * 10 + 20, node["id"], excerpt, "scientific_node"))
        for path in self.state["files"]:
            # Discovery is language-independent. Parsing capability determines
            # the inspect view, not whether public text can be found at all.
            try:
                _, text = self.read(path)
            except (OSError, ValueError, UnicodeError):
                continue
            path_terms = set(re.findall(r"[^\W_]+", path.casefold()))
            for line, text_line in enumerate(text.splitlines(), 1):
                terms = set(re.findall(r"[^\W_]+", text_line.casefold()))
                overlap = len(words & terms)
                if overlap == 0 and not (words and words <= path_terms) and query.casefold() not in text_line.casefold():
                    continue
                score = overlap * 3 + len(words & path_terms) + 8 * (query.lower() in text_line.lower())
                hits.append((score, f"{path}:{line}", text_line.strip(), "source"))
        hits.sort(key=lambda h: (-h[0], h[1]))
        page = hits[offset:offset + MAX_FIND_RESULTS]
        return {"status": "ok", "matches": [{"target": target, "excerpt": excerpt[:300], "kind": kind}
                                            for _, target, excerpt, kind in page],
                "total_matches": len(hits), "next_offset": offset + len(page) if offset + len(page) < len(hits) else None,
                "scope": "Lexical discovery, not a scientific relevance verdict. Explicit paths remain inspectable outside the index."}

    def _target(self, target):
        if not isinstance(target, str) or not target:
            raise ValueError("Supply a returned target, ID or relative source path")
        if target in self.state["targets"]:
            previous = self.state["targets"][target]
            raw, _ = self.read(previous["path"])
            if digest_json(raw.hex()) != previous["content_hash"]:
                raise ValueError("Source changed since this ID was inspected; inspect " + previous["path"] + " for current IDs")
            return previous["path"], previous["line"], None
        symbol = None
        if "#" in target:
            target, symbol = target.rsplit("#", 1)
        match = re.fullmatch(r"(.+):(\d+)", target)
        return (match[1], int(match[2]), symbol) if match else (target, 1, symbol)

    def inspect(self, target, view="relationships", offset=0, analysis=None):
        graph = self.state.get("scientific_graph") or {}
        if target == "#graph":
            nodes = graph.get("nodes") or []
            if not nodes:
                return {"status": "empty", "note": "No prepared graph in this store; find/inspect the file index "
                                                   "and record the model from inspected sources."}
            return {"status": "ok", "type": "scientific_graph",
                    "nodes": [{"id": node["id"], "name": node.get("name"), "path": node.get("path"),
                               "line": node.get("line"), "kind": node.get("kind"),
                               "instances": node.get("instances"),
                               "findings": [f.get("rule") for f in node.get("findings") or []]}
                              for node in nodes],
                    "edges": len(graph.get("edges") or []),
                    "documents": graph.get("documents") or [],
                    "summary": graph.get("summary") or {},
                    "note": "Inspect a node ID for findings, quantities, dependencies and source evidence; "
                            "inspect returned path:line targets for uncompiled detail."}
        # Scientific graph nodes are inspected from the prepared representation.
        graph_nodes = {n["id"]: n for n in graph.get("nodes", [])}
        if target in graph_nodes:
            node = graph_nodes[target]
            self._visible(node.get("entity_ids") or [], node.get("source_ids") or [])
            result = {"status": "ok", "target": target, "type": "scientific_node",
                      "name": node.get("name", ""), "path": node.get("path", ""),
                      "line": node.get("line", 0), "kind": node.get("kind", ""),
                      "language": source_language(node.get("path", "")),
                      "signature": node.get("signature"), "instances": node.get("instances"),
                      "arguments": node.get("arguments"), "findings": node.get("findings") or [],
                      "quantities": node.get("quantities") or [], "conditions": node.get("conditions") or [],
                      "operations": node.get("operations") or {}, "computation_id": node.get("computation_id"),
                      "entity_ids": node.get("entity_ids") or [], "source_ids": node.get("source_ids") or [],
                      "dependencies": [e for e in graph.get("edges", [])
                                       if e.get("from") == target or e.get("to") == target],
                      "boundary": node.get("boundary") or [],
                      "note": "IDs above are citable in record_model once inspected here."}
            if not node.get("source_ids") and node.get("path"):
                # No parsed region for this node in the prepared packet: compile
                # the public file location on demand so citations are real.
                try:
                    detail = self.inspect(f"{node['path']}:{node.get('line') or 1}", "relationships", 0, analysis)
                    result["evidence"] = {key: detail.get(key) for key in
                                          ("target", "computations", "quantities_and_expressions",
                                           "relationships", "sources", "coverage", "backend_request")}
                except (OSError, ValueError, KeyError, TypeError, SyntaxError) as error:
                    result["evidence_error"] = f"{type(error).__name__}: {error}"
            if view == "source":
                result["source"] = self._node_source(node)
            return result
        path, line, symbol = self._target(target)
        raw, text = self.read(path)
        lines = text.splitlines()
        if not 1 <= line <= max(1, len(lines)):
            raise ValueError("Source line outside file")
        language = source_language(path)
        is_document = Path(path).suffix.lower() in {".md", ".rst", ".txt", ".xml", ".json", ".toml", ".yaml", ".yml", ".cmake"} or Path(path).name == "CMakeLists.txt"
        tree = None
        if language == "python" and view != "source":
            try:
                tree = ast.parse(text, filename=path)
            except SyntaxError:
                language = None  # Keep a source-only inspectable computation.
        if tree is not None:
            definitions = []
            def walk(node, owner=""):
                for child in ast.iter_child_nodes(node):
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                        qualified = owner + "." + child.name if owner else child.name
                        definitions.append((qualified, child))
                        walk(child, qualified)
                    else:
                        walk(child, owner)
            walk(tree)
            matches = [n for qualified, n in definitions if (qualified == symbol.replace(".<locals>.", ".")
                       if "." in symbol else n.name == symbol)] if symbol else [n for _, n in definitions if n.lineno <= line <= n.end_lineno]
            if symbol and len(matches) != 1:
                return {"status": "ambiguous_target", "targets": [f"{path}:{n.lineno}" for n in matches]}
            owner = min(matches, key=lambda n: n.end_lineno-n.lineno) if matches else None
            start, end = (owner.lineno, owner.end_lineno) if owner else (line, min(len(lines), line+59))
        else:
            start, end = line, min(len(lines), line+79)
        reference = {"path": path, "start_line": start, "end_line": end}
        if view not in {"relationships", "definitions", "source"}:
            raise ValueError("Use relationships, definitions or source")
        if (view == "source" and not symbol) or is_document:
            start, end = line, len(lines)
        if is_document or view == "source":
            selected_text = "\n".join(lines[start-1:end])
            if offset > len(selected_text):
                raise ValueError("Offset outside source")
            quote = selected_text[offset:offset+8000]
            lo = start + selected_text[:offset].count("\n")
            hi = lo + quote.count("\n")
            identifier = "doc_" + digest_json([path, raw.hex(), start, offset, quote])[:24]
            document = {"id": identifier, "path": path, "start_line": lo, "end_line": hi, "quote": quote,
                        "source_kind": "document" if is_document else "code",
                        "character_offset": offset, "partial": offset > 0 or offset+len(quote) < len(selected_text)}
            payload = {"objects": [], "operations": [], "links": [], "unsupported": [],
                       "context": {"scientific_passages": [document] if is_document else [],
                           "code_passages": [] if is_document else [{k: v for k, v in
                                {**document, "kind": "source_excerpt", "text": quote}.items() if k != "quote"}],
                           "analysis_regions": [] if is_document else [{"path": path, "start_line": lo, "end_line": hi}]}}
            self._cache(payload, raw, path)
            self.state["targets"][identifier] = {"path": path, "line": lo, "content_hash": digest_json(raw.hex())}
            self._visible([], [identifier])
            return {"status": "ok", "source": document, "offset_unit": "characters",
                    "next_offset": offset+len(quote) if offset+len(quote) < len(selected_text) else None}
        if language == "python":
            packet = evidence.extract_evidence(self.root, [path], max_files=1, max_entries=2000,
                                               references=[reference], preserve_interfaces=True)
        elif language:
            packet = extract_native_evidence(self.root, [path], max_entries=2000, references=[reference])
            candidates = []
            for entry in packet["entries"]:
                name = entry.get("native", {}).get("function_name")
                if name and not entry.get("native", {}).get("declaration_only"):
                    last = max((e["end_line"] for e in packet["entries"] if e.get("function_scope") == entry["scope"]), default=entry["end_line"])
                    if (symbol and name == symbol) or (not symbol and entry["start_line"] <= line <= last):
                        candidates.append((last-entry["start_line"], entry["start_line"], last))
            if candidates:
                _, reference["start_line"], reference["end_line"] = min(candidates)
        else:
            packet = {"entries": [{"id": "ev_"+digest_json([path,raw.hex(),start,end])[:24], "path": path,
                "sha256": hashlib.sha256(raw).hexdigest(), "start_line": start, "end_line": end,
                "scope": "<source_excerpt>", "kind": "expression", "language": "unsupported",
                "text": "\n".join(lines[start-1:end]), "expression": None}],
                "coverage": {"task_local_retrieval": {"references": [reference]}}}
        packet.setdefault("coverage", {})["task_local_retrieval"] = {"references": [reference]}
        selected_view = reading_input({"context": {"code_passages": packet["entries"], "analysis_regions": [reference]}})
        selected_ids = {s["id"] for s in selected_view["sources"]}
        packet["entries"] = [e for e in packet["entries"] if e["id"] in selected_ids]
        graph = extract_objects(self.root, packet) if language else {"objects": [], "operations": [], "links": [], "unsupported": [{"reason": "source_only_language"}]}
        payload = enrichment_input(graph, packet)
        if analysis:
            from .source_backends import attach_source_analysis
            analysis = self._namespace_analysis(analysis)
            if not language:
                self._lift_analyzer_sources(payload, analysis, path, raw)
            attach_source_analysis(payload, analysis)
        self._cache(payload, raw, path)
        compiled = reading_input(payload)
        sources = {s["id"]: s for s in compiled["sources"]}
        entities = {e["id"]: e for e in compiled["entities"]}
        templates = {t["id"]: t for t in compiled["templates"]}
        computations = compiled["computations"]
        roots = [e for e in compiled["entities"] if e.get("kind") == "source_computation"]
        base = next((i for i, e in enumerate(roots) if e["id"] == target), None)
        if base is None:
            base = next((i for i, e in enumerate(roots) if any(sources[s]["start_line"] >= line for s in e["source_ids"])), 0)
        page_start = offset if offset else base
        page = roots[page_start:page_start+PAGE_SIZE]
        page_ids = {e["id"] for e in page}
        for item in page:
            page_ids.update(c["predicate_id"] for c in item.get("condition_refs", []) if c.get("predicate_id"))
        # Parameters and named quantities make operand bindings interpretable.
        neighbors = {r[k] for r in compiled["relations"] if r["source"] in page_ids or r["target"] in page_ids for k in ("source", "target")}
        page_ids.update(i for i in neighbors if entities[i].get("kind") != "source_computation")
        shown = [entities[i] for i in sorted(page_ids)]
        source_ids = {i for e in shown for i in e.get("source_ids", [])}
        source_ids.update(s["id"] for s in sources.values() if s.get("kind") == "code" and s["text"].lstrip().startswith(('"""', "'''")))
        inline_sources = []
        visible_sources = set()
        for identifier in sorted(source_ids):
            record = copy.deepcopy(sources[identifier])
            if len(record["text"]) > 6000:
                record.update(text="Not inlined; inspect this source location with view=source.",
                              omitted_text_chars=len(sources[identifier]["text"]),
                              expand_target=f"{record['path']}:{record['start_line']}")
            else:
                visible_sources.add(identifier)
            inline_sources.append(record)
        self._visible(page_ids | {c["id"] for c in computations}, visible_sources)
        for item in compiled["entities"]:
            if item.get("source_ids"):
                site = sources[item["source_ids"][0]]
                self.state["targets"][item["id"]] = {"path": path, "line": site["start_line"], "content_hash": digest_json(raw.hex())}
        for identifier, site in sources.items():
            self.state["targets"][identifier] = {"path": path, "line": site["start_line"], "content_hash": digest_json(raw.hex())}
        self.save()
        displayed_templates = []
        for identifier in sorted({e["template_id"] for e in shown if e.get("template_id")}):
            template = copy.deepcopy(templates[identifier])
            if len(json.dumps(template)) > 6000:
                owner = next(e for e in shown if e.get("template_id") == identifier)
                template = {"id": identifier, "structure_not_inlined": True,
                            "expand_target": owner["id"], "view": "source"}
            displayed_templates.append(template)
        from .source_backends import JOERN_SOURCE_SUFFIXES
        return {"status": "ok", "target": reference,
            "backend_request": ({**reference, "sha256": hashlib.sha256(raw).hexdigest()}
                                if analysis is None and view == "relationships" and Path(path).suffix.lower() in JOERN_SOURCE_SUFFIXES else None),
            "analysis_backends": [a["backend"] for a in (analysis or {}).get("analyses", [])],
            "analysis_gaps": (analysis or {}).get("gaps", []),
            "computations": [{"id": c["id"], "name": c["name"], "body_status": c["body_status"]} for c in computations],
            "quantities_and_expressions": shown,
            "templates": displayed_templates,
            "relationships": [r for r in compiled["relations"] if r["source"] in page_ids or r["target"] in page_ids],
            "sources": inline_sources,
            "next_offset": page_start+PAGE_SIZE if page_start+PAGE_SIZE < len(roots) else None,
            "total_expressions": len(roots), "coverage": compiled["coverage"],
            "note": "Other relationship endpoints are expandable IDs. Source excerpts are not a complete specification; scientific meanings are yours to establish."}

    @staticmethod
    def _namespace_analysis(analysis):
        result = copy.deepcopy(analysis)
        for backend in result.get("analyses", []):
            if backend["backend"] != "joern":
                continue
            prefix = digest_json([result.get("source_hashes", {}), backend.get("language"),
                                  sorted({n.get("path", "") for n in backend["nodes"]})])[:16] + ":"
            mapping = {n["id"]: prefix+n["id"] for n in backend["nodes"]}
            for node in backend["nodes"]:
                node["id"] = mapping[node["id"]]
            for edge in backend["links"]:
                edge["source"], edge["target"] = mapping[edge["source"]], mapping[edge["target"]]
            for method in backend.get("selection", {}).get("methods", []):
                method["id"] = mapping.get(method["id"], prefix+method["id"])
                method["node_ids"] = [mapping[i] for i in method["node_ids"]]
        return result

    @staticmethod
    def _lift_analyzer_sources(payload, analysis, path, raw):
        """Use Joern-located literal expressions for languages without a native syntax adapter."""
        lines = raw.decode().splitlines()
        entries = payload["context"]["code_passages"]
        for backend in analysis.get("analyses", []):
            if backend["backend"] != "joern":
                continue
            for node in backend["nodes"]:
                props, line = node.get("properties", {}), node.get("line")
                code = props.get("CODE", "")
                if node.get("path") != path or node["kind"] not in {"CALL", "RETURN"} or not line or not code:
                    continue
                last = line + len(code.splitlines()) - 1
                if last > len(lines) or code.strip() not in "\n".join(lines[line-1:last]):
                    continue  # Lowered/generated analyzer code is not literal source.
                identifier = "ev_" + digest_json([path, hashlib.sha256(raw).hexdigest(), line, props.get("COLUMN_NUMBER"), code])[:24]
                entries.append({"id": identifier, "path": path, "scope": node.get("scope"),
                    "kind": "expression", "language": backend.get("language", "unsupported"),
                    "start_line": line, "end_line": last, "text": code,
                    "start_col": max(0, props.get("COLUMN_NUMBER", 1)-1),
                    "end_col": max(0, props.get("COLUMN_NUMBER", 1)-1)+len(code.encode())})

    def _cache(self, payload, raw, path):
        key = digest_json(payload)
        write_json(self.store / "views" / (key + ".json"), payload)
        self.state["payloads"][key] = {"path": path, "content_hash": digest_json(raw.hex())}

    def _visible(self, entities, sources):
        self.state["visible_entities"] = sorted(set(self.state["visible_entities"]) | set(entities))
        self.state["visible_sources"] = sorted(set(self.state["visible_sources"]) | set(sources))
        self.save()

    def _node_source(self, node):
        """Inline the prepared passages a graph node cites, when available."""
        pieces = []
        for key, info in self.state.get("payloads", {}).items():
            if not info.get("prepared"):
                continue
            payload = read_json(self.store / "views" / (key + ".json"))
            context = payload.get("context") or {}
            entries = {e.get("id"): e for e in (context.get("code_passages") or [])}
            documents = {d.get("id"): d for d in (context.get("scientific_passages") or [])}
            for identifier in node.get("source_ids") or []:
                entry = entries.get(identifier) or documents.get(identifier)
                if entry:
                    pieces.append({"id": identifier, "path": entry.get("path"),
                                   "start_line": entry.get("start_line"), "end_line": entry.get("end_line"),
                                   "text": (entry.get("text") or entry.get("quote") or "")[:6000]})
        return pieces

    def record_model(self, model):
        if not isinstance(model, dict) or not model.get("expected_change") or not model.get("preserve"):
            raise ValueError("Record purpose, computations, expected_change and preserve with source citations")
        model = {"schema_version": VERSION, **model}
        errors = list(Draft202012Validator(schema()).iter_errors(model))
        if errors:
            raise ValueError("Invalid model fields: " + errors[0].message)
        def citations(value):
            if isinstance(value, dict):
                yield from value.get("source_ids", [])
                for key, child in value.items():
                    if key != "source_ids":
                        yield from citations(child)
            elif isinstance(value, list):
                for child in value:
                    yield from citations(child)
        if not set(citations(model)) <= set(self.state["visible_sources"]):
            raise ValueError("Cite source IDs whose contents you inspected")
        ids = [i for c in model.get("computations", []) for i in
               [c.get("computation_id"), *c.get("expression_ids", []), *(q.get("object_id") for q in c.get("quantities", []))]]
        if not ids or not set(ids) <= set(self.state["visible_entities"]):
            raise ValueError("Select computation/quantity/expression IDs returned by inspect")
        merged = {key: {} for key in ("objects", "operations", "unsupported", "links", "documents", "entries", "regions", "analysis")}
        current_hashes = {}
        for key in self.state["payloads"]:
            info = self.state["payloads"][key]
            if not info.get("prepared"):
                if info["path"] not in current_hashes:
                    current_hashes[info["path"]] = digest_json(self.read(info["path"])[0].hex())
                if current_hashes[info["path"]] != info["content_hash"]:
                    continue  # Previous source versions remain archived, not current evidence.
            payload = read_json(self.store / "views" / (key + ".json"))
            for field in ("objects", "operations", "links", "unsupported"):
                for item in payload.get(field, []):
                    merged[field][item.get("id", digest_json(item))] = item
            for field, source in (("documents", "scientific_passages"), ("entries", "code_passages"), ("regions", "analysis_regions"), ("analysis", "analysis_sources")):
                for item in payload.get("context", {}).get(source, []):
                    merged[field][item.get("id", digest_json(item))] = item
        graph = {k: list(merged[k].values()) for k in ("objects", "operations", "links", "unsupported")}
        graph.update(schema_version="scientific-objects-1.0", coverage={})
        payload = {**graph, "context": {"scientific_passages": list(merged["documents"].values()),
            "code_passages": list(merged["entries"].values()), "analysis_regions": list(merged["regions"].values()),
            "analysis_sources": list(merged["analysis"].values()),
            "linked_document_paths": [d["path"] for d in merged["documents"].values()]}}
        bundle = object_bundle(graph, model, reading_input(payload))
        if not bundle["assembly"]["usable"] or bundle["graph"]["enrichment"]["dropped"]:
            raise ValueError("Model not recorded: " + json.dumps(bundle["graph"]["enrichment"]["dropped"]))
        revision = self.state.get("model_revision", 0) + 1
        write_json(self.store / f"model-{revision}.json", bundle["graph"]["scientific_model"])
        write_json(self.store / "scientific-model.json", bundle["graph"]["scientific_model"])
        (self.store / "scientific-model.md").write_text(bundle["handoff"])
        self.state.update(model_recorded=True, model_revision=revision)
        self.save()
        return {"status": "recorded", "revision": revision, "repair_tools_enabled": True,
                "artifact": "scientific-model.json", "scope": "References checked; scientific correctness is not mechanically established."}

    def dispatch(self, request, analysis=None):
        if not isinstance(request, dict):
            raise ValueError("Tool request must be an object")
        action = request.get("action")
        offset = request.get("offset", 0)
        if type(offset) is not int or offset < 0:
            raise ValueError("offset must be a nonnegative integer")
        if action == "find":
            return self.find(request.get("query"), offset)
        if action == "inspect":
            return self.inspect(request.get("target"), request.get("view", "relationships"), offset, analysis)
        if action == "record_model":
            return self.record_model(request.get("model"))
        raise ValueError("Use find, inspect or record_model")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--request", help="Base64 JSON request")
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--analysis", type=Path, help="Caller-owned normalized analyzer receipt")
    args = parser.parse_args(argv)
    try:
        store = ScienceStore(args.root, args.store)
        result = store.prepare() if args.prepare else store.dispatch(json.loads(base64.b64decode(args.request).decode()),
                                                                  read_json(args.analysis) if args.analysis else None)
    except (OSError, ValueError, KeyError, TypeError, SyntaxError) as error:
        result = {"status": "error", "error": str(error)[:2000]}
    print(json.dumps(result, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
