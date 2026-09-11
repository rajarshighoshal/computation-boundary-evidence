"""Fingerprint semantics: exactness, scale-free equivalence, key-agnostic, reversal, structure."""
import numpy as np
import pytest

from scicontext.fingerprint import FINGERPRINT_BYTE_BUDGET, fingerprint


def test_scalars_are_typed_and_deterministic():
    assert fingerprint(3)["exact"] == fingerprint(3)["exact"]
    assert fingerprint(3)["exact"] != fingerprint(3.0)["exact"]
    assert fingerprint("mode-a")["exact"] == fingerprint("mode-a")["exact"]
    assert fingerprint(None)["struct"] == "NoneType"


def test_float_equiv_rounds_scale_free():
    a = fingerprint(1.0 + 1e-13)
    b = fingerprint(1.0 + 2e-13)
    c = fingerprint(2.0)
    assert a["equiv"] == b["equiv"]
    assert a["equiv"] != c["equiv"]
    assert a["exact"] != b["exact"]


def test_ndarray_exact_equiv_multiset_rev():
    a = np.array([[1.0, 2.0], [3.0, 4.0]])
    b = np.array([[1.0, 2.0], [3.0, 4.0]])
    c = np.array([[1000.0, 2000.0], [3000.0, 4000.0]])  # scale-free equivalent
    d = np.array([[4.0, 3.0], [2.0, 1.0]])              # reversed flat order
    fa, fb, fc, fd = (fingerprint(x) for x in (a, b, c, d))
    assert fa["exact"] == fb["exact"]
    assert fa["equiv"] == fc["equiv"]
    assert fa["exact"] != fc["exact"]
    assert fa["multiset"] == fd["multiset"]             # sorted values equal
    assert fa["rev"] != fa["exact"]
    assert fa["struct"] == fc["struct"] == fd["struct"]


def test_dict_key_agnostic_multiset():
    d1 = {"a": 1.0, "b": 2.0}
    d2 = {"x": 1.0, "y": 2.0}  # different keys, same values
    assert fingerprint(d1)["multiset"] == fingerprint(d2)["multiset"]
    assert fingerprint(d1)["exact"] != fingerprint(d2)["exact"]


def test_sequence_reversal():
    assert fingerprint([1, 2, 3])["rev"] == fingerprint([3, 2, 1])["exact"]
    assert fingerprint([1, 2, 3])["multiset"] == fingerprint([3, 2, 1])["multiset"]


def test_object_via_dict_depth_cap():
    class M:
        def __init__(self):
            self.gain = 0.15
    assert fingerprint(M())["t"] == "obj"
    assert fingerprint(M())["exact"] == fingerprint(M())["exact"]


def test_byte_budget_truncates_large_arrays():
    big = np.ones((FINGERPRINT_BYTE_BUDGET // 8 + 1,), dtype=np.float64)
    fp = fingerprint(big)
    assert fp["truncated"] is True
    assert fp["exact"] is None
    assert fp["struct"] is not None
    small = np.ones(10)
    assert fingerprint(small)["truncated"] is False


def test_opaque_values_are_typed_not_id_based():
    class A:
        __slots__ = ()
    assert fingerprint(A())["exact"] == fingerprint(A())["exact"]
    assert fingerprint(A())["struct"] == "A"
    assert fingerprint(object())["struct"] == "object"
