"""Relation classification and loci rules R1-R7 on synthetic traces."""
from scicontext.fingerprint import fingerprint
from scicontext.relations import _input_relation, _output_relation, derive_loci


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


def test_r1_identical_output_is_an_observation_without_a_declaration():
    # f(1.0) and f(2.0) returning the same value is an observation; only a
    # declared requirement makes it a sensitivity violation.
    result = derive_loci(_module_trace(), [])
    assert not [l for l in result["loci"] if l["properties"]["rule_id"] == "R1"]
    pairs = result["dynamic"]["insensitive_pairs"]
    assert len(pairs) == 1
    assert pairs[0]["input_relation"] == "param_delta"
    assert pairs[0]["delta_param"] == {"name": "x", "a": "1.0", "b": "2.0"}


def test_reordered_inputs_with_changed_output_are_observations_not_invariance_requirements():
    records = [
        _record(1, "<module>", None),
        _record(2, "sig", 1, inputs={"keys": fingerprint([1, 2, 3])}, return_value=[1.0, 2.0]),
        _record(3, "sig", 1, inputs={"keys": fingerprint([3, 1, 2])}, return_value=[1.0, 3.0]),
    ]
    result = derive_loci(records, [])
    invariance = [l for l in result["loci"] if l["properties"]["rule_id"] == "R2"]
    assert len(invariance) == 1
    assert invariance[0]["properties"]["status"] == "observed"
    assert invariance[0]["properties"]["predicate_source"] == "execution_observation"
    assert invariance[0]["properties"]["evidence"]["pairs"][0]["output_relation"] == "different"


def test_related_inputs_with_matching_outputs_do_not_prove_an_invariant():
    records = [
        _record(1, "<module>", None),
        _record(2, "sig", 1, inputs={"keys": fingerprint([1, 2, 3])}, return_value=[1.0, 2.0]),
        _record(3, "sig", 1, inputs={"keys": fingerprint([3, 1, 2])}, return_value=[1.0, 2.0]),
    ]
    result = derive_loci(records, [])
    holds = [l for l in result["loci"] if l["properties"]["rule_id"] == "R3"]
    assert len(holds) == 1 and holds[0]["properties"]["status"] == "observed"
    assert holds[0]["properties"]["evidence"]["pairs"][0]["output_relation"] == "identical"
    assert not [l for l in result["loci"] if l["properties"]["rule_id"] == "R2"]


def test_distinct_inputs_with_matching_outputs_do_not_require_distinctness():
    records = [
        _record(1, "<module>", None),
        _record(2, "project", 1, inputs={"mode": fingerprint("m1")}, return_value=[1.0]),
        _record(3, "project", 1, inputs={"mode": fingerprint("m2")}, return_value=[1.0]),
        _record(4, "project", 1, inputs={"mode": fingerprint("m3")}, return_value=[1.0]),
    ]
    result = derive_loci(records, [])
    collapse = [l for l in result["loci"] if l["properties"]["rule_id"] == "R4"]
    assert len(collapse) >= 1
    assert all(l["properties"]["status"] == "observed" for l in collapse)
    assert all(l["properties"]["predicate_source"] == "execution_observation" for l in collapse)
    assert all(l["properties"]["evidence"]["pairs"] for l in collapse)


def test_closeness_declaration_is_not_an_exact_equality_requirement():
    import numpy as np
    a, b = np.array([1.0, 2.0]), np.array([1.001, 2.0])
    assert np.allclose(a, b, atol=.01)
    records = [
        _record(1, "<module>", None),
        _record(2, "f", 1, inputs={"x": fingerprint(1.0)}, return_value=a),
        _record(3, "f", 1, inputs={"x": fingerprint(2.0)}, return_value=b),
    ]
    predicates = [{"kind": "closeness", "text": "np.allclose(a, b, atol=.01)",
                   "operands": ["a", "b"], "evaluated": {"a": fingerprint(a), "b": fingerprint(b)}}]
    result = derive_loci(records, predicates)
    assert result["dynamic"]["declared_equivalent_pairs"] == [[2, 3]]
    assert result["loci"], "Retain the measured relationship, not a false violation"
    assert all(l["properties"]["status"] == "observed" for l in result["loci"])


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
    assert finiteness[0]["properties"]["status"] == "observed"  # NaN may encode missing data.
    assert finiteness[0]["properties"]["predicate_source"] == "execution_observation"


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


def test_r6s_uses_script_polarity_not_field_names():
    records = [_record(1, "<module>", None)]
    # The script asserts `assert not collapse` (falsy required); the report
    # observes collapse=False -> the condition PASSES; no violation.
    evaluations = [{"kind": "inequality", "line": 5, "text": "not collapse",
                    "operands": ["collapse"], "asserted_truthy": False,
                    "evaluated": {"collapse": False}}]
    result = derive_loci(records, evaluations, script_status=None)
    assert not [l for l in result["loci"] if l["properties"]["rule_id"] == "R6s"]


def test_r6s_violation_when_asserted_condition_fails():
    records = [_record(1, "<module>", None)]
    # `assert signature_agreement` (truthy required); observed False -> violated.
    evaluations = [{"kind": "inequality", "line": 7, "text": "signature_agreement",
                    "operands": ["signature_agreement"], "asserted_truthy": True,
                    "evaluated": {"signature_agreement": False}}]
    report = {"status": "workflow_completed", "observation": {"signature_agreement": False}}
    result = derive_loci(records, evaluations, script_status=None, script_report=report)
    r6s = [l for l in result["loci"] if l["properties"]["rule_id"] == "R6s"]
    assert len(r6s) == 1
    assert r6s[0]["properties"]["evidence"]["measures"]["required_truthy"] is True


def test_unbound_numeric_observation_records_no_violation():
    records = [_record(1, "<module>", None)]
    # A jump-like numeric observation with NO asserting statement in the
    # script: recorded value only, never a continuity violation.
    evaluations = []
    result = derive_loci(records, evaluations, script_status=None,
                         script_report={"status": "workflow_completed",
                                        "observation": {"transition_across_boundary": 1.5}})
    assert not [l for l in result["loci"] if l.get("properties", {}).get("rule_id") in ("R6p", "R6s")]


def test_r1_requires_proven_identical_outputs():
    import numpy as np
    base = np.arange(500, dtype=float)
    swapped = base.copy()
    swapped[10], swapped[400] = swapped[400], swapped[10]   # stats preserved
    fa, fb = fingerprint(base), fingerprint(swapped)
    records = [
        _record(1, "<module>", None),
        _record(2, "f", 1, inputs={"x": fingerprint(1.0)}, return_value=None),
    ]
    # simulate returns with stats-equal but content-different fingerprints
    records[0]["return_fp"] = None
    a = {"inputs": {"x": fingerprint(1.0)}, "return_fp": fa}
    b = {"inputs": {"x": fingerprint(2.0)}, "return_fp": fb}
    relation, _ = _input_relation(a, b)
    assert relation == "param_delta"
    output = _output_relation(a, b)
    assert output != "identical"   # swapped values can never be provably identical
    # Scale-free equivalence may hold, but R1 fires ONLY on proven identity:
    records = [
        _record(1, "<module>", None),
        {"seq": 2, "name": "f", "file": "m.py", "line": 1, "parent_seq": 1,
         "inputs": {"x": fingerprint(1.0)}, "return_fp": fa, "fingerprinted": True},
        {"seq": 3, "name": "f", "file": "m.py", "line": 1, "parent_seq": 1,
         "inputs": {"x": fingerprint(2.0)}, "return_fp": fb, "fingerprinted": True},
    ]
    result = derive_loci(records, [])
    assert not [l for l in result["loci"] if l["properties"]["rule_id"] == "R1"]


def test_matching_summaries_are_not_labelled_value_equivalence():
    import numpy as np
    a, b = np.array([1., 2., 3., 4.]), np.array([1., 3., 2., 4.])
    assert _output_relation({"return_fp": fingerprint(a)}, {"return_fp": fingerprint(b)}) == "similar_summary"
    from scicontext.relations import _scale_free_equal
    assert not _scale_free_equal({"t": "ndarray", "struct": "shape", "stats": None},
                                {"t": "ndarray", "struct": "shape", "stats": None})


def _predicates_from(script_text):
    from scicontext.trace_runtime import _parse_predicates
    return _parse_predicates(script_text)


def test_parser_bare_boolean_assert_produces_falsy_predicate():
    forms = _predicates_from("assert not collapse\n")
    assert len(forms) == 1
    assert forms[0]["kind"] == "boolean"
    assert forms[0]["asserted_truthy"] is False
    assert "collapse" in forms[0]["operands"][0]


def test_parser_literal_equality_produces_required_value():
    forms = _predicates_from("assert collapse == False\n")
    assert len(forms) == 1
    assert forms[0]["required_value"] is False
    assert forms[0]["asserted_truthy"] is False


def test_parser_to_relation_falsy_passes():
    forms = _predicates_from("assert not collapse\n")
    records = [_record(1, "<module>", None)]
    report = {"status": "workflow_completed", "observation": {"collapse": False}}
    result = derive_loci(records, [{**f, "evaluated": {"collapse": False}} for f in forms],
                         script_status=None, script_report=report)
    assert not [l for l in result["loci"] if l["properties"].get("rule_id") == "R6s"]


def test_parser_to_relation_literal_eq_false_passes():
    forms = _predicates_from("assert collapse == False\n")
    records = [_record(1, "<module>", None)]
    report = {"status": "workflow_completed", "observation": {"collapse": False}}
    result = derive_loci(records, [{**f, "evaluated": {"collapse": False}} for f in forms],
                         script_status=None, script_report=report)
    assert not [l for l in result["loci"] if l["properties"].get("rule_id") == "R6s"]


def test_parser_to_relation_truthy_assert_failing_observation_violates():
    forms = _predicates_from("assert signature_agreement\n")
    records = [_record(1, "<module>", None)]
    report = {"status": "workflow_completed", "observation": {"signature_agreement": False}}
    result = derive_loci(records, [{**f, "evaluated": {"signature_agreement": False}} for f in forms],
                         script_status=None, script_report=report)
    r6s = [l for l in result["loci"] if l["properties"].get("rule_id") == "R6s"]
    assert len(r6s) == 1


def test_unbound_numeric_observation_emits_measured_record():
    records = [_record(1, "<module>", None)]
    report = {"status": "workflow_completed", "observation": {"transition_across_boundary": 1.5}}
    result = derive_loci(records, [], script_status=None, script_report=report)
    assert result["dynamic"]["observed_values"][0]["field"] == "transition_across_boundary"
    assert not [l for l in result["loci"] if l.get("properties", {}).get("rule_id") in ("R6p", "R6s")]


def test_runner_failure_is_not_a_scientific_violation():
    records = [_record(1, "<module>", None)]
    result = derive_loci(records, [], script_status=None,
                         script_report={"status": "runner_failure", "error": "CMake configuration failed"})
    assert not result["loci"]
    assert result["dynamic"]["reproduction"]["classification"] == "runner_failure"


def test_post_fix_success_is_not_a_violation():
    records = [_record(1, "<module>", None)]
    result = derive_loci(records, [], script_status=None, script_report={"status": "post_fix_success"})
    assert not result["loci"]
    assert result["dynamic"]["reproduction"]["classification"] == "success"


def test_scientific_failure_emits_r6_containment():
    records = [_record(1, "<module>", None)]
    result = derive_loci(records, [], script_status=None,
                         script_report={"status": "pre_fix_expected_failure", "failure_kind": "collapse"})
    r6 = [l for l in result["loci"] if l["properties"]["rule_id"] == "R6"]
    assert len(r6) == 1
    assert r6[0]["properties"]["constraint_type"] == "distinctness"
    assert result["dynamic"]["reproduction"]["classification"] == "scientific_failure"


def test_r1_identical_output_is_observation_unless_declared():
    # Rounding 3.0 to one vs two decimal places legitimately gives the same
    # result: unchanged output is an observation, not a sensitivity violation.
    fa = fingerprint(3.0)
    records = [
        {"seq": 1, "name": "<module>", "file": "reproduce.py", "line": 1, "parent_seq": None},
        {"seq": 2, "name": "round_like", "file": "m.py", "line": 1, "parent_seq": 1,
         "inputs": {"places": fingerprint(1)}, "return_fp": fa, "fingerprinted": True},
        {"seq": 3, "name": "round_like", "file": "m.py", "line": 1, "parent_seq": 1,
         "inputs": {"places": fingerprint(2)}, "return_fp": fa, "fingerprinted": True},
    ]
    result = derive_loci(records, [])
    assert not [l for l in result["loci"] if l["properties"]["rule_id"] == "R1"]
    assert result["dynamic"]["insensitive_pairs"], "unchanged output stays an observation"
