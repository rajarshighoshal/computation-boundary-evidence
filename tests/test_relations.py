"""Relation classification and loci rules R1-R7 on synthetic traces."""
from scicontext.fingerprint import fingerprint
from scicontext.relations import derive_loci


def _fp(*values):
    return [fingerprint(value) for value in values]


def _record(seq, name, parent, inputs=None, return_value=None, file="m.py", line=1):
    record = {"seq": seq, "name": name, "file": file, "line": line, "parent_seq": parent,
              "inputs": inputs or {}, "return_fp": fingerprint(return_value) if return_value is not None else None,
              "fingerprinted": True}
    return record


def _module_trace():
    """module -> f(x=1) and f(x=2) returning the same thing (R1 insensitivity)."""
    (fp_ret,) = _fp(3.0)
    return [
        _record(1, "<module>", None),
        _record(2, "f", 1, inputs={"x": fingerprint(1.0)}, return_value=3.0),
        _record(3, "f", 1, inputs={"x": fingerprint(2.0)}, return_value=3.0),
    ]


def test_r1_sensitivity_violated_when_param_delta_gives_identical_output():
    result = derive_loci(_module_trace(), [])
    loci = result["loci"]
    sensitivity = [l for l in loci if l["properties"]["rule_id"] == "R1"]
    assert len(sensitivity) == 1
    assert sensitivity[0]["properties"]["constraint_type"] == "sensitivity"
    assert sensitivity[0]["properties"]["status"] == "violated"
    pair = sensitivity[0]["properties"]["evidence"]["pairs"][0]
    assert pair["input_relation"] == "param_delta"
    assert pair["delta_param"] == {"name": "x", "a": "1.0", "b": "2.0"}


def test_r2_invariance_violated_when_related_inputs_differ_in_output():
    records = [
        _record(1, "<module>", None),
        _record(2, "sig", 1, inputs={"keys": fingerprint([1, 2, 3])}, return_value=[1.0, 2.0]),
        _record(3, "sig", 1, inputs={"keys": fingerprint([3, 1, 2])}, return_value=[1.0, 3.0]),
    ]
    result = derive_loci(records, [])
    invariance = [l for l in result["loci"] if l["properties"]["rule_id"] == "R2"]
    assert len(invariance) == 1
    assert invariance[0]["properties"]["status"] == "violated"


def test_r3_invariance_holds_when_related_inputs_agree():
    records = [
        _record(1, "<module>", None),
        _record(2, "sig", 1, inputs={"keys": fingerprint([1, 2, 3])}, return_value=[1.0, 2.0]),
        _record(3, "sig", 1, inputs={"keys": fingerprint([3, 1, 2])}, return_value=[1.0, 2.0]),
    ]
    result = derive_loci(records, [])
    holds = [l for l in result["loci"] if l["properties"]["rule_id"] == "R3"]
    assert len(holds) == 1 and holds[0]["properties"]["status"] == "holds"
    assert not [l for l in result["loci"] if l["properties"]["rule_id"] == "R2"]


def test_r4_distinctness_violated_for_collapse():
    records = [
        _record(1, "<module>", None),
        _record(2, "project", 1, inputs={"mode": fingerprint("m1")}, return_value=[1.0]),
        _record(3, "project", 1, inputs={"mode": fingerprint("m2")}, return_value=[1.0]),
        _record(4, "project", 1, inputs={"mode": fingerprint("m3")}, return_value=[1.0]),
    ]
    result = derive_loci(records, [])
    collapse = [l for l in result["loci"] if l["properties"]["rule_id"] == "R4"]
    assert len(collapse) >= 1


def test_r7_nondeterminism_suppresses_relation_rules():
    records = [
        _record(1, "<module>", None),
        _record(2, "f", 1, inputs={"x": fingerprint(1.0)}, return_value=1.0),
        _record(3, "f", 1, inputs={"x": fingerprint(1.0)}, return_value=2.0),
    ]
    result = derive_loci(records, [])
    assert result["dynamic"]["nondeterministic_funcs"]
    assert not [l for l in result["loci"] if l["properties"]["rule_id"] in {"R1", "R2", "R4"}]


def test_r5_finiteness_from_nan_stats():
    import numpy as np
    records = [
        _record(1, "<module>", None),
        _record(2, "solve", 1, inputs={}, return_value=np.array([np.nan, 1.0])),
    ]
    result = derive_loci(records, [])
    finiteness = [l for l in result["loci"] if l["properties"]["rule_id"] == "R5"]
    assert len(finiteness) == 1


def test_r6_containment_when_script_failure_matches_predicate():
    records = [
        _record(1, "<module>", None),
        _record(2, "parse", 1, inputs={}, return_value=[0.5, 1.3]),
    ]
    evaluations = [{"kind": "bounds", "line": 5, "text": "(x < 1.0).all()",
                    "operands": ["x"], "evaluated": {"x": fingerprint([0.5, 1.3])}}]
    result = derive_loci(records, evaluations, script_status="AssertionError: (x < 1.0).all()")
    containment = [l for l in result["loci"] if l["properties"]["rule_id"] == "R6"]
    assert len(containment) == 1
    assert not [l for l in result["loci"] if l["properties"]["rule_id"] == "R6p"]
