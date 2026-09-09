"""Restore the public release at explicit revisions and preserve integrity receipts."""
from __future__ import annotations

import csv
import re
import subprocess
import sys
from pathlib import Path

from .io import digest_file, digest_json, read_json, utc_now, write_json

RELEASE_URL = "https://github.com/OpenMOSS/SWE-bench-Science.git"
RELEASE_COMMIT = "42e7e97915ff7d73436a5d37b5cbe6b77e9c2a00"
DATASET_ID = "OpenMOSS-Team/SWE-bench-Science"
DATASET_REVISION = "d8bdbcb4ecb2b565686382459c815d2b6291fd31"


def run(command: list[str], cwd: Path | None = None) -> str:
    return subprocess.run(command, cwd=cwd, check=True, text=True, stdout=subprocess.PIPE).stdout.strip()


def task_rows(snapshot: Path) -> list[dict]:
    with (snapshot / "data/tasks.csv").open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    ids = [row["task_id"] for row in rows]
    if sorted(ids) != [f"{i:03d}" for i in range(1, 120)]:
        raise ValueError("Release must contain exactly 001..119 without duplicate IDs")
    for row in rows:
        if row["image_platform"] != "linux/amd64":
            raise ValueError(f"Unsupported release platform: {row['task_id']}")
        for name in ("environment_image", "verifier_image"):
            if not re.fullmatch(r"docker\.io/kevinxulearning/[^\s]+@sha256:[0-9a-f]{64}", row[name]):
                raise ValueError(f"Unpinned or unexpected {name}: {row['task_id']}")
    return rows


def prepare(workspace: Path, task_ids: list[str], *, allow_restricted: bool = False) -> dict:
    workspace = workspace.resolve()
    vendor = workspace / "vendor/swe-bench-science"
    snapshot = workspace / "data/release"
    if not vendor.exists():
        vendor.parent.mkdir(parents=True, exist_ok=True)
        run(["git", "clone", RELEASE_URL, str(vendor)])
        run(["git", "checkout", "--detach", RELEASE_COMMIT], vendor)
    if run(["git", "rev-parse", "HEAD"], vendor) != RELEASE_COMMIT:
        raise ValueError("Existing vendor checkout has another revision; refusing to overwrite it")
    if run(["git", "status", "--porcelain", "--untracked-files=no"], vendor):
        raise ValueError("Pinned vendor source is modified")
    try:
        from huggingface_hub import snapshot_download
    except ImportError as error:
        raise RuntimeError("Install scicontext[runner] to restore the dataset") from error
    snapshot_download(DATASET_ID, repo_type="dataset", revision=DATASET_REVISION,
                      local_dir=str(snapshot), token=False, max_workers=4)
    rows = task_rows(snapshot)
    by_id = {row["task_id"]: row for row in rows}
    if len(set(task_ids)) != len(task_ids) or any(t not in by_id for t in task_ids):
        raise ValueError("Invalid or duplicate task selection")
    gated = [t for t in task_ids if by_id[t]["restricted_license"].lower() == "true"]
    if gated and not allow_restricted:
        raise ValueError(f"Explicit restricted-license opt-in required for: {','.join(gated)}")
    # Materialize exact IDs. Never overwrite an unrelated selection directory.
    selection_key = digest_json({"task_ids": task_ids, "allow_restricted_licenses": allow_restricted})[:12]
    selected = workspace / "data/selections" / selection_key
    expected = {"task_ids": task_ids, "allow_restricted_licenses": allow_restricted}
    if selected.exists():
        if read_json(selected / "selection.json") != expected:
            raise ValueError("Existing materialized selection differs")
    else:
        command = [sys.executable, str(snapshot / "scripts/materialize.py"), "--task-id", ",".join(task_ids), "--output", str(selected)]
        if allow_restricted:
            command.append("--allow-restricted-licenses")
        run(command, snapshot)
    receipt = {
        "schema_version": "1.0", "recorded_at": utc_now(), "release_commit": RELEASE_COMMIT,
        "dataset_id": DATASET_ID, "dataset_revision": DATASET_REVISION,
        "table_sha256": digest_file(snapshot / "data/tasks.csv"),
        "selection_sha256": digest_file(selected / "selection.json"),
        "selection_path": str(selected), "task_ids": task_ids,
        "allow_restricted_licenses": allow_restricted,
        "tasks": [{k: by_id[t][k] for k in ("task_id", "repository_url", "base_commit", "environment_image", "verifier_image", "restricted_license")} for t in task_ids],
        "missing_base_commit_ids": [r["task_id"] for r in rows if not re.fullmatch(r"[0-9a-f]{40}", r["base_commit"])],
        "file_hashes": {str(p.relative_to(selected)): digest_file(p) for p in sorted(selected.rglob("*")) if p.is_file()},
    }
    write_json(workspace / "data/release-receipt.json", receipt)
    return receipt
