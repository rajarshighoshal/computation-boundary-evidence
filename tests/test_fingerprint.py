"""Structure-fingerprint semantics: structure + stats, not data contents."""
import numpy as np

from scicontext.fingerprint import EXACT_HASH_BYTES, fingerprint
from scicontext.relations import _scale_free_equal, _same


def test_scalars_are_typed_and_deterministic():
    assert fingerprint(3)["exact"] == fingerprint(3)["exact"]
    assert fingerprint(3)["exact"] != fingerprint(3.0)["exact"]
    assert fingerprint("mode-a")["exact"] == fingerprint("mode-a")["exact"]
    assert fingerprint(None)["struct"] == "NoneType"


def test_float_equiv_rounds_scale_free():
    a = fingerprint(1.0 + 1e-13)
    b = fingerprint(1.0 + 2e-13)
    c = fingerprint(2.0)
    assert _scale_free_equal(a, b)
    assert not _scale_free_equal(a, c)
    assert a["exact"] != b["exact"]


def test_ndarray_is_structure_plus_stats_plus_small_exact():
    a = np.array([[1.0, 2.0], [3.0, 4.0]])
    b = np.array([[1.0, 2.0], [3.0, 4.0]])
    c = np.array([[1000.0, 2000.0], [3000.0, 4000.0]])
    d = np.array([[4.0, 3.0], [2.0, 1.0]])
    fa, fb, fc, fd = (fingerprint(x) for x in (a, b, c, d))
    assert fa["struct"] == "ndarray:[2, 2]:float64"
    assert fa["exact"] == fb["exact"] and _same(fa, fb)
    assert _scale_free_equal(fa, fc)      # scale-free via normalized stats
    assert not _same(fa, fc)              # values differ, content digest differs
    assert not _same(fa, fd)
    assert fa["stats"]["n"] == 4 and fa["stats"]["min"] == 1.0
    assert fa["multiset"] is None and fa["rev"] is None  # arrays: structure only


def test_large_arrays_have_unknown_identity():
    big = np.ones((EXACT_HASH_BYTES // 8 + 1,), dtype=np.float64)
    fp = fingerprint(big)
    assert fp["exact"] is None
    assert fp["content"] is None          # identity unknown, never stats-implied
    assert fp["stats"] is not None        # stats stay descriptive
    assert fp["struct"] is not None


def test_swapped_interior_values_are_not_identical():
    a = np.arange(1000, dtype=float)
    b = a.copy()
    b[10], b[900] = b[900], b[10]         # same min/max/sum, different content
    fa, fb = fingerprint(a), fingerprint(b)
    assert fa["exact"] is not None and fa["exact"] != fb["exact"]


def test_dict_key_agnostic_multiset():
    d1 = {"a": 1.0, "b": 2.0}
    d2 = {"x": 1.0, "y": 2.0}
    assert fingerprint(d1)["multiset"] == fingerprint(d2)["multiset"]
    assert not _same(fingerprint(d1), fingerprint(d2))


def test_sequence_reversal():
    assert fingerprint([1, 2, 3])["rev"] == fingerprint([3, 2, 1])["exact"]
    assert fingerprint([1, 2, 3])["multiset"] == fingerprint([3, 2, 1])["multiset"]


def test_object_third_party_is_opaque():
    class A:
        pass
    fp = fingerprint(A())
    assert fp["t"] == "opaque" and fp["struct"] == "A"
    assert fp["exact"] is None


def test_nan_stats_recorded_without_hashing():
    a = np.array([np.nan, 1.0, np.inf])
    fp = fingerprint(a)
    assert fp["stats"]["n_nan"] == 1 and fp["stats"]["n_inf"] == 1
    assert fp["stats"]["min"] == 1.0
