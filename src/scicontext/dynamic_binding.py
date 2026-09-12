"""Derive the compact core from a full trace: quantity graph + dependence signatures.

The raw trace is the dataset; this module learns the representation from ALL
instances: unique observed quantities (deduplicated by exact fingerprint)
become state nodes, instances become transition edges, and per-function
dependence signatures summarize which inputs the output actually responds to.
No truncation: the raw trace remains the lossless evidence artifact.
"""
from __future__ import annotations

from collections import defaultdict

MAX_SIGNATURE_INSTANCES = 64


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
        identifier = fp.get("content") or fp.get("exact")
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
    output anywhere in the instance population? A zero-effect input is a
    dead parameter; a one-way difference marks full dependence."""
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
        argument_names.discard("self.__dict__")
        signature = {"func": func_key, "instances": len(records), "arguments": {}}
        for arg in sorted(argument_names):
            effect_seen = False
            non_effect_seen = False
            for a in records:
                for b in records:
                    if a is b:
                        continue
                    ia, ib = (a.get("inputs") or {}).get(arg), (b.get("inputs") or {}).get(arg)
                    if not ia or not ib or not ia.get("exact") or not ib.get("exact"):
                        continue
                    if ia["exact"] == ib["exact"]:
                        continue
                    others_same = all(
                        (a.get("inputs") or {}).get(k, {}) and (b.get("inputs") or {}).get(k, {})
                        and ((a["inputs"][k].get("exact") == b["inputs"][k].get("exact"))
                             or k == "self.__dict__")
                        for k in argument_names if k != arg)
                    if not others_same:
                        continue
                    out_a = (a.get("return_fp") or {}).get("exact")
                    out_b = (b.get("return_fp") or {}).get("exact")
                    if out_a and out_b and out_a != out_b:
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
