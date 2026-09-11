"""Quantity graph and dependence signatures: the learned core from a trace."""
from scicontext.dynamic_binding import build_quantity_graph, dependence_signatures


def _record(seq, name, parent, inputs, return_value, file="m.py", line=1):
    from scicontext.fingerprint import fingerprint
    return {"seq": seq, "name": name, "file": file, "line": line, "parent_seq": parent,
            "inputs": {k: fingerprint(v) for k, v in inputs.items()},
            "return_fp": fingerprint(return_value)}


def test_quantity_graph_deduplicates_states_and_links_transitions():
    records = [
        _record(1, "<module>", None, {}, None),
        _record(2, "f", 1, {"x": 1.0}, 10.0),
        _record(3, "g", 1, {"y": 10.0}, 20.0),
        _record(4, "f", 1, {"x": 1.0}, 10.0),  # same quantity as seq 2
    ]
    graph = build_quantity_graph(records)
    assert len(graph["quantities"]) == 4  # 1.0, 10.0 (dedup), 20.0, plus None-return excluded
    assert len(graph["transitions"]) == 4
    produced_10 = [q for q in graph["quantities"] if q["fingerprint_exact"] == graph["transitions"][1]["produced"][0].removeprefix("q_")]
    # the produced quantity id of seq2 equals the consumed one of seq3
    assert graph["transitions"][1]["produced"][0] == graph["transitions"][2]["consumed"][0]["quantity"]


def test_dependence_signatures_separate_dead_and_live_parameters():
    records = [
        _record(1, "<module>", None, {}, None),
        _record(2, "f", 1, {"x": 1.0, "dead": 100.0}, 2.0),
        _record(3, "f", 1, {"x": 2.0, "dead": 100.0}, 4.0),
        _record(4, "f", 1, {"x": 2.0, "dead": 200.0}, 4.0),
        _record(5, "f", 1, {"x": 1.0, "dead": 200.0}, 2.0),
    ]
    signatures = dependence_signatures(records)
    f = next(sig for sig in signatures if sig["func"][1] == "f")
    assert f["arguments"]["x"] == "dependent"
    assert f["arguments"]["dead"] == "no_effect"


def test_single_instance_functions_have_no_signature():
    records = [
        _record(1, "<module>", None, {}, None),
        _record(2, "once", 1, {"x": 1.0}, 1.0),
    ]
    assert dependence_signatures(records) == []
