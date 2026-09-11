"""Native-language syntax anchors in the shared scientific-object representation."""
from __future__ import annotations

import copy

from .scientific_objects import _Extractor


class NativeExtractor(_Extractor):
    def normal(self, value, entry):
        return value.casefold() if entry["language"] == "fortran" else value

    def binding(self, entry, name):
        name = self.normal(name, entry)
        if name in entry.get("native", {}).get("omitted_prior_bindings", []):
            self.problem(entry, "omitted_native_binding", symbol=name)
            return None
        position = lambda e: tuple(e.get("native", {}).get("order_start", (e["start_line"], e["start_col"])))
        if any(e["path"] == entry["path"] and e.get("function_scope") == entry.get("function_scope")
               and position(e) < position(entry) and e.get("native", {}).get("nonlocal_write")
               and self.normal(e["native"].get("writes_root", ""), e) == name for e in self.entries.values()):
            self.problem(entry, "native_mutation_not_resolved", symbol=name)
            return None
        for scope in reversed(entry.get("scope_chain", [entry["scope"]])):
            if entry.get("function_scope") and not scope.startswith(entry["function_scope"]):
                break  # Global values can change between calls; no interprocedural value proof.
            definitions = [e for e in self.entries.values() if e["path"] == entry["path"] and
                e.get("native", {}).get("binding_scope", e["scope"]) == scope
                and e["id"] != entry["id"] and e["kind"] in {"parameter", "declaration", "assignment"}
                and name in [self.normal(n, e) for n in e.get("entity_symbols", [])]
                and position(e) < position(entry)]
            definitions = [e for e in definitions if not e.get("native", {}).get("type_annotation") or
                           not any(p["kind"] == "parameter" for p in definitions)]
            if not definitions:
                continue
            candidate = max(definitions, key=position)
            branch = candidate.get("branch", [])
            if entry.get("branch", [])[:len(branch)] != branch:
                self.problem(entry, "conditional_native_binding", symbol=name)
                return None
            if candidate.get("native", {}).get("nonlocal_write"):
                self.problem(entry, "native_mutation_not_resolved", symbol=name)
                return None
            return self.statement(candidate)
        self.problem(entry, "unresolved_native_binding", symbol=name)
        return None

    def statement(self, entry):
        key = entry["id"]
        if key in self.done:
            return self.done[key]
        if key in self.active:
            self.problem(entry, "cyclic_native_binding")
            return None
        self.active.add(key)
        symbols = entry.get("entity_symbols", [])
        native = entry.get("native", {})
        output = None
        if entry["kind"] == "signature":
            output = self.obj(entry, "interface", kind="code_interface",
                properties={"signature": entry["text"], "language": entry["language"],
                            "runtime_type": "not_inferred", "interface": copy.deepcopy(native)})
        elif entry["kind"] in {"parameter", "declaration"}:
            output = self.obj(entry, "binding", symbol=symbols[0] if symbols else None,
                properties={"binding": entry["kind"], "declaration_text": native.get("declaration_text"),
                            "runtime_type": "not_inferred", "language": entry["language"]})
        elif entry["kind"] in {"assignment", "return", "call"}:
            expression = entry.get("native_expression")
            value = self.value(entry, expression) if expression else None
            if native.get("operator", "=") not in {"=", ":="}:
                updated = self.obj(entry, "update", properties={"language": entry["language"]})
                value = self.native_operation(entry, {"span": [key], "kind": "update"},
                    "uninterpreted_update", [("previous_target", self.binding(entry, symbols[0]) if symbols else None),
                                             ("right_operand", value)], updated,
                    {"syntax_operator": native["operator"]})
            props = copy.deepcopy(self.objects[value]["properties"]) if value else {}
            props.update(language=entry["language"], binding="source_only", target=native.get("target"))
            output = self.obj(entry, "binding", symbol=symbols[0] if symbols else None, properties=props)
            self.link(value, output, "returned_as" if entry["kind"] == "return" else "bound_as")
            if native.get("nonlocal_write") or native.get("operator", "=") not in {"=", ":="}:
                self.problem(entry, "native_write_effect_unresolved", target=native.get("target"),
                             operator=native.get("operator"))
        self.active.remove(key)
        self.done[key] = output
        return output

    def native_operation(self, entry, expression, kind, inputs, output, properties=None):
        return self.operation(entry, None, kind, None, inputs, output,
            {"language": entry["language"], "scientific_semantics": "unknown", **(properties or {})},
            ["Source syntax only; types, overloads, mutation effects and scientific meaning are not inferred."],
            identity=expression)

    def value(self, entry, expression):
        if expression is None:
            return None
        kind = expression["kind"]
        if kind == "name":
            return self.binding(entry, expression["name"])
        if kind == "literal":
            return self.obj(entry, expression, kind="literal",
                            properties={"literal_source": expression["text"], "language": entry["language"]})
        output = self.obj(entry, expression, properties={"language": entry["language"], "runtime_type": "unknown"})
        if kind == "binary":
            return self.native_operation(entry, expression, "source_binary", [
                ("left_operand", self.value(entry, expression["left"])),
                ("right_operand", self.value(entry, expression["right"]))], output,
                {"syntax_operator": expression["operator"]})
        if kind == "unary":
            return self.native_operation(entry, expression, "source_unary", [
                ("operand", self.value(entry, expression["operand"]))], output,
                {"syntax_operator": expression["operator"]})
        if kind == "call":
            self.inspected_calls.setdefault(entry["path"], set()).add((entry["id"], tuple(expression["span"])))
            callee = expression["callee"]
            lookup_scopes = entry.get("scope_chain", [])
            if entry["language"] == "cython" and entry.get("function_scope"):
                # Python/extension-class namespaces do not enclose method bodies
                # for unqualified name lookup; C++ member lookup is different.
                lookup_scopes = [s for s in lookup_scopes if not s.rsplit(".", 1)[-1].startswith("class:")]
            functions = [e for e in self.entries.values() if e["path"] == entry["path"] and e["kind"] == "signature"
                and self.normal(e.get("native", {}).get("function_name", ""), e) == self.normal(callee, entry)
                and (e["scope"] if e.get("native", {}).get("declaration_only") else
                     e.get("scope_chain", ["<module>"])[-2]) in lookup_scopes]
            definitions = [e for e in functions if not e.get("native", {}).get("declaration_only")]
            if entry["language"] == "c" and len(definitions) == 1:
                functions = definitions  # C has no function overloading; retain C++ ambiguity.
            shadowed = any(e["path"] == entry["path"] and e["scope"] in lookup_scopes
                and e["kind"] in {"parameter", "declaration", "assignment"}
                and self.normal(callee, entry) in [self.normal(s, e) for s in e.get("entity_symbols", [])]
                for e in self.entries.values())
            target = functions[0] if len(functions) == 1 and not shadowed else None
            declaration = target and target.get("native", {}).get("declaration_only")
            wrapper = {"status": "declaration_only" if declaration else "lexical_target_only" if target else "unresolved",
                "function": callee, "path": target["path"] if target else None,
                "source_entry_id": target["id"] if target else None,
                "body_scope": target["scope"] if target and not declaration else None}
            self.problem(entry, "native_call_semantics_unresolved", callee=callee,
                         call_or_index=bool(expression.get("index_ambiguous")), wrapper=wrapper)
            inputs = [(f"argument_{i}", self.value(entry, argument)) for i, argument in enumerate(expression["arguments"])]
            if shadowed and expression.get("index_ambiguous"):
                inputs.insert(0, ("indexed_or_callable_value", self.binding(entry, callee)))
            if expression.get("receiver"):
                inputs.insert(0, ("receiver", self.value(entry, expression["receiver"])))
            if target:
                inputs.insert(0, ("callee_interface", self.statement(target)))
            return self.native_operation(entry, expression, "uninterpreted_call", inputs,
                output, {"callee": callee, "call_or_index": bool(expression.get("index_ambiguous")), "wrapper": wrapper})
        self.problem(entry, "unsupported_native_expression", syntax_kind=expression.get("syntax_kind"),
                     expression=expression.get("text", "")[:200])
        return self.native_operation(entry, expression, "uninterpreted_expression", [
            (f"child_{i}", self.value(entry, child)) for i, child in enumerate(expression.get("children", []))],
            output, {"syntax_kind": expression.get("syntax_kind")})
