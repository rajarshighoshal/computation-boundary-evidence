"""SymPy owns symbolic construction and CSE; source syntax remains authoritative."""
from __future__ import annotations

import sympy as sp


def symbolic_projection(model):
    patterns = {t["id"]: t for t in model["templates"]}
    expressions, unit_ids, unsupported = [], [], []

    def convert(node, bindings):
        if "slot" in node:
            # Unknown scientific quantity types must not imply commutativity.
            return sp.Symbol(bindings[node["slot"]], commutative=False)
        op = node.get("op")
        if op == "literal":
            value = node["value"]
            try:
                return sp.Rational(value)
            except (TypeError, ValueError):
                raise ValueError("non_numeric_literal") from None
        args = [convert(a, bindings) for a in node.get("args", [])]
        if op == "add":
            return sp.Add(*args, evaluate=False)
        if op == "sub":
            return sp.Add(args[0], sp.Mul(-1, args[1], evaluate=False), evaluate=False)
        if op == "mul":
            return sp.Mul(*args, evaluate=False)
        if op == "div":
            return sp.Mul(args[0], sp.Pow(args[1], -1, evaluate=False), evaluate=False)
        if op == "pow":
            return sp.Pow(*args, evaluate=False)
        if op == "neg":
            return sp.Mul(-1, args[0], evaluate=False)
        raise ValueError("unsupported_symbolic_operator:" + str(op))

    for unit in model["transformations"]:
        try:
            expression = convert(patterns[unit["template_id"]]["pattern"],
                                 {b["slot"]: b["quantity_id"] for b in unit["bindings"]})
        except (ValueError, TypeError, NotImplementedError):
            unsupported.append(unit["id"])
            continue
        expressions.append(expression)
        unit_ids.append(unit["id"])
    replacements, reduced = sp.cse(expressions, symbols=sp.numbered_symbols("shared_"), order="canonical")
    return {"engine": "sympy", "version": sp.__version__,
            "shared_expressions": [{"symbol": str(symbol), "expression": sp.srepr(expr)} for symbol, expr in replacements],
            "results": [{"transformation_id": uid, "expression": sp.srepr(expr)} for uid, expr in zip(unit_ids, reduced)],
            "unsupported_transformation_ids": unsupported,
            "scope": "Formal noncommutative symbolic projection and common subexpressions; not a proof of floating-point equivalence. Original ordered templates and conditions are retained."}
