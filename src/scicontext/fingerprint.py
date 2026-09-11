"""Canonical value fingerprints for observed quantities.

Fingerprints are deterministic byte-level digests used to classify relations
between call instances: identical, equivalent (scale-free), key-agnostic
(relabeled), reversed, and structural (isomorphism candidates). Every digest
field is a sha256 hex string or None; ``truncated`` marks values that exceeded
the byte budget and were reduced to shape/dtype evidence only.
"""
from __future__ import annotations

import hashlib

FINGERPRINT_BYTE_BUDGET = 64 * 1024 * 1024
_MAX_DEPTH = 2


def _hash_bytes(*parts) -> str:
    digest = hashlib.sha256()
    for part in parts:
        if not isinstance(part, bytes):
            part = str(part).encode("utf-8", "surrogatepass")
        digest.update(part)
    return digest.hexdigest()


def _ndarray_fp(value, budget: int, depth: int) -> dict:
    import numpy as np
    array = np.asarray(value)
    shape, dtype = array.shape, str(array.dtype)
    size_bytes = int(array.nbytes)
    if dtype == "object":
        return {"t": "ndarray", "exact": "object-dtype", "equiv": "object-dtype",
                "multiset": None, "rev": None, "struct": _hash_bytes(f"{shape}|{dtype}|struct"),
                "bytes": size_bytes, "truncated": False}
    truncated = size_bytes > budget
    if not truncated:
        contiguous = np.ascontiguousarray(array)
        exact = _hash_bytes(f"{shape}|{dtype}|", contiguous.tobytes())
    else:
        exact = None
    scale = 1.0
    try:
        finite = np.abs(array[np.isfinite(array)])
        scale = float(np.max(finite)) if finite.size else 1.0
    except TypeError:
        scale = 1.0
    if scale == 0.0:
        scale = 1.0
    rounded = np.round(array / scale, 9) if scale != 1.0 else array
    contiguous = np.ascontiguousarray(rounded)
    equiv = _hash_bytes(f"{shape}|{dtype}|", contiguous.tobytes()) if not truncated else None
    flat = np.sort(contiguous.ravel())
    multiset = _hash_bytes(f"{shape}|{dtype}|", np.ascontiguousarray(flat).tobytes()) if not truncated else None
    rev = _hash_bytes(f"{shape}|{dtype}|", np.ascontiguousarray(array[::-1]).tobytes()) if not truncated else None
    return {"t": "ndarray", "exact": exact, "equiv": equiv, "multiset": multiset, "rev": rev,
            "struct": _hash_bytes(f"{shape}|{dtype}|struct"), "bytes": size_bytes, "truncated": truncated}


def _series_fp(value, budget: int, depth: int) -> dict:
    values = _ndarray_fp(value.to_numpy(), budget, depth) if hasattr(value, "to_numpy") else _ndarray_fp(list(value), budget, depth)
    index = _fingerprint(list(value.index), budget, depth + 1)
    values.update({"t": "series", "index_exact": index["exact"], "index_struct": index["struct"]})
    return values


def _dict_fp(value: dict, budget: int, depth: int) -> dict:
    if depth > _MAX_DEPTH:
        return {"t": "dict", "exact": None, "equiv": None, "multiset": None, "rev": None,
                "struct": _hash_bytes("dict|depth-cap"), "bytes": 0, "truncated": True}
    items = sorted((_fingerprint(key, budget, depth + 1)["exact"] or str(key), _fingerprint(val, budget, depth + 1))
                   for key, val in value.items())
    exact = _hash_bytes(*[f"{k}:{v['exact']}" for k, v in items])
    equiv = _hash_bytes(*[f"{k}:{v['equiv'] or v['exact']}" for k, v in items])
    multiset = _hash_bytes(*sorted(v["exact"] for _, v in items))
    struct = _hash_bytes(*sorted(f"{k}:{v['struct']}" for k, v in items))
    return {"t": "dict", "exact": exact, "equiv": equiv, "multiset": multiset, "rev": None,
            "struct": struct, "bytes": 0, "truncated": False}


def _sequence_fp(value, budget: int, depth: int) -> dict:
    if depth > _MAX_DEPTH:
        return {"t": "seq", "exact": None, "equiv": None, "multiset": None, "rev": None,
                "struct": _hash_bytes("seq|depth-cap"), "bytes": 0, "truncated": True}
    items = [_fingerprint(item, budget, depth + 1) for item in value]
    exact = _hash_bytes(*[v["exact"] for v in items])
    equiv = _hash_bytes(*[v["equiv"] or v["exact"] for v in items])
    multiset = _hash_bytes(*sorted(v["exact"] for v in items))
    rev = _hash_bytes(*[v["exact"] for v in reversed(items)])
    struct = _hash_bytes(*[v["struct"] for v in items])
    return {"t": "seq", "exact": exact, "equiv": equiv, "multiset": multiset, "rev": rev,
            "struct": struct, "bytes": 0, "truncated": False}


def _scalar_fp(value) -> dict:
    if isinstance(value, float):
        return {"t": "scalar", "exact": repr(value), "equiv": format(value, ".12g"), "multiset": format(value, ".12g"),
                "rev": None, "struct": "float", "bytes": 8, "truncated": False}
    if isinstance(value, str):
        return {"t": "scalar", "exact": value, "equiv": value, "multiset": value, "rev": None,
                "struct": "str", "bytes": len(value.encode("utf-8", "surrogatepass")), "truncated": False}
    text = repr(value)
    return {"t": "scalar", "exact": text, "equiv": text, "multiset": text, "rev": None,
            "struct": type(value).__name__, "bytes": 0, "truncated": False}


def _object_fp(value, budget: int, depth: int) -> dict:
    if hasattr(value, "__dict__"):
        inner = _dict_fp(vars(value), budget, depth + 1)
        inner.update({"t": "obj", "struct": _hash_bytes(type(value).__name__, inner["struct"])})
        return inner
    return {"t": "opaque", "exact": f"opaque:{type(value).__name__}", "equiv": f"opaque:{type(value).__name__}",
            "multiset": None, "rev": None, "struct": type(value).__name__, "bytes": 0, "truncated": False}


def _fingerprint(value, budget: int = FINGERPRINT_BYTE_BUDGET, depth: int = 0) -> dict:
    if value is None or isinstance(value, (bool, int, float, str)):
        return _scalar_fp(value)
    if isinstance(value, (list, tuple)):
        return _sequence_fp(value, budget, depth)
    if isinstance(value, (set, frozenset)):
        return _sequence_fp(sorted(value, key=lambda v: repr(type(v)) + str(v)), budget, depth)
    if isinstance(value, dict):
        return _dict_fp(value, budget, depth)
    try:
        import numpy as np
        if isinstance(value, np.ndarray):
            return _ndarray_fp(value, budget, depth)
    except ImportError:
        pass
    module = type(value).__module__ or ""
    if module.startswith(("pandas", "xarray")) or type(value).__name__ in {"Series", "DataFrame", "Index"}:
        try:
            return _series_fp(value, budget, depth)
        except Exception:
            pass
    return _object_fp(value, budget, depth)


def fingerprint(value, budget: int = FINGERPRINT_BYTE_BUDGET) -> dict:
    """Public entry point; deterministic across runs and processes."""
    return _fingerprint(value, budget, 0)
