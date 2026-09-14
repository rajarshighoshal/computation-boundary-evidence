"""Source-level views of one evidence graph; parser machinery is not model context.

Templates identify repeated ordered syntax, NOT equivalent values or algorithms.
Bindings, source conditions and conservative dependency edges remain per occurrence.
"""
from __future__ import annotations

import ast
import copy
from collections import Counter
from pathlib import PurePosixPath

from .io import digest_json

READING_VERSION = "scientific-reading-2.0"
_EXPRESSION_KINDS = {"assignment", "return", "call", "comparison", "predicate", "condition",
                     "expression", "augmented_assignment", "assertion", "container_mutation"}
_DEPENDENCIES = {"REACHING_DEF", "CDG", "CALL", "PARAMETER_LINK"}


def _pattern(entry):
    """Factor syntax into a shared tree and occurrence-specific identifier bindings.

    Constants, call/member names, operand order, subscripts and keyword names stay
    in the template. No algebraic rewriting, evaluation or candidate imports.
    """
    bindings = []

    def slot(name):
        if name not in bindings:
            bindings.append(name)
        return {"slot": bindings.index(name)}

    class Parameterize(ast.NodeTransformer):
        def visit_Name(self, node):
            return ast.copy_location(ast.Name(id="_q" + str(slot(node.id)["slot"]), ctx=node.ctx), node)

    text = entry.get("text", "")
    tree = entry.get("native_expression")
    if tree:
        effect = {k: v for k, v in entry.get("native", {}).items()
                  if k in {"operator", "target", "nonlocal_write", "writes_root"}}
        if tree.get("position_kind") == "cython_ast_line_envelope":
            if any(node.get("keywords_present") for node in _native_nodes(tree)):
                return {"language": "cython", "expression": text,
                        "binding_scope": "keyword_names_kept_in_source_syntax"}, [], False
            def structural(node):
                if isinstance(node, list):
                    return [structural(v) for v in node]
                if not isinstance(node, dict):
                    return node
                if node.get("kind") == "name":
                    return slot(node["name"])
                return {k: structural(v) for k, v in node.items()
                        if k not in {"span", "position_kind", "text"} or
                        k == "text" and node.get("kind") in {"literal", "unknown"}}
            return {"language": "cython", "tree": structural(tree), "effect": effect}, bindings, False
        # Large data initializers are one data object, with referenced symbols
        # preserved. Names in a table are NOT claimed to be compile-time constants.
        if tree.get("syntax_kind") == "initializer_list" and len(tree.get("children", [])) > 32:
            stack, names, kinds = [tree], set(), Counter()
            while stack:
                node = stack.pop()
                if isinstance(node, dict):
                    kinds[node.get("kind", "container")] += 1
                    if node.get("kind") == "name":
                        names.add(node.get("name", node.get("text", "")))
                    stack.extend(v for v in node.values() if isinstance(v, (dict, list)))
                elif isinstance(node, list):
                    stack.extend(node)
            bindings.extend(sorted(names))
            return {"data_initializer": {"entries": len(tree["children"]), "syntax_counts": dict(kinds),
                     "source_digest": digest_json(text), "referenced_names": sorted(names),
                     "constant_evaluation": "not_established"}}, bindings, True
        # The frontend already supplies byte spans. Replace only parsed name
        # occurrences; operators, arguments, indices and every unknown token stay.
        raw = tree.get("text", text).encode()
        base = tree.get("span", [0])[0]
        stack, replacements = [tree], {}
        while stack:
            node = stack.pop()
            if isinstance(node, dict):
                if node.get("kind") == "name" and node.get("span"):
                    lo, hi = (offset - base for offset in node["span"])
                    if 0 <= lo < hi <= len(raw):
                        replacements[(lo, hi)] = (node.get("name", node.get("text", "")))
                stack.extend(v for v in node.values() if isinstance(v, (dict, list)))
            elif isinstance(node, list):
                stack.extend(node)
        parts, offset = [], 0
        for (lo, hi), name in sorted(replacements.items()):
            if lo < offset:
                continue
            parts.extend([raw[offset:lo], ("_q" + str(slot(name)["slot"])).encode()])
            offset = hi
        parts.append(raw[offset:])
        return {"language": entry.get("language"), "expression": b"".join(parts).decode(),
                "syntax_kind": tree.get("syntax_kind", tree.get("kind")), "effect": effect}, bindings, False
    if entry.get("language") not in {None, "python"}:
        return {"language": entry.get("language"), "unparsed_expression": text}, [], False
    try:
        parsed = ast.parse(text)
        if any(isinstance(n, (ast.Lambda, ast.comprehension, ast.NamedExpr)) for n in ast.walk(parsed)):
            return {"language": "python", "expression": ast.unparse(parsed),
                    "binding_scope": "nested_bindings_kept_in_source_syntax"}, [], False
        # Avoid expanding literal collections into a huge prompt. literal_eval
        # parses data only; it never imports or executes source code.
        value = parsed.body if isinstance(parsed, ast.Expression) else None
        if value is None and len(parsed.body) == 1 and isinstance(parsed.body[0], ast.Assign):
            value = parsed.body[0].value
        if isinstance(value, (ast.List, ast.Tuple, ast.Set, ast.Dict)) and len(list(ast.walk(value))) > 256:
            try:
                literal = ast.literal_eval(value)
            except (ValueError, TypeError, SyntaxError, RecursionError):
                pass
            else:
                return {"literal_collection": {"type": type(literal).__name__, "entries": len(literal),
                        "source_digest": digest_json(text)}}, [], True
        return {"language": "python", "expression": ast.unparse(Parameterize().visit(parsed))}, bindings, False
    except (ValueError, SyntaxError, RecursionError):
        return {"language": entry.get("language"), "unparsed_expression": text}, [], False


def reading_input(payload):
    """Project source expressions, scoped quantities and actual dependency edges.

    Full objects/CPG records stay in evidence-input.json/source-analysis.json.
    This view owns no new dispatch, unit, scientific-law or equality assertions.
    """
    if payload.get("schema_version") == READING_VERSION:
        return copy.deepcopy(payload)
    context = payload.get("context", payload)
    passages = {p["id"]: p for p in context.get("code_passages", [])}
    all_passages = passages
    regions = context.get("analysis_regions", [])
    if regions:
        selected = {identifier for identifier, p in passages.items() if any(
            p.get("path") == r.get("path") and r.get("start_line", 0) <= p.get("start_line", -1) <= r.get("end_line", 0)
            for r in regions)}
        # Follow only explicit definition identities, not similar variable names.
        pending = list(selected)
        while pending:
            current = passages[pending.pop()]
            dependencies = [d.get("definition_id") for d in current.get("local_dependencies", [])]
            dependencies.extend(i for i, p in passages.items() if p.get("path") == current.get("path")
                and (owner := p.get("condition_for", p.get("native", {}).get("condition_for")))
                and any(label == owner or label.startswith(owner + ":") for label in current.get("branch", [])))
            for identifier in dependencies:
                if identifier in passages and identifier not in selected:
                    selected.add(identifier)
                    pending.append(identifier)
        scopes = {(passages[i].get("path"), passages[i].get("scope", "")) for i in selected}
        selected.update(i for i, p in passages.items() if p.get("kind") in {"signature", "docstring", "parameter"}
                        and any(p.get("path") == path and p.get("scope") and
                                (scope == p["scope"] or scope.startswith(p["scope"] + ".")) for path, scope in scopes))
        passages = {i: p for i, p in passages.items() if i in selected}
    entities, sources, definitions, templates, expressions = {}, {}, {}, {}, {}
    relations, seen_edges = [], set()

    def source(record, kind="code", text=None):
        result = {k: record[k] for k in ("id", "path", "start_line", "end_line", "language") if record.get(k) is not None}
        result.update(kind=kind, text=text if text is not None else record.get("quote", record.get("text", "")))
        sources[record["id"]] = result

    def edge(left, right, role, properties=None):
        if left == right or left not in entities or right not in entities:
            return
        key = (left, right, role, digest_json(properties or {}))
        if key not in seen_edges:
            relations.append({"id": "r" + str(len(relations)), "source": left, "target": right, "relation": role,
                              **({"properties": copy.deepcopy(properties)} if properties else {})})
            seen_edges.add(key)

    document_duplicates, document_ids, document_omissions = {}, {}, Counter()
    for passage in context.get("scientific_passages", []):
        if passage.get("id"):
            path = PurePosixPath(passage.get("path", ""))
            # Task/public scientific docs, plus explicitly linked repository docs.
            # Package-wide README/license inventories stay in the evidence file.
            if len(path.parts) > 1 and not str(path).startswith("@context/") and str(path) not in context.get("linked_document_paths", []):
                document_omissions["unlinked_repository_document"] += 1
                continue
            text = passage.get("quote", passage.get("text", ""))
            if text in document_ids:
                document_duplicates[passage["id"]] = document_ids[text]
                sources[document_ids[text]].setdefault("additional_origins", []).append(
                    {k: passage[k] for k in ("id", "path", "sha256", "start_line", "end_line") if k in passage})
                continue
            document_ids[text] = passage["id"]
            source(passage, "document")
    # Explanatory docstrings and interfaces remain attached to their actual site.
    for record in passages.values():
        if record.get("kind") in {"docstring", "signature", "parameter"}:
            source(record)
    for obj in payload.get("objects", []):
        if obj.get("kind") != "code_interface" and not obj.get("symbol"):
            continue  # intermediates are inside the source-expression templates
        props = {k: v for k, v in obj.get("properties", {}).items()
                 if v is not None and k in {"dimensions", "scale_to_si", "shape", "units", "parameter", "type"}}
        ids = [identifier for identifier in obj.get("source_entry_ids", []) if identifier in passages]
        if not ids:
            continue
        entities[obj["id"]] = {"id": obj["id"], "kind": obj["kind"], "name": obj.get("symbol"),
                               "properties": props, "source_ids": ids}
        if obj["kind"] == "code_interface":
            definitions[obj["id"]] = {"id": obj["id"], "name": obj.get("symbol") or obj.get("scope"),
                "path": obj.get("path"), "scope": obj.get("scope"), "source_ids": ids,
                "entity_ids": [obj["id"]]}
    data_ids = set()
    for record in passages.values():
        if not (record.get("kind") in _EXPRESSION_KINDS or record.get("expression_text") or record.get("native_expression")):
            continue
        pattern, names, data = _pattern(record)
        key = "t" + digest_json(pattern)[:12]
        templates.setdefault(key, {"id": key, "structure": pattern})
        identifier = record["id"]
        source(record, "data" if data else "code", text=("Data initializer; exact values remain at this source location."
                                                       if data else record.get("text", "")))
        if data:
            data_ids.add(identifier)
        dependencies = {d["name"]: d for d in record.get("local_dependencies", [])}
        bindings = []
        for index, name in enumerate(names):
            dependency = dependencies.get(name, {})
            bindings.append({"slot": index, "name": name, "definition_id": dependency.get("definition_id"),
                             "status": dependency.get("status", "unresolved"),
                             **({"reason": dependency["reason"]} if dependency.get("reason") else {})})
            if name in record.get("imports", {}):
                bindings[-1]["import_target"] = record["imports"][name]
        entities[identifier] = {"id": identifier, "kind": "data_initializer" if data else "source_computation",
            "name": record.get("kind", "expression"), "statement_kind": record.get("kind"),
            "template_id": key, "bindings": bindings, "source_ids": [identifier],
            "results": record.get("entity_symbols", record.get("targets", [])),
            "conditions": copy.deepcopy(record.get("branch", []))}
        if data:
            entities[identifier]["name"] = "data initializer"
        expressions[identifier] = record
    # A named quantity's declaration may not be a computation (e.g. parameter).
    for entity in entities.values():
        for identifier in entity["source_ids"]:
            if identifier in passages and identifier not in sources:
                source(passages[identifier])

    for identifier, record in expressions.items():
        condition_refs = []
        for label in record.get("branch", []):
            matches = [other for other, p in expressions.items() if p.get("path") == record.get("path")
                       and (owner := p.get("condition_for", p.get("native", {}).get("condition_for")))
                       and (label == owner or label.startswith(owner + ":"))]
            condition_refs.append({"branch": label, "predicate_id": matches[0] if len(matches) == 1 else None})
        entities[identifier]["condition_refs"] = condition_refs
        for condition in condition_refs:
            if condition["predicate_id"]:
                edge(condition["predicate_id"], identifier, "guards:" + condition["branch"])
        for binding in entities[identifier].get("bindings", []):
            target = binding["definition_id"]
            if target not in entities:
                if target is not None:
                    binding.update(definition_id=None, status="outside_selected_view")
                continue
            edge(target, identifier, "defines:" + binding["name"])
    object_map = {obj["id"]: obj for obj in payload.get("objects", [])}
    operation_map = {op["id"]: op.get("source_entry_id") for op in payload.get("operations", [])}
    for operation in payload.get("operations", []):
        identifier = operation.get("source_entry_id")
        if identifier in expressions and operation.get("documentation_url"):
            entities[identifier].setdefault("api_contracts", []).append(
                {k: copy.deepcopy(operation[k]) for k in ("kind", "api", "properties", "documentation_url", "assumptions") if k in operation})
    # Preserve object bindings/call-target candidates as evidence, not proved dispatch.
    projection = {**{i: i for i in entities}, **{i: s for i, s in operation_map.items() if s in entities}}
    for obj in payload.get("objects", []):
        if obj["id"] not in projection:
            candidates = [s for s in obj.get("source_entry_ids", []) if s in expressions]
            if len(candidates) == 1:
                projection[obj["id"]] = candidates[0]
    for link in payload.get("links", []):
        a, b = projection.get(link.get("source")), projection.get(link.get("target"))
        if a and b:
            edge(a, b, link["relation"])

    # Quotient Joern's dependence graph by source occurrence. Match only a unique
    # smallest source span containing the node's literal code, never just a name.
    analyzer = context.get("analysis_sources", [])
    projected_nodes, unprojected = {}, Counter()
    for node in analyzer:
        if node.get("kind") == "edge":
            continue
        candidates = [r for i, r in expressions.items() if i not in data_ids and r.get("path") == node.get("path")
                      and r.get("start_line", 0) <= node.get("start_line", -1) <= r.get("end_line", 0)
                      and node.get("text") and node["text"].strip() in r.get("text", "")]
        column = node.get("properties", {}).get("COLUMN_NUMBER")
        if column is not None:
            # Joern columns are one-based; packet source columns are zero-based.
            candidates = [r for r in candidates if r.get("start_col") is None or
                (r["start_line"] < node["start_line"] or r["start_col"] <= column - 1) and
                (r["end_line"] > node["start_line"] or r.get("end_col", column) >= column - 1)]
        def span_width(record):
            lines = record["end_line"] - record["start_line"]
            return (lines, record.get("end_col", 10**9) - record.get("start_col", 0) if lines == 0 else 0)
        if candidates:
            width = min(map(span_width, candidates))
            candidates = [r for r in candidates if span_width(r) == width]
        if len(candidates) == 1:
            projected_nodes[node["id"]] = candidates[0]["id"]
            if node.get("dispatch"):
                entities[candidates[0]["id"]].setdefault("dispatch_evidence", []).append(copy.deepcopy(node["dispatch"]))
        else:
            unprojected[node.get("kind", "unknown")] += 1
    projected_edges = 0
    for row in analyzer:
        if row.get("kind") == "edge" and row.get("relation") in _DEPENDENCIES:
            a, b = projected_nodes.get(row.get("source")), projected_nodes.get(row.get("target"))
            if a and b:
                edge(a, b, "joern:" + row["relation"], row.get("properties"))
                projected_edges += 1

    # Function view uses source scope identity. Module-level expressions stay
    # individual computations; they are not invented callable definitions.
    for identifier, entity in entities.items():
        record = expressions.get(identifier) or object_map.get(identifier, {})
        path, scope = record.get("path"), record.get("scope")
        owners = [d for d in definitions.values() if d.get("path") == path and scope and d.get("scope")
                  and (scope == d["scope"] or scope.startswith(d["scope"] + "."))]
        if owners:
            width = max(len(d["scope"]) for d in owners)
            owners = [d for d in owners if len(d["scope"]) == width]
        if len(owners) == 1:
            if identifier not in owners[0]["entity_ids"]:
                owners[0]["entity_ids"].append(identifier)
        elif identifier in expressions:
            definitions[identifier] = {"id": identifier, "name": entity["name"], "source_ids": [identifier],
                                      "entity_ids": [identifier]}
    for definition in definitions.values():
        members = set(definition["entity_ids"])
        links = [r for r in relations if r["source"] in members or r["target"] in members]
        definition["relation_ids"] = [r["id"] for r in links]
        definition["boundary_ids"] = sorted({r[k] for r in links for k in ("source", "target")} - members)
        definition["body_status"] = "source_excerpt" if members & expressions.keys() else "interface_only"
        definition.pop("scope", None)
        definition.pop("path", None)
    # Repeated non-scientific diagnostics remain counts, with full records on disk.
    return {"schema_version": READING_VERSION, "computations": list(definitions.values()),
        "entities": list(entities.values()), "templates": list(templates.values()), "relations": relations,
        "sources": list(sources.values()), "observations": copy.deepcopy(context.get("observations", [])),
        "coverage": {"projection": "Ordered source-expression templates with scoped bindings; shared syntax is not value equality.",
            "source_expressions": len(expressions), "shared_templates": len(templates), "data_initializers": len(data_ids),
            "task_slice_entries": len(passages), "available_entries": len(all_passages),
            "duplicate_document_passages": len(document_duplicates),
            "document_omissions": dict(document_omissions),
            "operations_without_source_expression": sum(s not in expressions for s in operation_map.values()),
            "joern_projected_nodes": len(projected_nodes), "joern_projected_edges": projected_edges,
            "joern_unprojected_kinds": dict(unprojected),
            "unsupported_counts": dict(Counter(r.get("reason", "unknown") for r in payload.get("unsupported", []))),
            "source_selection": {k: v for k, v in payload.get("selection", {}).items() if isinstance(v, (int, bool))},
            "detail_artifacts": ["evidence-input.json", "source-analysis.json", "packet.json"]}}


def render_reading(view):
    """Readable interpretation view of the SAME representation, not a second model.

    IDs remain exact. Show source statements once instead of repeated membership,
    source tables, CPG scaffolding and null metadata. Detailed views remain on disk.
    """
    sources = {s["id"]: s for s in view["sources"]}
    entities = {e["id"]: e for e in view["entities"]}
    lines = ["# Task evidence", ""]
    for source in sources.values():
        if source["kind"] == "document":
            lines += [f"[{source['id']}] {source['path']}:{source.get('start_line', '?')}", source["text"], ""]
    lines += ["# Shared expression structures", "Same template means the same ordered syntax, not equal values."]
    for template in view.get("templates", []):
        lines.append(template["id"] + " " + json_text(template["structure"]))
    shown_entities, shown_sources = set(), set()
    for computation in view["computations"]:
        lines += ["", f"## [{computation['id']}] {computation['name']} ({computation.get('body_status', 'unknown')})"]
        for identifier in dict.fromkeys(computation["entity_ids"] + computation.get("boundary_ids", [])):
            if identifier in shown_entities:
                lines.append("Shared entity: " + identifier)
                continue
            shown_entities.add(identifier)
            entity = entities[identifier]
            if entity.get("template_id"):
                lines.append(f"[{identifier}] {entity['template_id']} bindings=" + json_text(entity.get("bindings", [])))
                if entity.get("results"):
                    lines.append("Results: " + json_text(entity["results"]))
                if entity.get("conditions"):
                    lines.append("Source conditions: " + json_text(entity["conditions"]))
                if entity.get("dispatch_evidence"):
                    lines.append("Dispatch: " + json_text(entity["dispatch_evidence"]))
                if entity.get("api_contracts"):
                    lines.append("API contracts: " + json_text(entity["api_contracts"]))
            else:
                lines.append(f"[{identifier}] {entity.get('name') or entity['kind']} " + json_text(entity.get("properties", {})))
            for source_id in entity["source_ids"]:
                if source_id in shown_sources:
                    continue
                shown_sources.add(source_id)
                source = sources[source_id]
                lines.append(f"Source [{source_id}] {source['path']}:{source.get('start_line', '?')}: {source['text']}")
    # Docstrings are not always graph objects; they are nevertheless primary
    # evidence for quantity meanings and conventions, not disposable decoration.
    for source in sources.values():
        if source["kind"] != "document" and source["id"] not in shown_sources:
            lines += [f"Source [{source['id']}] {source['path']}:{source.get('start_line', '?')}: {source['text']}"]
    lines += ["", "# Recorded relationships"]
    lines += [f"{r['source']} --{r['relation']}--> {r['target']} " + json_text(r.get("properties", {})) for r in view["relations"]]
    if view.get("observations"):
        lines += ["# Observed behaviour (not requirements)", json_text(view["observations"])]
    lines += ["# Coverage", json_text(view["coverage"])]
    return "\n".join(lines) + "\n"


def json_text(value):
    import json
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _native_nodes(tree):
    if isinstance(tree, dict):
        yield tree
        for value in tree.values():
            yield from _native_nodes(value)
    elif isinstance(tree, list):
        for value in tree:
            yield from _native_nodes(value)
