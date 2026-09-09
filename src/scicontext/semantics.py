"""Small, conditional scientific-operation rules over inert expression trees.

This is not a scientific specification prover. LLM-supplied meanings are anchors;
the engine follows a few mathematical consequences and retains disagreements.
All scale calculations use exact rational arithmetic, not floating-point algebra.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from fractions import Fraction
from typing import Any


def _fraction(value: Any) -> Fraction:
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Fraction)):
        raise ValueError("not a rational number")
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("non-finite number")
    if len(str(value)) > 100:
        raise ValueError("rational exceeds resource limit")
    result = Fraction(str(value))
    if result.numerator.bit_length() > 1024 or result.denominator.bit_length() > 1024:
        raise ValueError("rational exceeds resource limit")
    return result


def _dimensions(value: Any) -> dict[str, Fraction] | None:
    if value is None:
        return None
    items = list(value.items()) if isinstance(value, dict) else [(d["dimension"], d["exponent"]) for d in value]
    if len(items) > 16 or len({k for k, _ in items}) != len(items):
        raise ValueError("duplicate or excessive dimensions")
    return {k: exponent for k, v in items if (exponent := _fraction(v))}


def _bindings(value: Any) -> dict[str, str]:
    if isinstance(value, dict):
        return value
    result = {}
    for pair in value or []:
        if pair["expected"] in result:
            raise ValueError("duplicate expected binding")
        result[pair["expected"]] = pair["actual"]
    return result


def _combine(a: dict | None, b: dict | None, sign: int = 1) -> dict | None:
    if a is None or b is None:
        return None
    dims = dict(a)
    for name, exp in b.items():
        dims[name] = dims.get(name, Fraction(0)) + sign * exp
        if not dims[name]:
            del dims[name]
    return dims


def _root(value: int, degree: int) -> int | None:
    if degree <= 0 or degree > 32 or value < 0:
        return None
    if value in (0, 1):
        return value
    lo, hi = 0, 1 << ((value.bit_length() + degree - 1) // degree)
    while lo <= hi:
        mid = (lo + hi) // 2
        power = mid ** degree
        if power == value:
            return mid
        if power < value:
            lo = mid + 1
        else:
            hi = mid - 1
    return None


def _power(base: Fraction, exp: Fraction) -> Fraction | None:
    if abs(exp) > 64 or exp.denominator > 32:
        return None
    # Bound the output before exponentiation, including nested powers.
    if max(base.numerator.bit_length(), base.denominator.bit_length()) * abs(exp.numerator) > 8192 * exp.denominator:
        return None
    if exp.denominator == 1:
        return base ** exp.numerator
    if base < 0:
        return None  # Branch/real-versus-complex conventions remain unresolved.
    numer = _root(base.numerator, exp.denominator)
    denom = _root(base.denominator, exp.denominator)
    if numer is None or denom is None:
        return None
    return Fraction(numer, denom) ** exp.numerator


def _constant_value(node: dict, depth: int = 0) -> Fraction:
    """Interpret only a tiny bounded arithmetic tree, never source strings."""
    if depth > 12 or not isinstance(node, dict):
        raise ValueError("unsupported scalar expression")
    op = node.get("op")
    if op == "constant" and set(node) == {"op", "value"}:
        return _fraction(node["value"])
    args = node.get("args")
    if op == "neg" and isinstance(args, list) and len(args) == 1:
        return -_constant_value(args[0], depth + 1)
    if op in ("add", "sub", "mul", "div") and isinstance(args, list) and len(args) == 2:
        a, b = (_constant_value(arg, depth + 1) for arg in args)
        result = a + b if op == "add" else a - b if op == "sub" else a * b if op == "mul" else a / b
        return _fraction(result)
    raise ValueError("expression is not a supported literal scalar")


@dataclass
class _Properties:
    """Conditional properties; scale is a formal factor, never a unit identity.

The factor includes both numeric literals and unit-basis anchors. Its equality
or inequality therefore cannot independently establish dimensional consistency
or a scientifically incorrect conversion. Additive expressions do not have an
unambiguous single coefficient under this deliberately small value model.
"""

    dimensions: dict[str, Fraction] | None = None
    scale: Fraction | None = None
    shape: tuple | None = None

    def serial(self) -> dict:
        return {
            "dimensions": None if self.dimensions is None else {k: str(v) for k, v in sorted(self.dimensions.items())},
            "scale": None if self.scale is None else str(self.scale),
            "shape": None if self.shape is None else list(self.shape),
        }


class _Evaluator:
    def __init__(self, quantities: list[dict], aliases: dict[str, str]):
        self.anchors: dict[str, list[dict]] = {}
        for q in quantities:
            for name in {q.get("code_symbol"), q.get("id"), q.get("name")} - {None, ""}:
                self.anchors.setdefault(name, []).append(q)
        self.aliases = aliases
        self.issues: list[tuple[str, str]] = []
        self.count = 0
        self.active: set[int] = set()

    def issue(self, status: str, text: str) -> None:
        if (status, text) not in self.issues:
            self.issues.append((status, text))

    def anchor(self, symbol: str) -> _Properties:
        candidates = self.anchors.get(self.aliases.get(symbol, symbol), [])
        if len(candidates) != 1:
            self.issue("unknown", f"Symbol {symbol!r} has {'ambiguous' if candidates else 'no'} semantic anchor.")
            return _Properties()
        q = candidates[0]
        if q.get("status") == "unresolved":
            self.issue("unknown", f"Quantity {q['id']} is unresolved; its proposed properties are not propagated.")
            return _Properties()
        if not q.get("evidence_ids"):
            self.issue("unknown", f"Quantity {q['id']} lacks supporting source references; its properties are not propagated.")
            return _Properties()
        if q.get("status") == "inferred":
            self.issue("conditional", f"Quantity {q['id']} uses inferred, not established, scientific meanings.")
        try:
            dims = _dimensions(q.get("dimensions"))
            scale = _fraction(q["scale"]) if q.get("scale") is not None else None
            if scale is not None and scale <= 0:
                raise ValueError("nonpositive scale")
            shape = q.get("shape")
            if shape is not None:
                if not isinstance(shape, list) or len(shape) > 16 or any(isinstance(x, bool) or not isinstance(x, (int, str)) or isinstance(x, int) and x < 1 or isinstance(x, str) and not x for x in shape):
                    raise ValueError("invalid shape")
                shape = tuple(shape)
            return _Properties(dims, scale, shape)
        except (ValueError, TypeError, KeyError, ZeroDivisionError):
            self.issue("unknown", f"Quantity {q['id']} has invalid or ambiguous property anchors.")
            return _Properties()

    def broadcast(self, a: tuple | None, b: tuple | None) -> tuple | None:
        if a is None or b is None:
            return None
        result = []
        for i in range(1, max(len(a), len(b)) + 1):
            x, y = a[-i] if i <= len(a) else 1, b[-i] if i <= len(b) else 1
            if x == y or x == 1 or y == 1:
                result.append(y if x == 1 else x)
            elif isinstance(x, int) and isinstance(y, int):
                self.issue("conflict", f"Shapes {list(a)} and {list(b)} cannot broadcast under NumPy-style elementwise semantics.")
                return None
            else:
                self.issue("unknown", f"Symbolic extents {x!r} and {y!r} have no established equality for broadcasting.")
                return None
        return tuple(reversed(result))

    def matmul_shape(self, a: tuple | None, b: tuple | None) -> tuple | None:
        if a is None or b is None:
            return None
        if not a or not b:
            self.issue("conflict", "Matrix multiplication requires non-scalar operands.")
            return None
        if len(a) > 2 or len(b) > 2:
            self.issue("unknown", "Batched matrix multiplication is outside this rule's supported scope.")
            return None
        left, right = a[-1], b[0]
        if left != right:
            status = "conflict" if isinstance(left, int) and isinstance(right, int) else "unknown"
            self.issue(status, f"Matrix contraction extents {left!r} and {right!r} do not have established equality.")
            return None
        return (() if len(a) == 1 else (a[0],)) + (() if len(b) == 1 else (b[1],))

    def evaluate(self, node: Any, depth: int = 0) -> _Properties:
        self.count += 1
        if self.count > 512 or depth > 64 or not isinstance(node, dict) or id(node) in self.active:
            self.issue("unknown", "Expression is invalid, cyclic, or exceeds the supported node/depth limit.")
            return _Properties()
        op = node.get("op")
        if not isinstance(op, str):
            self.issue("unknown", "Expression operation must be a supported string tag.")
            return _Properties()
        if op == "symbol" and set(node) == {"op", "name"} and isinstance(node["name"], str):
            return self.anchor(node["name"])
        if op == "constant" and set(node) == {"op", "value"}:
            try:
                return _Properties({}, _fraction(node["value"]), ())
            except (ValueError, ZeroDivisionError):
                self.issue("unknown", "Non-rational or unsafe constant is not interpreted.")
                return _Properties()
        arity = {"add": 2, "sub": 2, "mul": 2, "div": 2, "pow": 2, "matmul": 2,
                 "neg": 1, "sum": 1, "sqrt": 1, "norm": 1}
        if op not in arity or set(node) != {"op", "args"} or not isinstance(node["args"], list) or len(node["args"]) != arity.get(op):
            self.issue("unknown", f"Unsupported or malformed expression operation {str(op)[:100]!r}.")
            return _Properties()
        self.active.add(id(node))
        try:
            args = [self.evaluate(arg, depth + 1) for arg in node["args"]]
        finally:
            self.active.remove(id(node))
        a = args[0]
        if op == "neg":
            return _Properties(a.dimensions, -a.scale if a.scale is not None else None, a.shape)
        if op in {"sum", "norm"}:
            if op == "sum":
                self.issue("conditional", "Sum is interpreted as a complete scalar reduction, without axis/mask/weight arguments.")
            else:
                self.issue("conditional", "Norm uses the standard homogeneous numerical norm interpretation; domain and finite-value conditions are not proved.")
            return _Properties(a.dimensions, abs(a.scale) if op == "norm" and a.scale is not None else a.scale, ())
        if op in {"pow", "sqrt"}:
            try:
                exponent = Fraction(1, 2) if op == "sqrt" else _constant_value(node["args"][1])
                if abs(exponent) > 64 or exponent.denominator > 32:
                    raise ValueError
                dims = None if a.dimensions is None else {d: value * exponent for d, value in a.dimensions.items() if value * exponent}
                scale = None if a.scale is None else _power(a.scale, exponent)
                if scale is None:
                    self.issue("unknown", "Power has no supported exact rational scale; branch and domain conditions remain unresolved.")
                if exponent.denominator != 1:
                    self.issue("conditional", "Fractional powers require valid real/complex-domain and branch assumptions; these are not established by dimension propagation.")
                return _Properties(dims, scale, a.shape)
            except (ValueError, TypeError, KeyError, ZeroDivisionError, OverflowError):
                self.issue("unknown", "Only bounded constant rational powers with defined scale factors are supported.")
                return _Properties()
        b = args[1]
        shape = self.matmul_shape(a.shape, b.shape) if op == "matmul" else self.broadcast(a.shape, b.shape)
        if op in {"add", "sub"}:
            dims = None
            if a.dimensions is not None and b.dimensions is not None:
                if a.dimensions != b.dimensions:
                    self.issue("conflict", "Addition/subtraction combines different dimensions; scientific anchors or implementation disagree.")
                else:
                    dims = a.dimensions
            # No coefficient algebra is implemented for sums. Even x + x versus
            # 2*x must not produce a misleading coefficient/units disagreement.
            scale = None
            if a.scale is not None and b.scale is not None and a.scale != b.scale:
                self.issue("unknown", "Addition/subtraction has different formal scale factors, which may simply be ordinary numeric coefficients. The combined factor is unknown; this is not a unit inconsistency or evidence that conversion is required.")
            else:
                self.issue("unknown", "A single formal factor for addition/subtraction is not inferred; dimensions remain independently checkable.")
            return _Properties(dims, scale, shape)
        dims = _combine(a.dimensions, b.dimensions, -1 if op == "div" else 1)
        scale = None
        if a.scale is not None and b.scale is not None:
            if op == "div" and b.scale == 0:
                self.issue("conflict", "Division has an explicit zero scale/constant denominator.")
            else:
                scale = a.scale / b.scale if op == "div" else a.scale * b.scale
        if op == "div":
            self.issue("conditional", "Division requires a nonzero denominator on applicable inputs; symbolic scale cancellation does not establish that condition.")
        if scale is not None and (scale.numerator.bit_length() > 8192 or scale.denominator.bit_length() > 8192):
            self.issue("unknown", "Propagated scale exceeds the exact-arithmetic resource bound.")
            scale = None
        return _Properties(dims, scale, shape)


def _walk(node: Any) -> list[dict]:
    result = []
    stack = [node]
    seen = set()
    while stack and len(result) < 512:
        current = stack.pop()
        if not isinstance(current, dict) or id(current) in seen:
            continue
        seen.add(id(current))
        result.append(current)
        if isinstance(current.get("args"), list):
            stack.extend(reversed(current["args"]))
    return result


def _lift(claim: dict, quantities: list[dict], evidence_ids: set[str]) -> tuple[str, str]:
    operation = claim.get("operation", "other")
    if operation == "other":
        return "unknown", "No supported scientific-operation rule was requested."
    if not claim.get("assumptions"):
        return "unknown", "Scientific lifting requires explicitly recorded applicability assumptions; no assumptions were invented."
    if claim.get("status") == "unresolved" or not set(claim.get("evidence_ids", [])) & evidence_ids:
        return "unknown", "Scientific lifting lacks a resolved claim with cited public evidence."
    anchors = [q for q in quantities if q.get("status") != "unresolved" and set(q.get("evidence_ids", [])) & evidence_ids]
    if not anchors:
        return "unknown", "Scientific lifting lacks evidence-backed quantity meanings."
    nodes = _walk(claim.get("relation"))
    for node in nodes:
        if not isinstance(node.get("op"), str) or "args" in node and (not isinstance(node["args"], list) or any(not isinstance(a, dict) for a in node["args"])):
            return "unknown", "Malformed expression cannot support scientific-operation lifting."
    aliases = _bindings(claim.get("bindings", []))

    def meanings(node: dict) -> str:
        names = {aliases.get(n.get("name"), n.get("name")) for n in _walk(node) if n.get("op") == "symbol" and isinstance(n.get("name"), str)}
        relevant = [q for q in anchors if names & {q.get("code_symbol"), q.get("id"), q.get("name")}]
        return " ".join(str(q.get("meaning", "")) + " " + str(q.get("name", "")) for q in relevant).lower()

    def args_of(node: dict, op: str, arity: int) -> list[dict] | None:
        args = node.get("args")
        if node.get("op") == op and isinstance(args, list) and len(args) == arity and all(isinstance(a, dict) for a in args):
            return args
        return None

    if operation == "weighted_sum":
        for node in nodes:
            reduced = args_of(node, "sum", 1)
            factors = args_of(reduced[0], "mul", 2) if reduced else None
            if factors:
                left, right = map(meanings, factors)
                density = r"\b(density|integrand)\b"
                weight = r"\b(volume|quadrature|integration weight|cell weight)\b"
                if re.search(density, left) and re.search(weight, right) or re.search(density, right) and re.search(weight, left):
                    return "supported", "Candidate discrete integral: a weighted scalar reduction is linked to documented integrand/density and volume/quadrature meanings, conditional on the supplied assumptions."
    elif operation == "normalization":
        for node in nodes:
            args = args_of(node, "div", 2)
            if args and args[1].get("op") in {"norm", "sum"} and args[0].get("op") == "symbol" and args[1].get("args") == [args[0]]:
                if re.search(r"\b(vector|probability|distribution|weight|amplitude)\b", meanings(args[0])) and re.search(r"non.?zero|positive", " ".join(claim["assumptions"]), re.I):
                    return "supported", "Candidate normalization: a quantity is divided by its own norm/sum and the supplied applicability assumptions address a nonzero denominator; this does not prove probability validity or floating-point normalization."
    elif operation == "linear_transform":
        for node in nodes:
            args = args_of(node, "matmul", 2)
            if args and re.search(r"\b(matrix|rotation|transformation|operator)\b", meanings(args[0])) and re.search(r"\b(vector|coordinate|coordinates|position|state|field)\b", meanings(args[1])):
                return "supported", "Candidate linear transformation: matrix contraction is linked to documented operator and vector/state meanings; orthogonality, conservation, and invertibility are not inferred."
    elif operation == "unit_conversion":
        pattern = any(n.get("op") in {"mul", "div"} and isinstance(n.get("args"), list) and any(isinstance(a, dict) and a.get("op") == "constant" for a in n["args"]) and meanings(n) for n in nodes)
        described = re.search(r"unit|convert|conversion|representation|scal", claim.get("description", ""), re.I)
        if pattern and described and any(q.get("dimensions") is not None for q in anchors):
            return "supported", "Candidate unit conversion: an explicit multiplicative factor acts on dimension-anchored quantities and is described as a conversion; the physical correctness of the chosen factor remains evidence-dependent."
    return "unknown", "Operation label alone is insufficient: expression structure, scientific quantity meanings, or required applicability evidence did not support this lifting rule."


def analyze_graph(graph: dict) -> dict:
    """Propagate explicitly anchored properties; retain conflicts and unknown regions.

Call ``validate_graph`` before using results for a repair handoff. This helper also
accepts mapping-form dimensions/bindings for local analysis and synthetic tests.
"""
    findings = []
    claims = graph.get("claims", [])
    quantities = {q["id"]: q for q in graph.get("quantities", [])}
    evidence_ids = {e["id"] for e in graph.get("evidence", [])}
    coverage = {"claims": len(claims), "expressions": 0, "dimension_resolved": 0, "scale_resolved": 0,
                "shape_resolved": 0, "lift_supported": 0, "lift_unknown": 0, "conflicts": 0}

    for claim in claims:
        assumptions = list(claim.get("assumptions", []))

        def finding(kind: str, status: str, explanation: str, **extra: Any) -> None:
            findings.append({"claim_id": claim["id"], "kind": kind, "status": status,
                             "explanation": explanation, "assumptions": assumptions.copy(), **extra})
            if status == "conflict":
                coverage["conflicts"] += 1

        selected = [quantities[qid] for qid in claim.get("quantity_ids", []) if qid in quantities]
        try:
            bindings = _bindings(claim.get("bindings", []))
        except (TypeError, KeyError, ValueError):
            finding("bindings", "unknown", "Invalid or ambiguous binding records; semantic analysis for this claim is skipped.")
            continue
        results = {}
        for side in ("relation", "actual"):
            expression = claim.get(side)
            if expression is None:
                finding(f"{side}_properties", "unknown", "No expression supplied; no computational properties inferred.")
                continue
            coverage["expressions"] += 1
            evaluator = _Evaluator(selected, bindings if side == "relation" else {})
            props = evaluator.evaluate(expression)
            results[side] = props
            for attribute in ("dimensions", "scale", "shape"):
                if getattr(props, attribute) is not None:
                    coverage[{"dimensions": "dimension_resolved", "scale": "scale_resolved", "shape": "shape_resolved"}[attribute]] += 1
            has_conflict = any(status == "conflict" for status, _ in evaluator.issues)
            known = props.dimensions is not None or props.scale is not None or props.shape is not None
            finding(f"{side}_properties", "conflict" if has_conflict else "conditional" if known else "unknown",
                    "Mechanically propagated properties under supplied semantic anchors and supported operation conventions; no proof of scientific correctness.", properties=props.serial())
            for status, explanation in evaluator.issues:
                finding(f"{side}_limitation", status, explanation)
        if "relation" in results and "actual" in results:
            expected, actual = results["relation"], results["actual"]
            for attribute in ("dimensions", "scale", "shape"):
                a, b = getattr(expected, attribute), getattr(actual, attribute)
                if a is None or b is None:
                    finding(f"{attribute}_comparison", "unknown", f"Incomplete {attribute} information prevents comparison.")
                elif a == b:
                    explanation = f"Expected and actual {attribute} agree under the supplied anchors; agreement does not establish algorithmic or scientific correctness."
                    if attribute == "scale":
                        explanation += " Exact rational cancellation describes formal factors only, not floating-point error or empirical invariance."
                    finding(f"{attribute}_comparison", "agreement", explanation)
                elif attribute == "scale":
                    finding("scale_comparison", "conditional",
                            "Expected and actual formal multiplicative factors differ under supplied anchors. This is a candidate expression difference, not a physical-unit inconsistency or proof of an incorrect repair. Retain the intended requirement and investigate the expression, bindings, and assumptions.",
                            expected_factor=str(a), actual_factor=str(b))
                elif attribute == "shape" and len(a) == len(b) and not any(isinstance(x, int) and isinstance(y, int) and x != y for x, y in zip(a, b)):
                    finding("shape_comparison", "unknown", "Expected and actual symbolic shape extents lack established equality or inequality; no shape conflict is asserted.")
                else:
                    finding(f"{attribute}_comparison", "conflict", f"Expected and actual {attribute} differ under supplied anchors. Retain the intended requirement; the code, binding, or scientific interpretation may need correction.")
        status, explanation = _lift(claim, selected, evidence_ids)
        coverage["lift_supported" if status == "supported" else "lift_unknown"] += 1
        finding("semantic_lifting", status, explanation)
    return {"findings": findings, "coverage": coverage,
            "limitations": [
                "All scientific meanings originate in supplied evidence-backed anchors; inferred anchors remain conditional.",
                "Scale is a formal multiplicative factor relative to supplied anchors; arbitrary addition values and physical conversion correctness are not proved.",
                "Shape rules assume ordinary NumPy-style elementwise semantics for supported operators; overloaded operators and batched matrix multiplication require separate evidence.",
                "Algebraic dimensional/scale consistency is not floating-point, scientific, or behavioural correctness.",
                "A failing observation never automatically rejects an intended scientific requirement.",
            ]}
