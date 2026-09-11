"""Small code-first scientific object graph, without importing candidate code.

Rules describe documented API contracts, not a recovered specification or proof
that the candidate satisfies them. Domain labels are deliberately left to the
separate interpretation step. Source identity and conservative local bindings
come from the existing evidence packet; unresolved edges are never name-matched.
"""

from __future__ import annotations

import ast
import copy
import hashlib
import json
from fractions import Fraction
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

from . import evidence


SCHEMA_VERSION = "scientific-objects-1.0"
_DOCS = {
    "numpy.linalg.solve": "https://numpy.org/doc/stable/reference/generated/numpy.linalg.solve.html",
    "scipy.integrate.trapezoid": "https://docs.scipy.org/doc/scipy/reference/generated/scipy.integrate.trapezoid.html",
    "networkx.Graph": "https://networkx.org/documentation/stable/reference/classes/graph.html",
    "networkx.DiGraph": "https://networkx.org/documentation/stable/reference/classes/digraph.html",
    "networkx.connected_components": "https://networkx.org/documentation/stable/reference/algorithms/generated/networkx.algorithms.components.connected_components.html",
    "astropy.units.Quantity": "https://docs.astropy.org/en/stable/api/astropy.units.Quantity.html",
}
_ALIASES = {
    "networkx.classes.graph.Graph": "networkx.Graph",
    "networkx.classes.digraph.DiGraph": "networkx.DiGraph",
    "networkx.algorithms.components.connected_components": "networkx.connected_components",
    "networkx.algorithms.components.connected.connected_components": "networkx.connected_components",
    "astropy.units.quantity.Quantity": "astropy.units.Quantity",
}
@lru_cache(maxsize=1)
def _unit_registry():
    from pint import UnitRegistry
    return UnitRegistry(non_int_type=Decimal)


def _serial_dimension(value):
    rational = Fraction(value)
    return rational.numerator if rational.denominator == 1 else str(rational)


@lru_cache(maxsize=256)
def _unit_basis(text):
    """Read Pint's offline registry; only propagate multiplicative unit scales.

    Registry-defined constants are not mathematical exactness guarantees. Offset,
    logarithmic, custom or unrecognised units remain explicit unsupported cases.
    """
    from pint.errors import PintError
    try:
        registry = _unit_registry()
        unit = registry.parse_units(text)
        zero = registry.Quantity(Decimal(0), unit).to_base_units().magnitude
        one = registry.Quantity(Decimal(1), unit).to_base_units().magnitude
        two = registry.Quantity(Decimal(2), unit).to_base_units().magnitude
        if zero != 0 or one <= 0 or two != 2 * one:
            return None
        aliases = {"current": "electric_current", "substance": "amount", "luminosity": "luminous_intensity"}
        dims = {aliases.get(str(key).strip("[]"), str(key).strip("[]")): _serial_dimension(value)
                for key, value in unit.dimensionality.items() if value}
        return dims, str(Fraction(one))
    except (PintError, ValueError, TypeError, ArithmeticError):
        return None


def _id(prefix, *parts):
    return prefix + hashlib.sha256(json.dumps(parts, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:24]


def _literal(node):
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError):
        return None


def _shape(value):
    if isinstance(value, (int, float, complex, bool)):
        return []
    if isinstance(value, (list, tuple)):
        shapes = [_shape(item) for item in value]
        return [len(value), *(shapes[0] or [])] if shapes and shapes[0] is not None and all(s == shapes[0] for s in shapes) else [0] if not value else None
    return None


def _json_literal(value):
    if isinstance(value, dict) and any(not isinstance(key, str) for key in value):
        return None  # JSON must not silently turn integer keys into strings.
    try:
        return json.loads(json.dumps(value, allow_nan=False))
    except (ValueError, TypeError, OverflowError):
        return None


def _name(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _name(node.value)
        return base + "." + node.attr if base else None
    return None


class _Extractor:
    def __init__(self, root, packet):
        self.entries, self.objects, self.operations, self.links = {}, {}, {}, []
        self.unsupported, self.done, self.active = [], {}, set()
        self.scientific = set()
        self.sources, self.scope_indexes, self.inspected_calls = {}, {}, {}
        self.coverage = {"input_entries": len(packet.get("entries", [])), "valid_source_entries": 0,
                         "recognized_scientific_operations": 0, "rule_families": [],
                         "packet_truncation": {k: packet.get("coverage", {}).get(k) for k in
                                               ("files_truncated", "entries_truncated", "scan_files_truncated")},
                         "source_files": [], "limitations": [
            "Finite API rules and packet-local dataflow; absence is not scientific irrelevance.",
            "Contracts and inferred shapes/units are conditional on documented library semantics, not runtime proofs.",
            "Wrapper links identify lexical function bodies only: no argument substitution, return-value equivalence, cross-file linking or runtime call proof.",
            "Runtime monkey-patching, mutation analysis and domain meaning inferred from names are not modelled.",
            "Graph topology is constructor evidence only; later mutations and execution are not established."]}
        digests = {}
        for entry in packet.get("entries", []):
            path = entry.get("path")
            if path not in digests:
                _, problem = evidence._safe_file(root, path)
                try:
                    if problem:
                        digests[path] = None
                    else:
                        raw = evidence._read_regular(root, path)
                        digests[path] = hashlib.sha256(raw).hexdigest()
                        self.sources[path] = raw
                except (OSError, ValueError):
                    digests[path] = None
            if digests[path] is None or digests[path] != entry.get("sha256"):
                self.problem(entry, "stale_or_unreadable_source")
            else:
                self.entries[entry["id"]] = entry
        self.coverage["valid_source_entries"] = len(self.entries)
        self.coverage["source_files"] = sorted({e["path"] for e in self.entries.values()})

    def problem(self, entry, reason, **details):
        item = {"source_entry_id": entry.get("id"), "path": entry.get("path"), "reason": reason, **details}
        if item not in self.unsupported:
            self.unsupported.append(item)

    def obj(self, entry, tag, *, symbol=None, kind="computational_value", properties=None):
        key = _id("so_", entry["id"], tag)
        if key not in self.objects:
            self.objects[key] = {"id": key, "kind": kind, "symbol": symbol,
                "scope": entry["scope"], "path": entry["path"], "source_entry_ids": [entry["id"]],
                "source_span": {k: entry[k] for k in ("start_line", "end_line")},
                "properties": {"dimensions": None, "scale_to_si": None, "shape": None,
                               "source_branch": entry.get("branch", []),
                               **(properties or {})}, "roles": []}
        return key

    def role(self, oid, role):
        if oid and role not in self.objects[oid]["roles"]:
            self.objects[oid]["roles"].append(role)

    def link(self, source, target, relation):
        item = {"source": source, "target": target, "relation": relation}
        if source and target and item not in self.links:
            self.links.append(item)

    def operation(self, entry, node, kind, api, inputs, output, properties=None, assumptions=None, scientific=False, identity=None):
        key = _id("sop_", entry["id"], identity if identity is not None else ast.dump(node, include_attributes=True), kind)
        self.operations[key] = {"id": key, "kind": kind, "api": api,
            "source_entry_id": entry["id"], "inputs": [{"role": r, "object_id": o} for r, o in inputs],
            "source": {k: entry[k] for k in ("path", "scope", "start_line", "end_line")},
            "output_ids": [output] if output else [], "properties": {"source_branch": entry.get("branch", []), **(properties or {})},
            "assumptions": ["Standard documented library/operator behaviour; runtime overrides are not checked.", *(assumptions or [])],
            "documentation_url": _DOCS.get(api)}
        expression_span = entry.get("expression_span")
        if expression_span and isinstance(node, ast.Call):
            self.operations[key]["call_site"] = {
                "start_line": expression_span["start_line"] + node.lineno - 1,
                "start_col": node.col_offset + (expression_span["start_col"] if node.lineno == 1 else 0)}
        for role, oid in inputs:
            self.role(oid, role)
            self.link(oid, key, "input:" + role)
        self.link(key, output, "produces")
        if scientific:
            self.scientific.add(key)
            self.coverage["recognized_scientific_operations"] += 1
            if kind not in self.coverage["rule_families"]:
                self.coverage["rule_families"].append(kind)
        return output

    def canonical(self, entry, node):
        name = _name(node)
        if not name:
            return None
        base, *tail = name.split(".")
        imported = entry.get("imports", {}).get(base)
        if not imported:
            return None
        resolved = ".".join([imported, *tail])
        return _ALIASES.get(resolved, resolved)

    def source_scope(self, entry):
        """Reuse the existing scope index to disambiguate omitted definitions."""
        path = entry["path"]
        if path not in self.scope_indexes:
            try:
                tree = ast.parse(self.sources[path], filename=path)
                index = evidence._ScopeIndex(tree)
                scopes = {scope.name: scope for scope in index.scopes.values()}
                functions = {index.scopes[id(node)].name: node for node in ast.walk(tree)
                             if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and id(node) in index.scopes}
                self.scope_indexes[path] = scopes, functions
            except (SyntaxError, ValueError, UnicodeError, RecursionError):
                self.scope_indexes[path] = {}, {}
        scopes, functions = self.scope_indexes[path]
        return scopes.get(entry["scope"]), functions

    def binding(self, entry, name):
        dep = next((d for d in entry.get("local_dependencies", []) if d["name"] == name), None)
        if dep and dep.get("definition_id") in self.entries:
            return self.statement(self.entries[dep["definition_id"]])
        if dep and dep.get("scope") == entry["scope"] and dep.get("reason") == "parameter_alias_or_unindexed_definition":
            params = [e for e in self.entries.values() if e["path"] == entry["path"] and e["scope"] == entry["scope"]
                      and e["kind"] == "parameter" and e.get("entity_symbols") == [name]]
            if len(params) == 1:
                scope, functions = self.source_scope(entry)
                function = functions.get(entry["scope"])
                prior = [b for b in scope.bindings.get(name, []) if b.line < entry["start_line"]] if scope else []
                if function and len(prior) == 1 and prior[0].line == function.lineno and not prior[0].branch and not scope.is_dynamic():
                    return self.statement(params[0])
        self.problem(entry, "unresolved_dataflow", symbol=name, binding_reason=dep.get("reason") if dep else "not_indexed")
        return None

    def wrapper(self, entry, node):
        result = {"status": "unresolved", "function": _name(node.func), "path": None,
                  "source_entry_id": None, "body_scope": None,
                  "reason": "attribute_or_imported_target_not_resolved"}
        if not isinstance(node.func, ast.Name):
            return result
        scope, functions = self.source_scope(entry)
        if not scope:
            result["reason"] = "source_scope_unavailable"
            return result
        owner, bindings = scope.lookup(node.func.id)
        if not owner or len(bindings) != 1 or scope.is_dynamic() or bindings[0].branch or bindings[0].imported:
            result["reason"] = "missing_rebound_branch_or_external_binding"
            return result
        binding = bindings[0]
        if owner is scope and binding.line >= entry["start_line"]:
            result["reason"] = "definition_not_before_local_call"
            return result
        body_scope = f"{owner.name}.{node.func.id}@{binding.line}"
        function = functions.get(body_scope)
        if function is None or function.decorator_list:
            result["reason"] = "not_a_function_or_decorated_callable"
            return result
        signatures = [e for e in self.entries.values() if e["path"] == entry["path"] and
                      e["scope"] == body_scope and e["kind"] == "signature"]
        if len(signatures) != 1:
            result["reason"] = "function_signature_not_in_packet"
            return result
        return {"status": "lexical_target_only", "function": function.name, "path": entry["path"],
                "source_entry_id": signatures[0]["id"], "body_scope": body_scope,
                "reason": None, "runtime_invocation": "not_established",
                "argument_and_return_equivalence": "not_derived"}

    def statement(self, entry):
        key = entry["id"]
        if key in self.done:
            return self.done[key]
        if key in self.active:
            self.problem(entry, "cyclic_dataflow")
            return None
        self.active.add(key)
        symbols = entry.get("entity_symbols", [])
        output = None
        if entry["kind"] == "signature":
            output = self.obj(entry, "interface", kind="code_interface",
                              properties={"signature": entry["text"], "runtime_type": "not_inferred"})
        elif entry["kind"] == "parameter":
            output = self.obj(entry, "binding", symbol=symbols[0], properties={"binding": "parameter", "runtime_type": "unknown"})
        elif entry.get("expression_text") is not None and entry["kind"] in {"assignment", "return", "augmented_assignment", "call", "comparison", "assertion"}:
            try:
                node = ast.parse(entry["expression_text"], mode="eval").body
            except (SyntaxError, ValueError, RecursionError):
                self.problem(entry, "expression_parse_failure")
            else:
                if entry["kind"] == "augmented_assignment" or (entry["kind"] == "assignment" and
                        (len(entry.get("targets", [])) != 1 or not entry["targets"][0].isidentifier())):
                    self.problem(entry, "unsupported_assignment_binding")
                    # Keep the actual statement as an interpretation anchor,
                    # but return no binding: unpacked/mutated targets are not
                    # interchangeable with the whole RHS value.
                    self.obj(entry, "statement", kind="source_statement", properties={
                        "source_expression": entry["expression_text"], "targets": entry.get("targets", []),
                        "binding": "not_resolved", "scientific_semantics": "unknown"})
                else:
                    value = self.value(entry, node)
                    output = self.obj(entry, "binding", symbol=symbols[0] if symbols else None,
                        kind=self.objects[value]["kind"] if value else "computational_value",
                        properties=copy.deepcopy(self.objects[value]["properties"]) if value else {"binding": "unresolved"})
                    self.link(value, output, "returned_as" if entry["kind"] == "return" else "bound_as")
        self.active.remove(key)
        self.done[key] = output
        return output

    def value(self, entry, node):
        tag = ast.dump(node, include_attributes=True)
        if isinstance(node, ast.Name):
            return self.binding(entry, node.id)
        if isinstance(node, (ast.Constant, ast.List, ast.Tuple, ast.Dict, ast.UnaryOp)):
            literal = _literal(node)
            if literal is not None or isinstance(node, ast.Constant) and node.value is None:
                properties = {"shape": _shape(literal), "literal": _json_literal(literal),
                              "literal_python_type": type(literal).__name__}
                return self.obj(entry, tag, kind="literal", properties=properties)
        if isinstance(node, ast.Call):
            return self.call(entry, node)
        if isinstance(node, ast.Compare):
            output = self.obj(entry, tag, kind="source_predicate", properties={"runtime_type": "not_inferred"})
            return self.operation(entry, node, "source_comparison", None,
                [("left_operand", self.value(entry, node.left))] +
                [(f"comparator_{i}", self.value(entry, value)) for i, value in enumerate(node.comparators)], output,
                {"operators": [type(op).__name__ for op in node.ops], "expression": ast.unparse(node),
                 "scientific_semantics": "unknown"},
                ["Source condition only; overloaded comparison behavior and intended scientific validity are not established."])
        if isinstance(node, ast.BinOp):
            left, right = self.value(entry, node.left), self.value(entry, node.right)
            quantity = any(o and self.objects[o]["kind"] == "quantity" for o in (left, right))
            props = self.quantity_arithmetic(entry, node, left, right) if quantity else {}
            output = self.obj(entry, tag, kind="quantity" if quantity else "computational_value", properties=props)
            return self.operation(entry, node, "quantity_arithmetic" if quantity else "arithmetic",
                "astropy.units.Quantity" if quantity else None, [("left_operand", left), ("right_operand", right)],
                output, {"operator": type(node.op).__name__}, scientific=quantity)
        self.problem(entry, "unsupported_expression", expression=ast.unparse(node)[:240])
        return None

    def quantity_arithmetic(self, entry, node, left, right):
        if not left or not right:
            return {}
        a, b = (self.objects[o] for o in (left, right))
        pa, pb = a["properties"], b["properties"]
        da, db = pa.get("dimensions"), pb.get("dimensions")
        sa, sb = pa.get("scale_to_si"), pb.get("scale_to_si")
        # Bare numeric scalar/array values carry a dimensionless multiplicative
        # unit basis, not an assertion that arbitrary external data are unitless.
        if a["kind"] == "literal" and pa.get("shape") is not None:
            da, sa = {}, "1"
        if b["kind"] == "literal" and pb.get("shape") is not None:
            db, sb = {}, "1"
        props = {"dimensions": None, "scale_to_si": None, "shape": None}
        if da is None or db is None or sa is None or sb is None:
            self.problem(entry, "quantity_operand_units_unknown")
            return props
        if isinstance(node.op, (ast.Mult, ast.Div)):
            sign = -1 if isinstance(node.op, ast.Div) else 1
            dims = {k: Fraction(v) for k, v in da.items()}
            for k, v in db.items():
                dims[k] = dims.get(k, 0) + sign * Fraction(v)
            props.update(dimensions={k: _serial_dimension(v) for k, v in dims.items() if v},
                         scale_to_si=str(Fraction(sa) * Fraction(sb) ** sign))
        elif isinstance(node.op, (ast.Add, ast.Sub)):
            if a["kind"] != "quantity" or b["kind"] != "quantity":
                self.problem(entry, "quantity_addition_with_bare_value_not_propagated")
                return props
            if da == db:
                props.update(dimensions=dict(da), scale_to_si=sa,
                             right_to_left_unit_factor=str(Fraction(sb) / Fraction(sa)))
            else:
                props["dimensional_conflict"] = True
                self.problem(entry, "incompatible_quantity_addition", left_dimensions=da, right_dimensions=db)
        else:
            self.problem(entry, "unsupported_quantity_operator", operator=type(node.op).__name__)
        return props

    def arguments(self, entry, node, names, *, allowed=()):
        if len(node.args) > len(names) or any(isinstance(a, ast.Starred) for a in node.args) or any(k.arg is None for k in node.keywords):
            self.problem(entry, "unsupported_call_arguments")
            return None
        args = dict(zip(names, node.args))
        for keyword in node.keywords:
            if keyword.arg in args or keyword.arg not in {*names, *allowed}:
                self.problem(entry, "unsupported_call_keyword", keyword=keyword.arg)
                return None
            args[keyword.arg] = keyword.value
        return args

    def missing(self, entry, args, required):
        if args is None:
            return True
        missing = sorted(set(required) - args.keys())
        if missing:
            self.problem(entry, "missing_required_arguments", arguments=missing)
        return bool(missing)

    def call(self, entry, node):
        api = self.canonical(entry, node.func)
        tag = ast.dump(node, include_attributes=True)
        self.inspected_calls.setdefault(entry["path"], set()).add((entry["id"], tag))
        if api == "numpy.linalg.solve":
            args = self.arguments(entry, node, ["a", "b"])
            if self.missing(entry, args, ["a", "b"]):
                return None
            a, b = self.value(entry, args["a"]), self.value(entry, args["b"])
            output = self.obj(entry, tag, kind="linear_system_solution")
            props = {"relation": "A @ x = b", "coefficient_role": "coefficient_operator", "status": "API_contract_not_verified"}
            if a and (shape := self.objects[a]["properties"].get("shape")) is not None:
                props["coefficient_square_from_literal_shape"] = len(shape) >= 2 and shape[-1] == shape[-2]
            return self.operation(entry, node, "linear_solve", api, [("coefficient_operator", a), ("right_hand_side", b)], output, props,
                                  ["Coefficient array is square and full rank; rank is not inferred from shape."], True)
        if api == "scipy.integrate.trapezoid":
            args = self.arguments(entry, node, ["y", "x", "dx", "axis"])
            if self.missing(entry, args, ["y"]):
                return None
            y = self.value(entry, args["y"])
            # Both arguments are evaluated by Python. Dynamic x must retain dx
            # as a conditional scientific input, including its nested producer.
            xnode = args.get("x")
            coordinate = self.value(entry, xnode) if xnode is not None else None
            xobj = self.objects.get(coordinate)
            uniform = xnode is None or xobj is not None and xobj["kind"] == "literal" and xobj["properties"].get("literal_python_type") == "NoneType"
            explicit = xobj is not None and (xobj["kind"] in {"array", "quantity", "graph", "linear_system_solution", "integral"}
                       or xobj["kind"] == "literal" and xobj["properties"].get("literal_python_type") != "NoneType")
            dxnode = args.get("dx", ast.Constant(value=1.0))
            spacing = self.value(entry, dxnode) if not explicit or "dx" in args else None
            props = {"axis": _literal(args["axis"]) if "axis" in args else -1,
                     "axis_expression": ast.unparse(args["axis"]) if "axis" in args else "-1",
                     "coordinates_sorted": False, "x_takes_precedence_over_dx": True,
                     "coordinate_mode": "uniform_spacing" if uniform else "explicit_coordinates" if explicit else "conditional_x_or_spacing",
                     "input_applicability": {"integration_coordinates": "x is not None", "sample_spacing": "x is None"},
                     "dx_ignored_if_x_not_none": "dx" in args and not uniform}
            output = self.obj(entry, tag, kind="integral")
            inputs = [("sampled_field", y), ("integration_coordinates", None if uniform else coordinate),
                      ("sample_spacing", None if explicit else spacing)]
            if explicit and spacing:
                inputs.append(("evaluated_but_ignored_spacing", spacing))
            return self.operation(entry, node, "sampled_integration", api,
                inputs, output, props,
                ["Integrates in supplied coordinate order, not sorted order.", "Dynamic x may be None; then dx applies."], True)
        if api in {"networkx.Graph", "networkx.DiGraph"}:
            args = self.arguments(entry, node, ["incoming_graph_data"], allowed={"name"})
            if args is None:
                return None
            source = args.get("incoming_graph_data")
            topology = _literal(source) if source is not None else []
            edges = None
            if isinstance(topology, (list, tuple)) and all(isinstance(e, (list, tuple)) and len(e) == 2
                    and all(isinstance(v, (str, int, float, bool)) for v in e) for e in topology):
                edges = [list(e) for e in topology]
            if edges is None:
                self.problem(entry, "graph_topology_not_literal_edge_pairs")
            props = {"directed": api == "networkx.DiGraph", "multigraph": False,
                     "topology": {"status": "constructor_evidence_only", "edges": edges,
                                  "later_mutation": "not_modelled"}}
            output = self.obj(entry, tag, kind="graph", properties=props)
            return self.operation(entry, node, "graph_construction", api,
                [("incoming_graph_data", self.value(entry, source))] if source is not None else [], output, props, scientific=True)
        if api == "networkx.connected_components":
            args = self.arguments(entry, node, ["G"])
            if self.missing(entry, args, ["G"]):
                return None
            graph = self.value(entry, args["G"])
            directed = self.objects[graph]["properties"].get("directed") if graph else None
            props = {"partition_of": graph, "output_form": "generator_of_node_sets",
                     "requires_undirected": True, "directedness_conflict": directed is True}
            if directed is True:
                self.problem(entry, "connected_components_requires_undirected_graph")
            output = self.obj(entry, tag, kind="component_partition", properties=props)
            return self.operation(entry, node, "connected_component_partition", api, [("graph_topology", graph)], output, props,
                                  ["Graph must be undirected; dynamic input type is not established."], True)
        if api == "astropy.units.Quantity":
            args = self.arguments(entry, node, ["value", "unit"], allowed={"dtype", "copy", "order", "subok", "ndmin"})
            if self.missing(entry, args, ["value"]):
                return None
            value = self.value(entry, args["value"])
            unitnode = args.get("unit")
            unit = _literal(unitnode) if unitnode is not None else None
            canonical = self.canonical(entry, unitnode) if unitnode is not None else None
            if canonical and canonical.startswith("astropy.units."):
                unit = canonical.removeprefix("astropy.units.")
            basis = _unit_basis(unit) if isinstance(unit, str) else None
            props = {"unit_expression": ast.unparse(unitnode) if unitnode is not None else None,
                     "unit_literal": unit if isinstance(unit, str) else None,
                     "dimensions": dict(basis[0]) if basis else None, "scale_to_si": basis[1] if basis else None,
                     "unit_basis_source": "pint_registry_multiplicative_scale" if basis else "unknown",
                     "shape": self.objects[value]["properties"].get("shape") if value and "ndmin" not in args and "dtype" not in args else None}
            if not basis:
                self.problem(entry, "unsupported_or_implicit_quantity_unit", unit_expression=props["unit_expression"])
            output = self.obj(entry, tag, kind="quantity", properties=props)
            return self.operation(entry, node, "quantity_construction", api, [("numeric_value", value)], output, props, scientific=True)
        if api in {"numpy.array", "numpy.asarray"}:
            first = "object" if api == "numpy.array" else "a"
            args = self.arguments(entry, node, [first, "dtype"], allowed={"order", "copy", "ndmin", "like"})
            if self.missing(entry, args, [first]):
                return None
            value = self.value(entry, args[first])
            shape = self.objects[value]["properties"].get("shape") if value else None
            if {"ndmin", "like", "dtype"} & args.keys():
                shape = None
            output = self.obj(entry, tag, kind="array", properties={"shape": shape})
            return self.operation(entry, node, "array_construction", api, [("values", value)], output)
        wrapper = self.wrapper(entry, node)
        self.problem(entry, "uninterpreted_wrapper_call" if wrapper["status"] == "lexical_target_only" else "unrecognized_or_shadowed_call",
                     expression=ast.unparse(node.func), resolved_api=api, wrapper=wrapper)
        inputs = [(f"argument_{i}", self.value(entry, a)) for i, a in enumerate(node.args)]
        if wrapper.get("source_entry_id") in self.entries:
            inputs.insert(0, ("callee_interface", self.statement(self.entries[wrapper["source_entry_id"]])))
        inputs.extend(("keyword:" + (k.arg or "**"), self.value(entry, k.value)) for k in node.keywords)
        if api is None and isinstance(node.func, ast.Attribute):
            inputs.insert(0, ("receiver", self.value(entry, node.func.value)))
        output = self.obj(entry, tag, properties={"runtime_type": "unknown"})
        return self.operation(entry, node, "uninterpreted_call", api, inputs, output,
                              {"scientific_semantics": "unknown", "wrapper": wrapper})

    def finish(self):
        for entry in sorted(self.entries.values(), key=lambda e: (e["path"], e["start_line"], e.get("start_col", 0), e["id"])):
            self.statement(entry)
        interfaces = {(e["path"], e["scope"]): self.done.get(e["id"]) for e in self.entries.values()
                      if e["kind"] == "signature" and not e.get("native", {}).get("declaration_only")}
        for entry in self.entries.values():
            owner = interfaces.get((entry["path"], entry.get("function_scope") or entry["scope"]))
            value = self.done.get(entry["id"])
            if owner and value and entry["kind"] in {"parameter", "return"}:
                self.link(value, owner, "parameter_of" if entry["kind"] == "parameter" else "returns_from")
        # Finite call-site links, never a recursive semantic summary or claim
        # that caller arguments equal callee parameters. Wrapper chains remain
        # visible when their bodies were already selected into the packet.
        for operation in self.operations.values():
            wrapper = operation["properties"].get("wrapper", {})
            if wrapper.get("status") != "lexical_target_only":
                continue
            body = [o["id"] for o in self.operations.values() if
                    self.entries[o["source_entry_id"]]["path"] == wrapper["path"] and
                    self.entries[o["source_entry_id"]].get("function_scope", self.entries[o["source_entry_id"]]["scope"]) == wrapper["body_scope"]]
            wrapper["indexed_body_operation_ids"] = body
            for oid in body:
                self.link(operation["id"], oid, "may_invoke_body")
        # API-connected structure is a coverage category, not an admission gate.
        # Custom scientific computation must still expose source-backed objects
        # for contextual interpretation even when none of our API rules apply.
        connected = set(self.scientific)
        while True:
            before = len(connected)
            for link in self.links:
                if link["source"] in connected or link["target"] in connected:
                    connected.update((link["source"], link["target"]))
            if len(connected) == before:
                break
        objects = list(self.objects.values())
        operations = list(self.operations.values())
        self.coverage.update(objects=len(objects), operations=len(operations),
            api_connected_objects=sum(o["id"] in connected for o in objects),
            code_only_objects=sum(o["id"] not in connected for o in objects),
            unsupported_cases=len(self.unsupported),
            unresolved_inputs=sum(i["object_id"] is None for o in operations for i in o["inputs"]))
        per_file = []
        for path in sorted(set(self.coverage["source_files"]) | {u["path"] for u in self.unsupported if u["path"]}):
            ops = [o for o in self.operations.values() if self.entries[o["source_entry_id"]]["path"] == path]
            science = [o for o in ops if o["id"] in self.scientific]
            row = {"path": path, "inspected_calls": len(self.inspected_calls.get(path, set())),
                   "scientific_operations": len(science),
                   "scientific_api_calls": sum(o["kind"] != "quantity_arithmetic" for o in science),
                   "uninterpreted_calls": sum(o["kind"] == "uninterpreted_call" for o in ops),
                   "support_operations": sum(o["id"] not in self.scientific and o["kind"] != "uninterpreted_call" for o in ops),
                   "unsupported_cases": sum(u["path"] == path for u in self.unsupported)}
            row["scientific_call_fraction"] = row["scientific_api_calls"] / row["inspected_calls"] if row["inspected_calls"] else None
            per_file.append(row)
        totals = {key: sum(row[key] for row in per_file) for key in
                  ("inspected_calls", "scientific_operations", "scientific_api_calls", "uninterpreted_calls", "support_operations", "unsupported_cases")}
        totals["scientific_call_fraction"] = totals["scientific_api_calls"] / totals["inspected_calls"] if totals["inspected_calls"] else None
        self.coverage.update(per_file=per_file, totals=totals,
            fraction_definition="scientific_api_calls / inspected_calls; includes array/support and rejected calls in denominator, excludes arithmetic from numerator; packet-local, not scientific completeness")
        return {"schema_version": SCHEMA_VERSION, "objects": objects, "operations": operations,
                "links": list(self.links),
                "unsupported": self.unsupported, "coverage": self.coverage}


def _link_workflow_references(graph, packet):
    """Attach retrieved source candidates; never substitute arguments or infer call results."""
    entries = {e["id"]: e for e in packet["entries"]}
    interfaces = [o for o in graph["objects"] if o["kind"] == "code_interface"]
    references = packet.get("coverage", {}).get("workflow_retrieval", {}).get("references", [])
    added = []
    for ref in references:
        targets = [o for o in interfaces if o["path"] == ref["path"] and o["source_span"]["start_line"] == ref["start_line"]]
        if len(targets) != 1:
            continue
        target = targets[0]
        target_entry = entries[target["source_entry_ids"][0]]
        for caller in ref.get("callers", []):
            if caller.get("embedded_string"):
                # Program text is not a call executed by its Python host.
                continue
            candidates = []
            for operation in graph["operations"]:
                entry = entries[operation["source_entry_id"]]
                if operation["kind"] != "uninterpreted_call" or entry["path"] != caller["path"]:
                    continue
                properties = operation["properties"]
                callee = properties.get("callee") or properties.get("wrapper", {}).get("function")
                normal = str.casefold if entry.get("language") == "fortran" else str
                if not callee or normal(callee) != normal(caller["callee"]):
                    continue
                site = operation.get("call_site")
                if site is not None:
                    matches = site["start_line"] == caller["start_line"] and site["start_col"] == caller["start_col"]
                else:
                    matches = entry["start_line"] == caller["start_line"] and entry["start_col"] == caller["start_col"]
                if matches:
                    candidates.append(operation)
            if len(candidates) != 1:
                continue
            operation = candidates[0]
            evidence = {"object_id": target["id"], "path": ref["path"], "start_line": ref["start_line"],
                "symbol": ref["symbol"], "via": ref["via"], "caller": caller,
                "status": "source_reference_only", "runtime_invocation": "not_established",
                "argument_and_return_equivalence": "not_derived"}
            operation["properties"].setdefault("retrieved_targets", [])
            if evidence not in operation["properties"]["retrieved_targets"]:
                operation["properties"]["retrieved_targets"].append(evidence)
            added.append({"source": operation["id"], "target": target["id"], "relation": "possible_callee_interface"})
            if not target_entry.get("native", {}).get("declaration_only"):
                body = [o for o in graph["operations"] if o["source"]["path"] == target["path"] and
                        (entries[o["source_entry_id"]].get("function_scope") or o["source"]["scope"]) == target["scope"]]
                for body_op in body:
                    added.append({"source": operation["id"], "target": body_op["id"], "relation": "possible_callee_body"})
    for link in added:
        if link not in graph["links"]:
            graph["links"].append(link)
    graph["coverage"]["workflow_reference_links"] = sum(l["relation"] == "possible_callee_interface" for l in graph["links"])
    if added:
        graph["coverage"]["limitations"].append("Possible callee links are retrieval evidence, not dispatch/value-flow proofs; excluded from API-connected object counts.")


def extract_objects(root: Path, packet: dict) -> dict:
    """Lift supported, source-backed API uses into a compositional object graph.

    Pure static extraction: no model calls, repository imports or execution.
    Input is a packet from :func:`scicontext.packet.build_packet` or the existing
    evidence index. Properties marked unknown are intentionally not completed.
    """
    root = Path(root).resolve(strict=True)
    python_entries = [e for e in packet["entries"] if e.get("language", "python") == "python"]
    native_entries = [e for e in packet["entries"] if e.get("language", "python") != "python"]
    result = _Extractor(root, {**packet, "entries": python_entries}).finish()
    if native_entries:
        from .native_objects import NativeExtractor
        native = NativeExtractor(root, {**packet, "entries": native_entries}).finish()
        for key in ("objects", "operations", "links", "unsupported"):
            result[key].extend(native[key])
        coverage = result["coverage"]
        for key in ("input_entries", "valid_source_entries", "objects", "operations", "unsupported_cases",
                    "unresolved_inputs", "code_only_objects", "api_connected_objects", "recognized_scientific_operations"):
            coverage[key] += native["coverage"][key]
        coverage["source_files"] = sorted(set(coverage["source_files"]) | set(native["coverage"]["source_files"]))
        coverage["per_file"] = sorted(coverage["per_file"] + native["coverage"]["per_file"], key=lambda r: r["path"])
        for key in coverage["totals"]:
            if key != "scientific_call_fraction":
                coverage["totals"][key] += native["coverage"]["totals"][key]
        totals = coverage["totals"]
        totals["scientific_call_fraction"] = totals["scientific_api_calls"] / totals["inspected_calls"] if totals["inspected_calls"] else None
        coverage["limitations"].append("Native-language operators are source syntax, not inferred scientific or runtime semantics.")
    result["coverage"]["languages"] = sorted({e.get("language", "python") for e in packet["entries"]})
    source_issues = [s for s in packet.get("coverage", {}).get("skipped", []) if
                     s.get("reason") in {"parse_error", "partial_parse", "parse_or_read_failure", "native_entry_limit",
                         "cython_parse_error", "cython_parse_diagnostic", "cython_lexical_diagnostic",
                         "cython_compile_time_region_not_evaluated"}]
    rows = {r["path"]: r for r in result["coverage"]["per_file"]}
    for issue in source_issues:
        result["unsupported"].append({"source_entry_id": None, **issue})
        path = issue.get("path")
        if path not in rows:
            rows[path] = {"path": path, "inspected_calls": 0, "scientific_operations": 0,
                "scientific_api_calls": 0, "uninterpreted_calls": 0, "support_operations": 0,
                "unsupported_cases": 0, "scientific_call_fraction": None}
        rows[path]["unsupported_cases"] += 1
    if source_issues:
        result["coverage"]["per_file"] = [rows[p] for p in sorted(rows)]
        result["coverage"]["unsupported_cases"] = len(result["unsupported"])
        result["coverage"]["totals"]["unsupported_cases"] = sum(r["unsupported_cases"] for r in rows.values())
    result["coverage"]["source_frontend_issues"] = len(source_issues)
    _link_workflow_references(result, packet)
    return result
