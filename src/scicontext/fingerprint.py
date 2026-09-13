"""Structure fingerprints: detect value STRUCTURE, not data contents.

Arrays contribute shape/dtype and lightweight numeric stats (n, min, max,
sum, nan/inf counts) - never byte-level content hashing above a tiny
threshold, so nothing large is ever materialized. Containers contribute
recursive skeletons plus key-agnostic/order signatures built from item
structure and scalar values. Scalars keep their exact value: parameters
are the scientific fact worth recording. Third-party types are opaque.
"""
from __future__ import annotations

import hashlib

# Identity evidence budget: arrays within this size are byte-hashed; larger
# arrays carry NO identity digest (stats remain descriptive only). Matching
# statistics must never imply "identical".
EXACT_HASH_BYTES = 8 * 1024 * 1024
MAX_DEPTH = 2
MAX_CONTAINER_ITEMS = 1000


def _hash_bytes(*parts) -> str:
    digest = hashlib.sha256()
    for part in parts:
        if not isinstance(part, bytes):
            part = str(part).encode("utf-8", "surrogatepass")
        digest.update(part)
    return digest.hexdigest()


def _round9(value) -> float:
    return float(f"{value:.9g}")


def _array_fp(value, depth: int) -> dict:
    import numpy as np
    array = np.asarray(value)
    shape = list(array.shape)
    dtype = str(array.dtype)
    size_bytes = int(array.nbytes)
    stats = None
    if array.size and dtype != "object":
        try:
            if array.dtype.kind in "fc":
                finite = array[np.isfinite(array)]
                stats = {"n": int(array.size), "n_nan": int(np.isnan(array).sum()),
                         "n_inf": int(np.isinf(array).sum()),
                         "min": float(finite.min()) if finite.size else None,
                         "max": float(finite.max()) if finite.size else None,
                         "sum": float(finite.sum()) if finite.size else 0.0}
            else:
                stats = {"n": int(array.size), "n_nan": 0, "n_inf": 0,
                         "min": float(array.min()), "max": float(array.max()),
                         "sum": float(array.sum())}
        except Exception:
            stats = None
    exact = None
    if size_bytes <= EXACT_HASH_BYTES and dtype != "object":
        try:
            exact = _hash_bytes(f"{shape}|{dtype}|", np.ascontiguousarray(array).tobytes())
        except Exception:
            exact = None
    # Over-budget arrays: no identity digest. Stats are descriptive; they are
    # never used as equality evidence (relations treats missing content as
    # unknown, not equal).
    return {"t": "ndarray", "shape": shape, "dtype": dtype, "stats": stats,
            "struct": f"ndarray:{shape}:{dtype}", "exact": exact, "content": exact,
            "bytes": size_bytes, "equiv": None, "multiset": None, "rev": None, "truncated": False}


def _item_key(fp: dict) -> str:
    """Container item identity: exact bytes when small, otherwise content digest."""
    return fp.get("exact") if fp.get("exact") is not None else (fp.get("content") or fp.get("struct") or "")


def _sequence_fp(value, depth: int) -> dict:
    if depth > MAX_DEPTH:
        return {"t": "seq", "struct": "seq|depth-cap", "exact": None, "equiv": None,
                "multiset": None, "rev": None, "bytes": 0, "stats": None, "truncated": True}
    items = [_fingerprint(item, depth + 1) for item in value]
    exact = _hash_bytes(*[_item_key(item) for item in items])
    multiset = _hash_bytes(*sorted(_item_key(item) for item in items))
    rev = _hash_bytes(*[_item_key(item) for item in reversed(items)])
    struct = _hash_bytes(*[item["struct"] for item in items])
    return {"t": "seq", "struct": struct, "exact": exact, "content": exact, "equiv": None,
            "multiset": multiset, "rev": rev, "bytes": 0, "stats": None, "truncated": False}


def _dict_fp(value: dict, depth: int) -> dict:
    if depth > MAX_DEPTH:
        return {"t": "dict", "struct": "dict|depth-cap", "exact": None, "equiv": None,
                "multiset": None, "rev": None, "bytes": 0, "stats": None, "truncated": True}
    items = sorted(((_fingerprint(key, depth + 1), _fingerprint(val, depth + 1))
                     for key, val in value.items()),
                   key=lambda pair: _item_key(pair[0]) + "|" + pair[1].get("struct", ""))
    exact = _hash_bytes(*[f"{_item_key(k)}:{_item_key(v)}" for k, v in items])
    multiset = _hash_bytes(*sorted(_item_key(v) for _, v in items))
    struct = _hash_bytes(*sorted(f"{k['struct']}:{v['struct']}" for k, v in items))
    return {"t": "dict", "struct": struct, "exact": exact, "content": exact, "equiv": None,
            "multiset": multiset, "rev": None, "bytes": 0, "stats": None, "truncated": False}


def _scalar_fp(value) -> dict:
    if isinstance(value, float):
        text = repr(value)
        return {"t": "scalar", "struct": "float", "exact": text, "content": text,
                "equiv": format(value, ".12g"), "multiset": format(value, ".12g"),
                "rev": None, "bytes": 8, "stats": None, "truncated": False}
    if isinstance(value, str):
        return {"t": "scalar", "struct": "str", "exact": value, "content": value, "equiv": value,
                "multiset": value, "rev": None, "bytes": len(value.encode("utf-8", "surrogatepass")),
                "stats": None, "truncated": False}
    text = repr(value)
    return {"t": "scalar", "struct": type(value).__name__, "exact": text, "content": text, "equiv": text,
            "multiset": text, "rev": None, "bytes": 0, "stats": None, "truncated": False}


def _fingerprint(value, depth: int = 0) -> dict:
    try:
        import numpy as np
        if isinstance(value, np.generic):
            value = value.item()
    except (ImportError, TypeError):
        pass
    if value is None or isinstance(value, (bool, int, float, str)):
        return _scalar_fp(value)
    if isinstance(value, (list, tuple)):
        return _sequence_fp(value[:MAX_CONTAINER_ITEMS], depth)
    if isinstance(value, (set, frozenset)):
        return _sequence_fp(sorted(list(value)[:MAX_CONTAINER_ITEMS], key=lambda v: repr(type(v)) + str(v)), depth)
    if isinstance(value, dict):
        return _dict_fp(dict(list(value.items())[:MAX_CONTAINER_ITEMS]), depth)
    try:
        import numpy as np
        if isinstance(value, np.ndarray):
            return _array_fp(value, depth)
    except ImportError:
        pass
    root = (type(value).__module__ or "").split(".")[0]
    if root not in {"builtins", "numpy"}:
        return {"t": "opaque", "struct": type(value).__name__, "exact": None, "equiv": None,
                "multiset": None, "rev": None, "bytes": 0, "stats": None, "truncated": False}
    if hasattr(value, "__dict__") and depth <= MAX_DEPTH:
        return _dict_fp(vars(value), depth + 1)
    return {"t": "opaque", "struct": type(value).__name__, "exact": None, "equiv": None,
            "multiset": None, "rev": None, "bytes": 0, "stats": None, "truncated": False}


def fingerprint(value) -> dict:
    """Structure fingerprint; deterministic across runs and processes."""
    return _fingerprint(value, 0)
