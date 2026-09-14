"""Derive quantity and call-pair views from recorded execution evidence.

Known value fingerprints become state nodes and recorded calls become
transitions. Parameter-response summaries use bounded samples. This is
deterministic feature extraction, not a trained model; the trace preserves
recorded events, not every execution event or the full original values.
"""
from __future__ import annotations

from collections import defaultdict

MAX_SIGNATURE_INSTANCES = 64


def _known_identity(fp):
    if not fp:
        return None
    content = fp.get("content")
    return content if content is not None else fp.get("exact")


def build_quantity_graph(trace_records: list) -> dict:
    """State/transition graph over all instances.

    quantities: fingerprint-exact deduplicated values (produced outputs and
    consumed inputs). transitions: instance -> consumed/produced quantities.
    """
    quantities: dict[str, dict] = {}
    transitions: list[dict] = []
    producers: dict[str, list[int]] = defaultdict(list)

    def quantity_id(fp) -> str | None:
        if not fp:
            return None
        identifier = _known_identity(fp)
        if identifier is None:
            return None
        if identifier not in quantities:
            quantities[identifier] = {"id": f"q_{identifier[:16]}", "fingerprint_content": identifier,
                                      "type": fp.get("t"), "struct": fp.get("struct"),
                                      "stats": fp.get("stats"), "bytes": fp.get("bytes")}
        return identifier

    for record in trace_records:
        consumed = []
        for name, fp in (record.get("inputs") or {}).items():
            identifier = quantity_id(fp)
            if identifier:
                consumed.append({"arg": name, "quantity": quantities[identifier]["id"]})
        produced = []
        fp = record.get("return_fp")
        if fp:
            identifier = quantity_id(fp)
            if identifier:
                produced.append(quantities[identifier]["id"])
                producers[identifier].append(record["seq"])
        transitions.append({"seq": record["seq"], "func": (record["file"], record["name"], record["line"]),
                            "parent_seq": record.get("parent_seq"),
                            "consumed": consumed, "produced": produced})
    return {"quantities": list(quantities.values()), "transitions": transitions,
            "producers": {key: value for key, value in producers.items()}}


def dependence_signatures(trace_records: list) -> list:
    """Per func_key: for every input, does varying ONLY that input change the
    output in the observed call pairs? This is not a causal or universal claim:
    unknown fingerprints cannot establish either equality or a parameter effect."""
    groups: dict = defaultdict(list)
    for record in trace_records:
        groups[(record["file"], record["name"], record["line"])].append(record)
    signatures = []
    for func_key, records in sorted(groups.items()):
        if len(records) < 2:
            continue
        records = records[:MAX_SIGNATURE_INSTANCES]  # predeclared cap; the rest stay in the trace
        argument_names = set()
        for record in records:
            argument_names.update((record.get("inputs") or {}).keys())
        signature = {"func": func_key, "instances": len(records), "arguments": {}}
        for arg in sorted(argument_names - {"self.__dict__"}):
            effect_seen = False
            non_effect_seen = False
            for a in records:
                for b in records:
                    if a is b:
                        continue
                    ia = _known_identity((a.get("inputs") or {}).get(arg))
                    ib = _known_identity((b.get("inputs") or {}).get(arg))
                    if ia is None or ib is None:
                        continue
                    if ia == ib:
                        continue
                    others_same = all(
                        _known_identity((a.get("inputs") or {}).get(k)) is not None
                        and _known_identity(a["inputs"][k]) == _known_identity((b.get("inputs") or {}).get(k))
                        for k in argument_names if k != arg)
                    if not others_same:
                        continue
                    out_a = _known_identity(a.get("return_fp"))
                    out_b = _known_identity(b.get("return_fp"))
                    if out_a is None or out_b is None:
                        continue
                    if out_a != out_b:
                        effect_seen = True
                    else:
                        non_effect_seen = True
            if effect_seen and not non_effect_seen:
                signature["arguments"][arg] = "dependent"
            elif non_effect_seen and not effect_seen:
                signature["arguments"][arg] = "no_effect"
            elif effect_seen and non_effect_seen:
                signature["arguments"][arg] = "mixed"
        signatures.append(signature)
    return signatures
