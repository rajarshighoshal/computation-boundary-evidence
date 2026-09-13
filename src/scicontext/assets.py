"""Fetch verified harness/tool assets without installing into scientific runtimes."""
from __future__ import annotations

import base64
import fcntl
import hashlib
import json
import subprocess
import tarfile
import urllib.request
import zipfile
from functools import wraps
from pathlib import Path

from .io import digest_file, digest_json, read_json, write_json

CODEX_VERSION = "0.153.4"
HELPER_PACKAGES = ["jsonschema==4.26.0", "attrs==26.1.0", "jsonschema-specifications==2025.9.1", "referencing==0.37.0", "rpds-py==2026.6.3", "typing-extensions==4.16.0",
                   "pint==0.24.4", "flexcache==0.3", "flexparser==0.4", "platformdirs==4.11.8",
                   "sympy==1.14.0", "mpmath==1.3.0", "fortls==3.2.2", "json5==0.15.0", "packaging==26.0",
                   "tree-sitter==0.25.2", "tree-sitter-c==0.24.2", "tree-sitter-cpp==0.23.4",
                   "tree-sitter-fortran==0.6.0", "tree-sitter-matlab==1.3.1", "Cython==3.3.0"]


def _locked_asset(builder):
    """Serialize cache validation and creation across independent Pier processes.

    Locks live outside the verified asset directories and release on process
    exit. Different builders may run together; no unneeded variants are fetched.
    """
    @wraps(builder)
    def locked(cache: Path, *args, **kwargs) -> Path:
        cache.mkdir(parents=True, exist_ok=True)
        with (cache / f".{builder.__name__}.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                return builder(cache, *args, **kwargs)
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)
    return locked


@_locked_asset
def prepare_codex(cache: Path, architecture: str) -> Path:
    if architecture not in {"arm64", "x64"}:
        raise ValueError("Harness architecture must be arm64 or x64")
    destination = cache / f"codex-{CODEX_VERSION}-{architecture}"
    receipt_path = destination / "receipt.json"
    if receipt_path.is_file():
        receipt = read_json(receipt_path)
        if all(digest_file(destination / p) == h for p, h in receipt["files"].items()):
            return destination / "package"
        raise ValueError("Cached Codex files changed; refusing to use them")
    if destination.exists():
        raise ValueError(f"Incomplete harness cache requires inspection: {destination}")
    url = f"https://registry.npmjs.org/@openai%2fcodex/{CODEX_VERSION}-linux-{architecture}"
    with urllib.request.urlopen(url, timeout=60) as response:
        metadata = json.load(response)
    tar_url = metadata["dist"]["tarball"]
    if not tar_url.startswith("https://registry.npmjs.org/@openai/codex/"):
        raise ValueError("Unexpected npm artifact URL")
    with urllib.request.urlopen(tar_url, timeout=120) as response:
        blob = response.read()
    integrity = "sha512-" + base64.b64encode(hashlib.sha512(blob).digest()).decode()
    if integrity != metadata["dist"]["integrity"]:
        raise ValueError("Codex npm integrity mismatch")
    destination.mkdir(parents=True)
    archive = destination / "package.tgz"
    archive.write_bytes(blob)
    with tarfile.open(archive) as tar:
        tar.extractall(destination, filter="data")
    files = {str(p.relative_to(destination)): digest_file(p) for p in sorted((destination / "package").rglob("*")) if p.is_file()}
    write_json(receipt_path, {"version": CODEX_VERSION, "architecture": architecture, "url": tar_url, "integrity": integrity, "files": files})
    return destination / "package"


@_locked_asset
def prepare_helpers(cache: Path, python_minor: str) -> Path:
    if python_minor not in {"310", "311", "312", "313"}:
        raise ValueError(f"Unsupported task helper Python: {python_minor}")
    # pip's cross-platform download still evaluates some dependency markers
    # against its host interpreter. Pin the complete helper closure explicitly,
    # including typing-extensions needed by the scientific guests' Python 3.11.
    # rpds' calendar-version release dropped Python 3.10 wheels. Keep the
    # supported 3.10 guest on its compatible release, without changing 3.11+.
    packages = ["rpds-py==0.30.0" if python_minor == "310" and p.startswith("rpds-py==") else p
                for p in HELPER_PACKAGES]
    identity = digest_json(packages)[:12]
    destination = cache / f"helper-deps-cp{python_minor}-{identity}"
    receipt = destination / "receipt.json"
    if receipt.is_file():
        recorded = read_json(receipt)
        if not all((destination / p).is_file() and digest_file(destination / p) == h for p, h in recorded["files"].items()):
            raise ValueError("Helper dependency cache changed")
        return destination
    wheels = cache / f"helper-wheels-cp{python_minor}-{identity}"
    wheels.mkdir(parents=True, exist_ok=True)
    subprocess.run(["uvx", "--from", "pip", "pip", "download", "--dest", str(wheels), "--only-binary=:all:", "--no-deps",
                    "--platform", "manylinux2014_x86_64", "--python-version", python_minor,
                    "--implementation", "cp", "--abi", f"cp{python_minor}", *packages], check=True)
    destination.mkdir(parents=True, exist_ok=True)
    for wheel in sorted(wheels.glob("*.whl")):
        with zipfile.ZipFile(wheel) as archive:
            for member in archive.infolist():
                target = (destination / member.filename).resolve()
                if not target.is_relative_to(destination.resolve()):
                    raise ValueError("Unsafe wheel path")
            archive.extractall(destination)
    files = {str(p.relative_to(destination)): digest_file(p) for p in sorted(destination.rglob("*")) if p.is_file() and p != receipt}
    write_json(receipt, {"python": python_minor, "packages": packages, "wheels": {p.name: digest_file(p) for p in wheels.glob("*.whl")}, "files": files})
    return destination
