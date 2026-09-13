"""Task-local mathematical structure with shared templates and explicit bindings.

No algebraic reassociation, numerical equivalence, inferred physical laws or
candidate execution. Templates identify ordered expression structure up to
renaming quantities; each occurrence preserves its source and conditions.
"""
from __future__ import annotations

import ast
import copy
import hashlib
import json
import re
from collections import Counter, defaultdict
from textwrap import dedent
from .packet import _reproducer

VERSION = "scientific-computation-1.0"
MAX_EXPANDED_NODES = 256
OPS = {ast.Add: "add", ast.Sub: "sub", ast.Mult: "mul", ast.Div: "div",
       ast.Pow: "pow", ast.MatMult: "matmul", ast.FloorDiv: "floor_div", ast.Mod: "mod"}


def ident(prefix, value):
    return prefix + hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:24]


def size(tree):
    return 1 + sum(size(a) for a in tree.get("args", []))


def template(tree):
    slots, bindings = {}, []
    def visit(node):
        if node["op"] == "quantity":
            q = node["quantity_id"]
            if q not in slots:
                slots[q] = len(slots)
                bindings.append({"slot": slots[q], "quantity_id": q})
            return {"slot": slots[q]}
        return {**{k: v for k, v in node.items() if k != "args"},
                **({"args": [visit(a) for a in node["args"]]} if "args" in node else {})}
    return visit(tree), bindings


def family(pattern):
    op = pattern.get("op")
    def terms(n):
        return sum(terms(a) for a in n["args"]) if n.get("op") in {"add", "sub"} else int(n.get("op") == "mul")
    if op in {"add", "sub"} and terms(pattern) >= 2:
        return "sum_or_difference_of_products"
    return {"div": "ratio", "mul": "product", "pow": "power", "matmul": "matrix_product_syntax",
            "add": "sum", "sub": "difference", "neg": "negation",
            "call": "function_application", "call_or_index": "ambiguous_call_or_index",
            "select": "conditional_expression", "index": "indexed_access"}.get(op, op or "quantity_alias")


class Builder:
    def __init__(self, payload):
        self.payload = payload
        self.quantities, self.transforms, self.templates, self.edges = {}, {}, {}, {}
        self.gaps = []
        self.guards = []
        self.environments = {}
        self.body_functions = {}
        self.by_body = defaultdict(list)
        self.references = {r["id"]: r for key in ("function_bodies", "code_passages", "scientific_passages")
                           for r in payload["context"].get(key, [])}
        self.helpers = {(l["call_site"]["path"], l["call_site"]["start_line"], l["call_site"]["expression"]): l
                        for l in payload["context"].get("helper_calls", [])}
        for body in payload["context"].get("function_bodies", []):
            if body["path"].endswith(".py") and body["kind"] == "complete_function_body":
                try:
                    f = ast.parse(dedent(body["text"])).body[0]
                    if isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        self.body_functions[body["id"]] = (body, f)
                except (SyntaxError, RecursionError):
                    self.gaps.append({"source_id": body["id"], "reason": "body_parse_failure"})

    def quantity(self, body, name, line=0, column=0, binding_key=None):
        qid = ident("cq_", [body["id"], name, line, column, binding_key])
        self.quantities.setdefault(qid, {"id": qid, "symbol": name, "body_id": body["id"],
            "path": body["path"], "definition_line": line or None,
            "representation": {"units": None, "axes": None, "coordinate_frame": None}})
        return qid

    def edge(self, source, target, role, status="source_structure"):
        value = {"source": source, "target": target, "role": role, "status": status}
        self.edges[ident("ce_", value)] = value

    def leaf(self, body, name, env):
        qid = env.get(name, (self.quantity(body, name), None))[0]
        return {"op": "quantity", "quantity_id": qid}

    def expression(self, node, body, env, *, inline=False, depth=0):
        if depth > 24:
            return {"op": "unknown", "syntax": "expression_depth_limit"}
        recur = lambda n: self.expression(n, body, env, inline=inline, depth=depth + 1)
        if isinstance(node, ast.Name):
            if inline and node.id in env and env[node.id][1] is not None:
                return copy.deepcopy(env[node.id][1])
            return self.leaf(body, node.id, env)
        if isinstance(node, ast.Constant):
            return {"op": "literal", "value": repr(node.value)}
        if isinstance(node, ast.Attribute):
            return {"op": "attribute", "member": node.attr, "args": [recur(node.value)]}
        if isinstance(node, ast.Subscript):
            if isinstance(node.slice, ast.Constant):
                # A named field/element is a concrete quantity binding, not a
                # literal coefficient in the mathematical template.
                container = self.expression(node.value, body, env)
                parents = [b["quantity_id"] for b in template(container)[1]]
                qid = self.quantity(body, ast.unparse(node), binding_key=parents)
                for parent in parents:
                    self.edge(parent, qid, "element_or_field_of")
                return {"op": "quantity", "quantity_id": qid}
            return {"op": "index", "args": [recur(node.value), recur(node.slice)]}
        if isinstance(node, ast.Slice):
            return {"op": "slice", "args": [recur(n) if n else {"op": "omitted"} for n in (node.lower, node.upper, node.step)]}
        if isinstance(node, ast.BinOp):
            return {"op": OPS.get(type(node.op), type(node.op).__name__), "args": [recur(node.left), recur(node.right)]}
        if isinstance(node, ast.UnaryOp):
            return {"op": {ast.USub: "neg", ast.UAdd: "pos", ast.Not: "not"}.get(type(node.op), type(node.op).__name__), "args": [recur(node.operand)]}
        if isinstance(node, ast.Compare):
            return {"op": "compare", "operators": [type(op).__name__ for op in node.ops],
                    "args": [recur(node.left), *map(recur, node.comparators)]}
        if isinstance(node, ast.BoolOp):
            return {"op": type(node.op).__name__, "args": list(map(recur, node.values))}
        if isinstance(node, ast.IfExp):
            return {"op": "select", "args": [recur(node.test), recur(node.body), recur(node.orelse)]}
        if isinstance(node, (ast.Tuple, ast.List)):
            return {"op": type(node).__name__.lower(), "args": list(map(recur, node.elts))}
        if isinstance(node, ast.Dict):
            return {"op": "dict", "args": [{"op": "item" if k else "unpack",
                    "args": ([recur(k)] if k else []) + [recur(v)]} for k, v in zip(node.keys, node.values)]}
        if isinstance(node, ast.Call):
            # Calls retain identity and argument positions; a name is not a scientific API rule.
            return {"op": "call", "callee": ast.unparse(node.func),
                    "args": [*map(recur, node.args), *({"op": "keyword", "name": k.arg,
                                                     "args": [recur(k.value)]} for k in node.keywords)]}
        if isinstance(node, ast.Starred):
            return {"op": "unpack", "args": [recur(node.value)]}
        return {"op": "unknown", "syntax": ast.unparse(node)}

    def add(self, body, name, line, direct, expanded, env, conditions, language, source_id=None, column=0):
        if size(expanded) > MAX_EXPANDED_NODES:
            expanded = direct
            self.gaps.append({"source_id": source_id or body["id"], "line": line, "reason": "intermediate_expansion_limit"})
        pattern, bindings = template(expanded)
        # Language stays in template identity: '*' in MATLAB is not Python/Fortran '*'.
        tid = ident("ct_", [language, pattern])
        self.templates.setdefault(tid, {"id": tid, "language": language, "family": family(pattern), "pattern": pattern})
        output = self.quantity(body, name, line, column)
        uid = ident("cu_", [body["id"], line, column, name, source_id])
        inputs = template(direct)[1]
        u = {"id": uid, "body_id": body["id"], "path": body["path"], "line": line,
             "source_id": source_id or body["id"], "output": output, "template_id": tid,
             "bindings": bindings, "direct_inputs": inputs, "conditions": conditions,
             "statement_role": "return" if name.startswith("return@") else "assignment",
             "documentation": [], "resolved_intermediates": direct != expanded}
        self.transforms[uid] = u
        self.by_body[body["id"]].append(u)
        for item in inputs:
            self.edge(item["quantity_id"], uid, f"operand:{item['slot']}")
        self.edge(uid, output, "result")
        env[name] = (output, expanded if not conditions and not self.has_opaque(expanded) else None)
        if self.has_opaque(expanded):
            self.gaps.append({"source_id": u["source_id"], "line": line, "reason": "opaque_operation_or_call"})
        return u

    @staticmethod
    def has_opaque(tree):
        return tree.get("op") in {"unknown", "call", "call_or_index", "unpack"} or any(Builder.has_opaque(a) for a in tree.get("args", []))

    def python_body(self, body, f):
        env = {a.arg: (self.quantity(body, a.arg), None) for a in
               f.args.posonlyargs + f.args.args + f.args.kwonlyargs}
        offset = body["start_line"] - 1
        def block(statements, current, conditions):
            for st in statements:
                line = st.lineno + offset
                if isinstance(st, (ast.If, ast.For, ast.While, ast.AsyncFor)):
                    # Branch/loop writes must not masquerade as unconditional definitions.
                    label = ast.unparse(st.test) if isinstance(st, (ast.If, ast.While)) else f"{ast.unparse(st.target)} in {ast.unparse(st.iter)}"
                    changed = {n.id for n in ast.walk(st) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
                    if not isinstance(st, ast.If):
                        for name in changed:
                            current[name] = (self.quantity(body, name, line), None)
                    left, right = dict(current), dict(current)
                    left_ends = block(st.body, left, conditions + [{"kind": type(st).__name__, "expression": label, "arm": "body", "line": line}])
                    right_ends = block(st.orelse, right, conditions + [{"kind": type(st).__name__, "expression": label, "arm": "else", "line": line}])
                    for name in changed:
                        merged = self.quantity(body, name, -line)
                        for branch in (left, right):
                            if name in branch:
                                self.edge(branch[name][0], merged, "possible_branch_or_loop_value", "conditional_candidate")
                        current[name] = (merged, None)
                    if isinstance(st, ast.If):
                        if left_ends and right_ends:
                            return True
                        if left_ends or right_ends:
                            conditions = conditions + [{"kind": "continuation_guard", "expression": label,
                                "arm": "else" if left_ends else "body", "line": line}]
                    continue
                if isinstance(st, (ast.With, ast.Try, ast.Match, ast.AsyncWith)):
                    self.gaps.append({"source_id": body["id"], "line": line, "reason": "unsupported_control_region"})
                    for n in ast.walk(st):
                        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store):
                            current[n.id] = (self.quantity(body, n.id, -line), None)
                    continue
                if isinstance(st, ast.Raise):
                    self.guards.append({"body_id": body["id"], "line": line, "source_id": body["id"],
                        "conditions": copy.deepcopy(conditions), "action": ast.unparse(st), "status": "source_validation_not_physical_law"})
                    return True
                if isinstance(st, ast.Assert):
                    self.guards.append({"body_id": body["id"], "line": line, "source_id": body["id"],
                        "conditions": copy.deepcopy(conditions), "action": ast.unparse(st), "status": "source_assertion"})
                    conditions = conditions + [{"kind": "assertion", "expression": ast.unparse(st.test), "arm": "body", "line": line}]
                    continue
                if isinstance(st, ast.Return):
                    value, name = st.value or ast.Constant(None), f"return@{line}"
                elif isinstance(st, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                    targets = st.targets if isinstance(st, ast.Assign) else [st.target]
                    if len(targets) != 1 or st.value is None:
                        self.gaps.append({"source_id": body["id"], "line": line, "reason": "multiple_or_uninitialized_targets"})
                        continue
                    name, value = ast.unparse(targets[0]), st.value
                    if isinstance(st, ast.AugAssign):
                        value = ast.BinOp(left=targets[0], op=st.op, right=value)
                else:
                    if isinstance(st, ast.Expr) and isinstance(st.value, ast.Call):
                        for key, (q, _) in list(current.items()):
                            current[key] = (q, None)
                    continue
                direct = self.expression(value, body, current)
                expanded = self.expression(value, body, current, inline=True)
                self.add(body, name, line, direct, expanded, current, copy.deepcopy(conditions), "python", column=st.col_offset)
                if any(isinstance(n, ast.Call) for n in ast.walk(value)) or (not name.isidentifier() and not name.startswith("return@")):
                    # An indexed/attribute write can invalidate aliased earlier reads.
                    for key, (q, _) in list(current.items()):
                        current[key] = (q, None)
                if isinstance(st, ast.Return):
                    return True
            return False
        block(f.body, env, [])
        self.environments[body["id"]] = env

    def native_body(self, entries):
        first = entries[0]
        body = {"id": ident("cb_", [first["path"], first.get("function_scope") or first["scope"]]), "path": first["path"]}
        env = {}
        language = first.get("language", "native")
        normal = str.casefold if language == "fortran" else str
        def convert(n):
            if not n:
                return {"op": "unknown", "syntax": "missing_expression"}
            kind = n.get("kind")
            if kind == "name":
                return self.leaf(body, normal(n["name"]), env)
            if kind == "literal":
                return {"op": "literal", "value": n["text"]}
            if kind == "binary":
                op = {"+": "add", "-": "sub", "*": "mul", "/": "div", "**": "pow"}.get(n["operator"], n["operator"])
                return {"op": op, "args": [convert(n["left"]), convert(n["right"])]}
            if kind == "unary":
                return {"op": n["operator"], "args": [convert(n["operand"])]}
            if kind == "call":
                return {"op": "call_or_index" if n.get("index_ambiguous") else "call", "callee": n.get("callee"),
                        "args": [convert(a) for a in n.get("arguments", [])]}
            return {"op": "unknown", "syntax": n.get("text", "")}
        for entry in sorted(entries, key=lambda e: (e["start_line"], e.get("start_col", 0))):
            if entry["kind"] not in {"assignment", "return"}:
                continue
            value = entry.get("native_expression")
            for lost in entry.get("native", {}).get("omitted_prior_bindings", []):
                env.pop(normal(lost), None)
            name = normal((entry.get("entity_symbols") or [f"return@{entry['start_line']}"])[0])
            if entry["kind"] == "return":
                name = f"return@{entry['start_line']}"
            direct = convert(value)
            self.add(body, name, entry["start_line"], direct, direct, env, entry.get("branch", []), language, entry["id"], entry.get("start_col",0))
            if entry.get("branch"):
                env.pop(name, None)
        self.environments[body["id"]] = env

    def python_entries(self, entries):
        """Use archived/indexed expressions when a complete body is unavailable."""
        first = entries[0]
        body = {"id": ident("cb_", [first["path"], first["scope"]]), "path": first["path"]}
        env = {}
        for e in sorted(entries, key=lambda e: (e["start_line"], e.get("start_col", 0))):
            if e.get("kind") not in {"assignment", "augmented_assignment", "return"}:
                continue
            try:
                node = ast.parse(e.get("expression_text") or "", mode="eval").body
            except (SyntaxError, RecursionError):
                self.gaps.append({"source_id": e["id"], "reason": "indexed_expression_unavailable"})
                continue
            name = (e.get("targets") or e.get("entity_symbols") or [f"return@{e['start_line']}"])[0]
            if e["kind"] == "return":
                name = f"return@{e['start_line']}"
            if e["kind"] == "augmented_assignment":
                # Existing indexed expression stores only the RHS, not the update operator.
                self.gaps.append({"source_id": e["id"], "reason": "indexed_update_operator_unavailable"})
                env.pop(name, None)
                continue
            for dependency in e.get("local_dependencies", []):
                if dependency.get("status") == "unresolved" and dependency["name"] in env:
                    env.pop(dependency["name"])
            direct = self.expression(node, body, env)
            expanded = self.expression(node, body, env, inline=True)
            self.add(body, name, e["start_line"], direct, expanded, env, e.get("branch", []), "python", e["id"], e.get("start_col",0))
            if e.get("branch"):
                env.pop(name, None)
            if any(isinstance(n, ast.Call) for n in ast.walk(node)) or (not name.isidentifier() and not name.startswith("return@")):
                env = {key: (q, None) for key, (q, _) in env.items()}
        self.environments[body["id"]] = env

    def connect_helpers(self):
        for link in self.payload["context"].get("helper_calls", []):
            caller, callee = link["caller_body_id"], link["callee_body_id"]
            if caller not in self.body_functions or callee not in self.body_functions:
                continue
            caller_body = self.body_functions[caller][0]
            line = link["call_site"]["start_line"]
            for binding in link.get("argument_bindings", []):
                if binding["origin"] != "caller":
                    continue
                try:
                    names = {n.id for n in ast.walk(ast.parse(binding["expression"], mode="eval")) if isinstance(n, ast.Name)}
                except SyntaxError:
                    continue
                target = self.quantity(self.body_functions[callee][0], binding["parameter"])
                for name in names:
                    earlier = [u for u in self.by_body[caller] if u["line"] < line and self.quantities[u["output"]]["symbol"] == name]
                    source = max(earlier, key=lambda u: u["line"])["output"] if earlier and not any(u["conditions"] for u in earlier) else self.quantity(caller_body, name)
                    self.edge(source, target, f"argument:{binding['parameter']}", "static_call_candidate")
            for result in [u for u in self.by_body[caller] if u["line"] == line]:
                for returned in [u for u in self.by_body[callee] if u["statement_role"] == "return"]:
                    self.edge(returned["output"], result["id"], "returned_value", "static_call_candidate")

    def build(self):
        for body, function in self.body_functions.values():
            self.python_body(body, function)
        native, indexed_python = defaultdict(list), defaultdict(list)
        for entry in self.payload["context"].get("code_passages", []):
            if entry.get("native_expression") is not None:
                native[(entry["path"], entry.get("function_scope") or entry["scope"])].append(entry)
            elif entry["path"].endswith(".py") and not any(b["path"] == entry["path"] and
                    b["start_line"] <= entry["start_line"] <= b["end_line"] for b, _ in self.body_functions.values()):
                indexed_python[(entry["path"], entry["scope"])].append(entry)
        for group in native.values():
            self.native_body(group)
        for group in indexed_python.values():
            self.python_entries(group)
        self.connect_helpers()
        docs = self.payload["context"].get("scientific_passages", [])
        for u in self.transforms.values():
            symbols = {self.quantities[b["quantity_id"]]["symbol"] for b in u["bindings"]}
            symbols.add(self.quantities[u["output"]]["symbol"])
            for doc in docs:
                matches = sorted(s for s in symbols if s.isidentifier() and len(s) > 2 and re.search(r"\b" + re.escape(s) + r"\b", doc["quote"]))
                if matches:
                    u["documentation"].append({"source_id": doc["id"], "symbols": matches, "status": "symbol_reference_not_proven_meaning"})
        patterns = Counter(u["template_id"] for u in self.transforms.values())
        used_quantities = {e[k] for e in self.edges.values() for k in ("source", "target")}
        used_quantities.update(b["quantity_id"] for u in self.transforms.values() for b in u["bindings"])
        quantities = [q for q in self.quantities.values() if q["id"] in used_quantities]
        arithmetic = {"add", "sub", "mul", "div", "pow", "matmul", ".*", "./", "^", ".^"}
        def has_arithmetic(p):
            return p.get("op") in arithmetic or any(has_arithmetic(a) for a in p.get("args", []))
        condition_sets = {}
        for u in self.transforms.values():
            conditions = u.pop("conditions")
            cid = ident("cc_", [u["body_id"], conditions])
            condition_sets.setdefault(cid, {"id": cid, "body_id": u["body_id"], "conditions": conditions})
            u["condition_set_id"] = cid
        return {"schema_version": VERSION, "templates": list(self.templates.values()),
                "quantities": quantities, "transformations": list(self.transforms.values()),
                "condition_sets": list(condition_sets.values()),
                "links": list(self.edges.values()), "guards": self.guards, "gaps": self.gaps,
                "coverage": {"transformations": len(self.transforms), "unique_templates": len(patterns),
                             "shared_templates": sum(n > 1 for n in patterns.values()),
                             "instances_in_shared_templates": sum(n for n in patterns.values() if n > 1),
                             "arithmetic_transformations": sum(has_arithmetic(self.templates[u["template_id"]]["pattern"]) for u in self.transforms.values()),
                             "non_reproducer_arithmetic_transformations": sum(not _reproducer(u["path"]) and has_arithmetic(self.templates[u["template_id"]]["pattern"]) for u in self.transforms.values()),
                             "languages": sorted({t["language"] for t in self.templates.values()})},
                "scope": "Ordered syntax and source-backed dependencies; no physical meaning or runtime equivalence inferred."}


def build_computation(payload):
    return Builder(payload).build()


def conditions_for(model, unit):
    return next(c["conditions"] for c in model["condition_sets"] if c["id"] == unit["condition_set_id"])


def computation_input(payload):
    """Interpret the shared representation; retain evidence without duplicate indexes."""
    model = build_computation(payload)
    if not model["transformations"]:
        payload["computation"] = model
        return payload
    objects = [{k: o[k] for k in ("id", "kind", "symbol", "path", "source_span")}
               for o in attach_computation({"objects": []}, model)["objects"]]
    required_entries = {u["source_id"] for u in model["transformations"]}
    context = copy.deepcopy(payload["context"])
    context["code_passages"] = [{k: e[k] for k in ("id", "path", "scope", "start_line", "end_line", "sha256", "text", "language") if k in e}
                                for e in context.get("code_passages", []) if e["id"] in required_entries]
    # Legacy API contracts remain available as evidence without becoming a
    # second set of arbitrary annotation targets.
    context["api_contract_operations"] = [o for o in payload.get("operations", []) if o.get("api")]
    return {"objects": objects, "operations": [], "links": [], "unsupported": model["gaps"],
            "computation": model, "context": context,
            "evidence_packets": [{k: p[k] for k in ("id", "anchor", "function_body_ids", "document_ids", "gaps", "claim_scope") if k in p}
                                 for p in payload.get("evidence_packets", [])],
            "selection": {"strategy": "shared_computational_templates", "source_selection": payload.get("selection", {}),
                          "annotation_targets": len(objects), "note": "Original graph remains in the extraction artifact; representation owns computational links."}}


def attach_computation(graph, model):
    result = copy.deepcopy(graph)
    result["computation"] = copy.deepcopy(model)
    templates = {t["id"]: t for t in model["templates"]}
    quantities = {q["id"]: q for q in model["quantities"]}
    existing = {o["id"] for o in result["objects"]}
    for u in model["transformations"]:
        if u["id"] in existing:
            continue
        result["objects"].append({"id": u["id"], "kind": "computational_relation",
            "symbol": quantities[u["output"]]["symbol"], "path": u["path"], "scope": u["body_id"],
            "source_entry_ids": [u["source_id"]], "source_span": {"start_line": u["line"], "end_line": u["line"]},
            "roles": [templates[u["template_id"]]["family"]], "properties": {
                "template_id": u["template_id"], "bindings": u["bindings"], "conditions": conditions_for(model, u),
                "documentation": u["documentation"], "scientific_semantics": "requires_source_interpretation"}})
    return result


def render_computation(graph):
    """One display per shared template, with bindings and conditions per occurrence."""
    model = graph["computation"]
    quantities = {q["id"]: q for q in model["quantities"]}
    objects = {o["id"]: o for o in graph["objects"]}
    templates = {t["id"]: t for t in model["templates"]}
    groups = defaultdict(list)
    for unit in model["transformations"]:
        groups[unit["template_id"]].append(unit)
    def formula(p):
        if "slot" in p:
            return f"v{p['slot']}"
        args = [formula(a) for a in p.get("args", [])]
        if p["op"] == "literal":
            return p["value"]
        symbols = {"add": "+", "sub": "-", "mul": "*", "div": "/", "pow": "**", "matmul": "@"}
        if p["op"] in symbols:
            return f"({args[0]} {symbols[p['op']]} {args[1]})"
        if p["op"] == "attribute":
            return args[0] + "." + p["member"]
        if p["op"] == "index":
            return args[0] + "[" + args[1] + "]"
        return p.get("callee", p["op"]) + "(" + ", ".join(args) + ")"
    # Prefer interpreted computations and repeated arithmetic, not workflow wrappers.
    ordered = sorted(groups, key=lambda tid: (
        not any(objects.get(u["id"], {}).get("interpretation") for u in groups[tid]),
        templates[tid]["family"] in {"function_application", "dict", "quantity_alias", "literal"},
        -len(groups[tid]), tid))
    lines = ["# Scientific computation", "", "Shared mathematical forms with concrete quantity bindings. "
             "Full dependencies, conditions and source evidence: scientific-graph.json and scientific-sources.json.", ""]
    used, limit = 0, 16000
    for tid in ordered:
        pattern = templates[tid]
        expression = formula(pattern["pattern"])
        section = [f"## {pattern['family']} — {tid}", f"`{expression}`", ""]
        common_conditions = [c for c in conditions_for(model, groups[tid][0]) if all(c in conditions_for(model, u) for u in groups[tid])]
        if common_conditions:
            section.append("Shared conditions: " + json.dumps(common_conditions, ensure_ascii=False))
        for u in groups[tid]:
            bindings = ", ".join(f"v{b['slot']}={quantities[b['quantity_id']]['symbol']}" for b in u["bindings"])
            section += [f"- {u['id']}: {quantities[u['output']]['symbol']} ← {bindings}",
                        f"  Source: {u['path']}:{u['line']}"]
            remaining_conditions = [c for c in conditions_for(model, u) if c not in common_conditions]
            if remaining_conditions:
                section.append("  Conditions: " + json.dumps(remaining_conditions, ensure_ascii=False))
            meaning = objects.get(u["id"], {}).get("interpretation", {})
            if meaning.get("meaning"):
                section.append("  Meaning: " + meaning["meaning"])
            for field in ("conventions", "assumptions"):
                for statement in meaning.get(field, []):
                    section.append(f"  {field}: {statement}")
        text = "\n".join(section)
        if used + len(text) > limit:
            continue  # Whole groups remain in durable graph, never cut a condition off its occurrence.
        lines.extend(section + [""])
        used += len(text)
    lines += ["Additional groups and unsupported cases remain in the durable graph. "
              "Structural correspondence does not establish numerical equivalence or a physical law."]
    return "\n".join(lines) + "\n"
