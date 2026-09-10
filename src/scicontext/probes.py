"""Run a small declared set of independent Python probes with GNU timeout."""
from __future__ import annotations

import concurrent.futures
import math
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

from .io import digest_file, write_json


def _preview(path: Path, limit: int) -> str:
    if not path.is_file():
        return ""
    with path.open("rb") as stream:
        if path.stat().st_size <= limit:
            return stream.read(limit).decode("utf-8", errors="replace")
        head = stream.read(limit // 2)
        stream.seek(-limit // 2, 2)
        tail = stream.read(limit // 2)
    return head.decode("utf-8", errors="replace") + "\n[truncated]\n" + tail.decode("utf-8", errors="replace")


def run_probes(specs: list[dict], root: Path, scratch: Path, seconds: float,
               per_probe_seconds: float = 45.0) -> list[dict]:
    if not math.isfinite(seconds) or seconds <= 0:
        raise ValueError("Probe phase requires a positive finite allowance")
    if not math.isfinite(per_probe_seconds) or per_probe_seconds <= 0:
        raise ValueError("Per-probe limit requires a positive finite allowance")
    if len(specs) > 2:
        raise ValueError("At most two independent probes are supported")
    root, scratch = root.resolve(), scratch.resolve()
    ids = [p["id"] for p in specs]
    if len(set(ids)) != len(ids) or any(not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", i) for i in ids):
        raise ValueError("Probe IDs must be unique safe names")
    phase_started = time.monotonic()
    deadline = phase_started + seconds

    def execute(spec):
        start = time.monotonic()
        destination = scratch / "probe-results" / spec["id"]
        destination.mkdir(parents=True, exist_ok=True)
        artifact = (destination / "receipt.json").relative_to(scratch).as_posix()
        receipt = {"id": spec["id"], "claim_ids": spec["claim_ids"], "description": spec["description"],
                   "status": "not_run", "exit_code": None, "duration_seconds": 0.0,
                   "started_offset_seconds": start - phase_started,
                   "script_sha256": None, "artifact": artifact}
        try:
            relative = Path(spec["script"])
            if (relative.is_absolute() or relative.suffix != ".py" or "\\" in spec["script"]
                    or any(x.startswith(".") or x == ".." for x in relative.parts)):
                raise ValueError("Probe script must be a relative Python file under scratch")
            source = scratch / relative
            if (any((scratch.joinpath(*relative.parts[:i])).is_symlink() for i in range(1, len(relative.parts) + 1))
                    or not source.resolve().is_relative_to(scratch) or source.stat().st_size > 32768):
                raise ValueError("Probe script is outside scratch or exceeds the size limit")
            # Preserve exactly the script used by this execution separately from outputs.
            copied = destination / "script.py"
            shutil.copyfile(source, copied)
            receipt["script_sha256"] = digest_file(copied)
            allowance = min(per_probe_seconds, deadline - time.monotonic())
            if allowance <= 3:
                receipt["reason"] = "insufficient_phase_time"
                return receipt
            receipt["allowance_seconds"] = allowance
            command = ["timeout", "--signal=TERM", "--kill-after=3s", f"{allowance - 3}s", sys.executable, str(copied)]
            env = {**os.environ, "PYTHONPATH": str(root) + ":" + str(root / "source"),
                   "PYTHONDONTWRITEBYTECODE": "1", "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1"}
            with (destination / "stdout.txt").open("w") as stdout, (destination / "stderr.txt").open("w") as stderr:
                result = subprocess.run(command, cwd=destination, env=env, stdout=stdout, stderr=stderr)
            receipt["exit_code"] = result.returncode
            receipt["status"] = "timeout" if result.returncode in {124, 137} else "completed" if result.returncode == 0 else "failed"
        except subprocess.TimeoutExpired:
            receipt["status"] = "timeout"
        except (OSError, ValueError) as error:
            receipt.update(status="failed", error=f"{type(error).__name__}: {error}")
        finally:
            receipt["duration_seconds"] = time.monotonic() - start
            receipt["finished_offset_seconds"] = time.monotonic() - phase_started
            receipt["stdout_excerpt"] = _preview(destination / "stdout.txt", 1400)
            receipt["stderr_excerpt"] = _preview(destination / "stderr.txt", 900)
            write_json(destination / "receipt.json", receipt)
        return receipt

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        return list(pool.map(execute, specs))
