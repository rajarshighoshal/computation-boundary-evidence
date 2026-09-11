"""Small durable artifact primitives; no hidden state or environment discovery."""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

_DENIED_COMPONENTS = {
    "auth", "credentials", "secrets", "private", "private_tests", "verifier",
    "verifiers", "gold", "gold_patch", "gold_patches", "answers",
}
_DENIED_FILES = {"auth.json", "credentials.json", "credentials", "id_rsa", "id_ed25519", "secrets.json"}


def _safe_relative(path: str) -> str | None:
    """Reject absolute, hidden, traversal, or verifier/credential-adjacent paths."""
    if not path or "\\" in path or "\x00" in path or ":" in path:
        return "invalid relative path"
    parts = PurePosixPath(path).parts
    if PurePosixPath(path).is_absolute() or any(p in {".", ".."} or p.startswith(".") for p in parts):
        return "absolute, hidden, or traversal path"
    if not parts or any(p.lower() in _DENIED_COMPONENTS for p in parts):
        return "private, verifier, or credential path"
    name = parts[-1].lower()
    if name in _DENIED_FILES or name.endswith((".pem", ".key")) or re.search(r"(?:^|[_-])(private|verifier|credentials|secret)(?:[_-]|\.)", name):
        return "private, verifier, or credential file"
    return None


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def digest_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def digest_json(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def write_json(path: Path, value: object) -> None:
    """Atomic replacement of a single owned artifact, never a recursive operation."""
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n"
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def read_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as stream:
        result = json.load(stream, parse_constant=lambda x: (_ for _ in ()).throw(ValueError(f"Nonfinite JSON: {x}")))
    if not isinstance(result, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return result
