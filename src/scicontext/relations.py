"""Relation layer and constraint-locus derivation (rules R1-R9).

Consumes trace records, script-declared predicate evaluations and an optional
observer summary; emits constraint_locus records with evidence. The rules are
predeclared and task-agnostic: they classify relations between repeated call
instances of the same function and map them onto constraint findings.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

SCHEMA_VERSION = "scientific-objects-1.1"
MAX_PAIRS_PER_FUNC = 8
_TRIVIAL_SCALARS = {"bool", "int", "NoneType"}


def _fp_equal(a, b, field="exact"):
    if not a or not b:
        return False
    value = a.get(field)
    return value == b.get(field) and value is not None


def _stats_equal(a, b):
    if a is None or b is None:
        return a == b
    keys = {"n", "min", "max", "sum", "n_nan", "n_inf"}
    for key in keys:
        left, right = a.get(key), b.get(key)
        if left is None and right is None:
            continue
        if left is None or right is None:
            return False
        if abs(float(left) - float(right)) > 1e-9 * max(1.0, abs(float(left)), abs(float(right))):
            return False
    return True


def _round9(value) -> float:
    return float(f"{value:.9g}")


def _same(a, b):
    """Equality evidence, strongest first: content digest, byte-exact, array
    stats, otherwise unknown (never equal on struct alone)."""
    if not a or not b:
        return False
    left, right = a.get("content"), b.get("content")
    if left is not None and right is not None:
        return left == right
    left, right = a.get("exact"), b.get("exact")
    if left is not None and right is not None:
        return left == right
    if a.get("t") == b.get("t") == "ndarray":
        return a.get("struct") == b.get("struct") and _stats_equal(a.get("stats"), b.get("stats"))
    return False


def _normalized(stats: dict) -> tuple:
    if not stats:
        return ()
    scale = max(1.0, abs(float(stats.get("min") or 0)), abs(float(stats.get("max") or 0)))
    return tuple(_round9(float(stats[key]) / scale) for key in ("min", "max", "sum")
                 if stats.get(key) is not None)


def _scale_free_equal(a, b):
    """Scale-free equivalence: each stats tuple normalized by its own scale."""
    if not a or not b:
        return False
    if a.get("t") == b.get("t") == "scalar" and a.get("equiv") is not None:
        return a["equiv"] == b["equiv"]
    if a.get("t") == b.get("t") == "ndarray" and a.get("struct") == b.get("struct"):
        return _normalized(a.get("stats")) == _normalized(b.get("stats"))
    return False


def _is_trivial(fp) -> bool:
    return bool(fp) and fp.get("t") == "scalar" and fp.get("struct") in _TRIVIAL_SCALARS


def _input_relation(a, b) -> tuple[str, dict | None]:
    if not a.get("inputs") and not b.get("inputs"):
        return ("identical", None)
    keys = set(a.get("inputs", {})) | set(b.get("inputs", {}))
    if set(a.get("inputs", {})) != set(b.get("inputs", {})):
        return ("different", None)
    all_exact = all(_same(a["inputs"].get(k), b["inputs"].get(k)) for k in keys)
    if all_exact:
        return ("identical", None)
    all_equiv = all(_scale_free_equal(a["inputs"].get(k), b["inputs"].get(k))
                    or _same(a["inputs"].get(k), b["inputs"].get(k)) for k in keys)
    if all_equiv:
        return ("equivalent", None)
    deltas = []
    rest_identical = True
    for key in keys:
        fa, fb = a["inputs"].get(key), b["inputs"].get(key)
        if not _same(fa, fb):
            if (fa and fb and fa.get("t") == fb.get("t") == "scalar"
                    and fa.get("struct") in {"float", "int"}):
                deltas.append((key, fa["exact"], fb["exact"]))
            else:
                rest_identical = False
    if len(deltas) == 1 and rest_identical:
        name, va, vb = deltas[0]
        return ("param_delta", {"name": name, "a": va, "b": vb})
    for key in keys:
        fa, fb = a["inputs"].get(key), b["inputs"].get(key)
        if fa and fb and fa.get("t") in {"seq", "dict"} and _fp_equal(fa, fb, "rev"):
            others = keys - {key}
            if all(_same(a["inputs"].get(k), b["inputs"].get(k)) for k in others):
                return ("reversed", None)
    all_multiset = all((fa and fb and fa.get("multiset") == fb.get("multiset") and fa.get("multiset") is not None)
                       or _same(fa, fb) for fa, fb in ((a["inputs"].get(k), b["inputs"].get(k)) for k in keys))
    if all_multiset:
        return ("relabeled", None)
    all_struct = all(fa and fb and fa.get("struct") == fb.get("struct") and fa.get("struct") is not None
                     for fa, fb in ((a["inputs"].get(k), b["inputs"].get(k)) for k in keys))
    if all_struct:
        return ("isomorphic_candidate", None)
    return ("different", None)


def _output_relation(a, b) -> str:
    fa, fb = a.get("return_fp"), b.get("return_fp")
    if _same(fa, fb):
        return "identical"
    if _scale_free_equal(fa, fb):
        return "equivalent"
    if fa and fb and fa.get("multiset") == fb.get("multiset") and fa.get("multiset") is not None:
        return "relabeled"
    if fa and fb and fa.get("rev") == fb.get("exact") and fa.get("exact") is not None:
        return "reversed"
    return "different"


def _declared_relations(predicate_evaluations, instances) -> tuple[set, set]:
    """Root-level producer instances bound to script predicate operands."""
    declared_equivalent: set = set()
    declared_distinct: set = set()
    producers = {}
    for seq, instance in instances.items():
        if instance.get("parent_seq") is None:
            continue
        parent = instances.get(instance["parent_seq"])
        if parent and parent.get("name") == "<module>" and instance.get("return_fp"):
            producers.setdefault(instance["return_fp"]["exact"], []).append(seq)
    for evaluation in predicate_evaluations:
        values = list(evaluation.get("evaluated", {}).values())
        operands = evaluation.get("operands") or []
        pairs = []
        for operand in operands:
            from .trace_runtime import _root_name
            name = _root_name(operand)
            if name and evaluation.get("evaluated", {}).get(name):
                fp = evaluation["evaluated"][name]
                candidate = producers.get(fp["exact"], [])
                if candidate:
                    pairs.append(candidate[0])
        if len(pairs) >= 2:
            a, b = pairs[0], pairs[1]
            if a != b:
                if evaluation.get("kind") in {"equality", "closeness"}:
                    declared_equivalent.add((a, b))
                elif evaluation.get("kind") == "inequality":
                    declared_distinct.add((a, b))
    return declared_equivalent, declared_distinct


def _children_map(instances) -> dict:
    children = defaultdict(list)
    for seq, instance in instances.items():
        parent = instance.get("parent_seq")
        if parent is not None:
            children[parent].append(seq)
    for seqs in children.values():
        seqs.sort()
    return children


def _aligned_children(a, b, instances, children):
    ca = [seq for seq in children.get(a, [])]
    cb = [seq for seq in children.get(b, [])]
    groups = defaultdict(lambda: [None, None])
    for seq in ca:
        instance = instances[seq]
        key = (instance["file"], instance["name"], instance["line"])
        ordinal = len([s for s in children.get(a, []) if s < seq
                       and (instances[s]["file"], instances[s]["name"], instances[s]["line"]) == key])
        groups[(key, ordinal)][0] = seq
    for seq in cb:
        instance = instances[seq]
        key = (instance["file"], instance["name"], instance["line"])
        ordinal = len([s for s in children.get(b, []) if s < seq
                       and (instances[s]["file"], instances[s]["name"], instances[s]["line"]) == key])
        groups[(key, ordinal)][1] = seq
    return [(x, y) for x, y in groups.values() if x is not None and y is not None]


def _first_divergence(a, b, instances, children) -> int:
    """Deepest aligned child pair with related inputs and different outputs."""
    locus = a
    pending = [(a, b)]
    while pending:
        x, y = pending.pop(0)
        locus = x
        for cx, cy in _aligned_children(x, y, instances, children):
            relation, _ = _input_relation(instances[cx], instances[cy])
            if relation in {"identical", "equivalent", "relabeled", "reversed"} and \
                    _output_relation(instances[cx], instances[cy]) == "different":
                pending.append((cx, cy))
    return locus


def _provenance_chain(fp_exact: str, instances, children) -> list:
    chain = []
    for seq, instance in instances.items():
        return_fp = instance.get("return_fp") or {}
        if (return_fp.get("content") or return_fp.get("exact")) == fp_exact:
            chain.append(seq)
    return chain[:3]


def _cl(key, rule, func_key, constraint_type) -> dict:
    file, name, line = func_key
    import hashlib
    digest = hashlib.sha256(json.dumps([constraint_type, func_key, rule], sort_keys=True).encode()).hexdigest()[:24]
    return {"id": f"cl_{digest}", "kind": "constraint_locus", "symbol": f"{constraint_type}@{name}",
            "path": file, "scope": name,
            "source_entry_ids": [], "source_span": {"start_line": line, "end_line": line},
            "properties": {"constraint_type": constraint_type, "status": "violated", "rule_id": rule,
                           "predicate_source": "script_declared", "locus_transitions": [],
                           "static_candidates": [], "evidence": {"pairs": [], "measures": {}}},
            "roles": ["constraint_finding"]}


def derive_loci(trace_records: list, predicate_evaluations: list, script_status: str | None = None,
                observer_summary: dict | None = None, packet: dict | None = None,
                script_file: str | None = None, script_report: dict | None = None) -> dict:
    if script_file:
        trace_records = [record for record in trace_records if record.get("file") != script_file]
    instances = {record["seq"]: record for record in trace_records}
    children = _children_map(instances)
    declared_equivalent, declared_distinct = _declared_relations(predicate_evaluations, instances)
    groups = defaultdict(list)
    for record in trace_records:
        groups[(record["file"], record["name"], record["line"])].append(record["seq"])
    loci: list[dict] = []
    nondeterministic: list[tuple] = []
    pair_count = 0
    for func_key, seqs in groups.items():
        if len(seqs) < 2:
            continue
        for index, a in enumerate(seqs[:MAX_PAIRS_PER_FUNC]):
            for b in seqs[index + 1:MAX_PAIRS_PER_FUNC]:
                if a == b:
                    continue
                pair_count += 1
                ia, ib = instances[a], instances[b]
                relation, delta = _input_relation(ia, ib)
                output = _output_relation(ia, ib)
                if relation == "identical" and output == "different":
                    nondeterministic.append(func_key)
                    continue
                pair_key = (min(a, b), max(a, b))
                differing_inputs = [k for k in set(ia.get("inputs", {})) | set(ib.get("inputs", {}))
                                    if not _same(ia.get("inputs", {}).get(k), ib.get("inputs", {}).get(k))]
                scientific_pair = (relation in {"relabeled", "reversed"}
                                   or pair_key in declared_equivalent
                                   or any(
                    (ia.get("inputs", {}).get(k) or {}).get("t") in {"scalar", "ndarray"}
                    or (ib.get("inputs", {}).get(k) or {}).get("t") in {"scalar", "ndarray"}
                    for k in differing_inputs))
                if relation == "param_delta" and output in {"identical", "equivalent"} \
                        and not _is_trivial(ia.get("return_fp")):
                    locus = _cl(func_key, "R1", func_key, "sensitivity")
                    locus["properties"]["locus_transitions"] = [a, b]
                    locus["properties"]["evidence"]["pairs"] = [{"a": a, "b": b, "input_relation": relation,
                                                                 "output_relation": output, "delta_param": delta}]
                    loci.append(locus)
                elif scientific_pair and (pair_key in declared_equivalent or relation in {"relabeled", "reversed"}):
                    if output == "different":
                        deepest = _first_divergence(a, b, instances, children)
                        locus = _cl(func_key, "R2", func_key, "invariance")
                        locus["properties"]["locus_transitions"] = [deepest, a, b]
                        locus["properties"]["evidence"]["pairs"] = [{"a": a, "b": b, "input_relation": relation,
                                                                     "output_relation": output,
                                                                     "declared": pair_key in declared_equivalent}]
                        loci.append(locus)
                    else:
                        locus = _cl(func_key, "R3", func_key, "invariance")
                        locus["properties"]["status"] = "holds"
                        locus["properties"]["locus_transitions"] = [a, b]
                        loci.append(locus)
                elif scientific_pair and relation not in {"equivalent", "param_delta"} and output == "identical" \
                        and not _is_trivial(ia.get("return_fp")):
                    distinct_pairs = sum(1 for x in seqs if x != a
                                         and _input_relation(instances[x], ia)[0] not in {"equivalent", "param_delta"}
                                         and _output_relation(instances[x], ia) == "identical")
                    if distinct_pairs >= 2 or pair_key in declared_distinct:
                        locus = _cl(func_key, "R4", func_key, "distinctness")
                        locus["properties"]["locus_transitions"] = [a, b]
                        loci.append(locus)
    # R5: finiteness via fingerprint stats.
    for record in trace_records:
        fp = record.get("return_fp") or {}
        stats = fp.get("stats")
        if stats and (stats.get("n_nan") or stats.get("n_inf")):
            locus = _cl((record["file"], record["name"], record["line"]), "R5",
                        (record["file"], record["name"], record["line"]), "finiteness")
            locus["properties"]["locus_transitions"] = [record["seq"]]
            locus["properties"]["evidence"]["measures"] = {"n_nan": stats["n_nan"], "n_inf": stats["n_inf"]}
            loci.append(locus)
    # R6/R6': script predicate violations (the reproducer failed its own check).
    script_observable_producers = {}
    for seq, instance in instances.items():
        if instance.get("parent_seq") is not None and instance.get("return_fp"):
            parent = instances.get(instance["parent_seq"])
            if parent and parent.get("name") == "<module>":
                fp = instance["return_fp"]
                script_observable_producers.setdefault(fp.get("content") or fp.get("exact"), seq)
    for evaluation in predicate_evaluations:
        # The failing reproducer names its own violated predicate: match the
        # assertion text against the recorded failure before claiming violation.
        violated = bool(script_status) and evaluation.get("text") in script_status
        if not violated:
            continue
        from .trace_runtime import _root_name
        names = [_root_name(o) for o in (evaluation.get("operands") or [])]
        producers = [script_observable_producers.get(name) for name in names if name]
        func_key = ("reproduce.py", "<script>", evaluation.get("line", 0))
        if evaluation.get("kind") in {"equality", "closeness"}:
            locus = _cl(func_key, "R6p", func_key, "continuity")
            locus["properties"]["locus_transitions"] = [p for p in producers if p]
            loci.append(locus)
        elif evaluation.get("kind") == "bounds":
            locus = _cl(func_key, "R6", func_key, "containment")
            locus["properties"]["locus_transitions"] = [p for p in producers if p]
            loci.append(locus)
    # R8: process-level completion evidence.
    if observer_summary:
        for process in observer_summary.get("processes", []):
            if process.get("exe") != "python" and (process.get("stall") or observer_summary.get("stall")):
                locus = _cl((str(process.get("pid")), process.get("exe", ""), 0), "R8",
                            (str(process.get("pid")), process.get("exe", ""), 0), "completion")
                locus["properties"]["predicate_source"] = "process_observable"
                locus["properties"]["evidence"]["process"] = process
                loci.append(locus)
    if script_report:
        if script_report.get("status") != "workflow_completed":
            kind = script_report.get("failure_kind") or "workflow_failure"
            locus = _cl(("reproduce.py", "<script>", 0), "R6", ("reproduce.py", "<script>", 0),
                        "distinctness" if "collapse" in kind else "containment")
            locus["properties"]["evidence"]["measures"]["reproduction_status"] = script_report.get("status")
            if kind != "workflow_failure":
                locus["properties"]["evidence"]["measures"]["failure_kind"] = kind
            loci.append(locus)
        # Script-declared observations carry the constraints even when the
        # report status is nominal: boolean agreement/invariance/distinctness
        # fields that are False, and numeric transition/jump/difference fields
        # that are nonzero, are recorded as observed violations with the
        # script's own measured value.
        observations = script_report.get("observation", script_report.get("scientific_observation")) or {}
        if isinstance(observations, dict):
            for field, value in observations.items():
                name = str(field).lower()
                if isinstance(value, bool) and not value and any(
                        token in name for token in ("agreement", "invariant", "consistent",
                                                    "distinct", "collapse", "finite")):
                    kind = "distinctness" if "distinct" in name or "collapse" in name else "invariance"
                    locus = _cl(("reproduce.py", "<script>", 0), "R6s", ("reproduce.py", "<script>", 0), kind)
                    locus["properties"]["evidence"]["measures"][field] = value
                    loci.append(locus)
                elif isinstance(value, (int, float)) and not isinstance(value, bool) and abs(value) > 1e-9 \
                        and any(token in name for token in ("transition", "jump", "across", "boundary", "diff")):
                    locus = _cl(("reproduce.py", "<script>", 0), "R6p", ("reproduce.py", "<script>", 0), "continuity")
                    locus["properties"]["evidence"]["measures"][field] = value
                    loci.append(locus)
    aggregated: dict[str, dict] = {}
    for locus in loci:
        existing = aggregated.get(locus["id"])
        if existing is None:
            aggregated[locus["id"]] = locus
            continue
        existing["properties"]["locus_transitions"] = sorted(set(
            existing["properties"]["locus_transitions"] + locus["properties"]["locus_transitions"]))
        existing["properties"]["evidence"]["pairs"].extend(locus["properties"]["evidence"]["pairs"])
    unique_loci = list(aggregated.values())
    return {"loci": unique_loci,
            "dynamic": {"schema_version": SCHEMA_VERSION, "instances": len(instances),
                        "pairs": pair_count, "loci": len(unique_loci),
                        "nondeterministic_funcs": sorted({json.dumps(key) for key in nondeterministic}),
                        "declared_equivalent_pairs": sorted(map(list, declared_equivalent)),
                        "declared_distinct_pairs": sorted(map(list, declared_distinct))}}


def load_trace(trace_path: Path) -> list:
    import gzip
    opener = gzip.open if str(trace_path).endswith(".gz") else open
    with opener(trace_path, "rt", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]
