"""Run one guest command and clean its descendants, using only Python 3.11 stdlib.

Usage: python -m scicontext.supervise SPEC_JSON

Strict supervision requires a dedicated Linux process with no existing children.
Linux adopts orphaned descendants as a child subreaper. Signals are sent only to
verified direct children: their PIDs cannot be reused before we reap them. Other
POSIX systems offer an explicitly opt-in, limited process-group fallback.
"""

from __future__ import annotations

import ctypes
from contextlib import ExitStack
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
import time
from typing import Any


@dataclass(frozen=True)
class ProcessIdentity:
    pid: int
    start_ticks: int
    parent_pid: int
    state: str

    @property
    def key(self) -> tuple[int, int]:
        return self.pid, self.start_ticks

    def record(self) -> dict[str, int]:
        return {"pid": self.pid, "start_ticks": self.start_ticks}


def _read_identity(pid: int) -> ProcessIdentity | None:
    try:
        stat = Path(f"/proc/{pid}/stat").read_text()
    except (FileNotFoundError, ProcessLookupError):
        return None
    # comm can contain spaces and parentheses; fields after its final ')' start
    # at field 3 (state). starttime is field 22.
    fields = stat[stat.rfind(")") + 2 :].split()
    return ProcessIdentity(pid, int(fields[19]), int(fields[1]), fields[0])


def _process_snapshot() -> dict[int, ProcessIdentity]:
    result = {}
    for entry in os.scandir("/proc"):
        if not entry.name.isdecimal():
            continue
        try:
            identity = _read_identity(int(entry.name))
        except PermissionError:
            # Foreign users' entries may be hidden. The dedicated supervisor's
            # own children must remain readable; /proc/<self>/children below
            # checks that none of them were silently omitted.
            continue
        if identity is not None:
            result[identity.pid] = identity
    own_children = Path(f"/proc/{os.getpid()}/task/{os.getpid()}/children")
    for child in own_children.read_text().split():
        pid = int(child)
        if pid not in result:
            identity = _read_identity(pid)
            if identity is not None:
                result[pid] = identity
    return result


class LinuxOwner:
    guarantee = "linux_subreaper"

    def __init__(self) -> None:
        self.pid = os.getpid()
        snapshot = _process_snapshot()
        if any(item.parent_pid == self.pid for item in snapshot.values()):
            raise RuntimeError("Linux supervision requires no preexisting children")
        libc = ctypes.CDLL(None, use_errno=True)
        prctl = libc.prctl
        prctl.restype = ctypes.c_int
        if prctl(36, 1, 0, 0, 0) != 0:  # PR_SET_CHILD_SUBREAPER
            error = ctypes.get_errno()
            raise OSError(error, "cannot enable Linux child subreaper")
        enabled = ctypes.c_int()
        if prctl(37, ctypes.byref(enabled), 0, 0, 0) != 0 or enabled.value != 1:
            raise RuntimeError("Linux child subreaper could not be verified")
        self.known: dict[tuple[int, int], ProcessIdentity] = {}
        self.term: set[tuple[int, int]] = set()
        self.kill: set[tuple[int, int]] = set()
        self.errors: list[dict[str, Any]] = []

    def refresh(self) -> dict[int, ProcessIdentity]:
        snapshot = _process_snapshot()
        owned = {
            pid: item for pid, item in snapshot.items()
            if item.parent_pid == self.pid
            or item.key in self.known
        }
        # Include descendants while their original parent is still alive. Once
        # an ancestor exits, even double-forked / setsid children are adopted.
        changed = True
        while changed:
            changed = False
            for pid, item in snapshot.items():
                if pid not in owned and item.parent_pid in owned:
                    owned[pid] = item
                    changed = True
        for item in owned.values():
            self.known[item.key] = item
        return owned

    def signal_child(self, item: ProcessIdentity, signum: int) -> None:
        current = _read_identity(item.pid)
        if (current is None or current.key != item.key
                or current.parent_pid != self.pid or current.state == "Z"):
            return
        # No reaping occurs between identity check and signal. This direct-child
        # restriction avoids the pidfd availability problem under emulation and
        # prevents a recycled foreign PID from being signalled.
        try:
            os.kill(item.pid, signum)
        except ProcessLookupError:
            return
        except OSError as exc:
            self.errors.append({**item.record(), "signal": signum, "errno": exc.errno})
            return
        (self.kill if signum == signal.SIGKILL else self.term).add(item.key)

    def reap(self, owned: dict[int, ProcessIdentity], process: subprocess.Popen[bytes]) -> None:
        process.poll()
        for item in owned.values():
            if item.pid == process.pid or item.parent_pid != self.pid:
                continue
            current = _read_identity(item.pid)
            if current is None or current.key != item.key:
                continue
            try:
                os.waitpid(item.pid, os.WNOHANG)
            except ChildProcessError:
                pass

    def cleanup(self, process: subprocess.Popen[bytes], deadline: float, grace: float) -> dict[str, Any]:
        cleanup_start = time.monotonic()
        cleanup_deadline = min(deadline, cleanup_start + grace)
        kill_at = cleanup_start + max(0, cleanup_deadline - cleanup_start) / 2
        owned = self.refresh()
        while True:
            self.reap(owned, process)
            owned = self.refresh()
            if not owned:
                break
            now = time.monotonic()
            signum = signal.SIGKILL if now >= kill_at else signal.SIGTERM
            for item in owned.values():
                sent = self.kill if signum == signal.SIGKILL else self.term
                if item.key not in sent and item.parent_pid == self.pid:
                    self.signal_child(item, signum)
            if now >= cleanup_deadline:
                # The final sweep still sends SIGKILL, but does not invent an
                # unbounded grace interval beyond the supplied total budget.
                break
            time.sleep(min(0.01, max(0, cleanup_deadline - time.monotonic())))
            owned = self.refresh()
        self.reap(owned, process)
        remaining = self.refresh()
        return {
            "guarantee": self.guarantee,
            "success": not remaining and not self.errors,
            "tracked": [self.known[key].record() for key in sorted(self.known)],
            "sigterm": [{"pid": pid, "start_ticks": start} for pid, start in sorted(self.term)],
            "sigkill": [{"pid": pid, "start_ticks": start} for pid, start in sorted(self.kill)],
            "survivors": [item.record() for item in remaining.values()],
            "errors": self.errors,
            "duration_seconds": time.monotonic() - cleanup_start,
        }


class PosixGroupOwner:
    guarantee = "process_group_only"

    def refresh(self) -> dict[int, ProcessIdentity]:
        return {}

    def cleanup(self, process: subprocess.Popen[bytes], deadline: float, grace: float) -> dict[str, Any]:
        cleanup_start = time.monotonic()
        cleanup_deadline = min(deadline, cleanup_start + grace)
        errors = []
        sent = []
        for signum in (signal.SIGTERM, signal.SIGKILL):
            # Reap a completed leader first; Darwin may report EPERM when the
            # only remaining group member is its unreaped zombie.
            process.poll()
            try:
                os.killpg(process.pid, signum)
                sent.append(signum)
            except ProcessLookupError:
                break
            except OSError as exc:
                errors.append({"signal": signum, "errno": exc.errno})
            if signum == signal.SIGTERM:
                time.sleep(max(0, min(grace / 2, cleanup_deadline - time.monotonic())))
        while process.poll() is None and time.monotonic() < cleanup_deadline:
            time.sleep(min(0.01, max(0, cleanup_deadline - time.monotonic())))
        return {
            "guarantee": self.guarantee,
            "success": process.poll() is not None and not errors,
            "tracked": [{"pid": process.pid, "start_ticks": None}],
            "signals": sent,
            "survivors": [] if process.poll() is not None else [{"pid": process.pid}],
            "errors": errors,
            "limitation": "Escaped process groups, including setsid descendants, are not covered.",
            "duration_seconds": time.monotonic() - cleanup_start,
        }


def _positive_number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a positive finite number")
    value = float(value)
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{field} must be a positive finite number")
    return value


def _validate_spec(spec: Any) -> dict[str, Any]:
    if not isinstance(spec, dict):
        raise ValueError("spec must be a JSON object")
    command = spec.get("command")
    if (not isinstance(command, list) or not command
            or any(not isinstance(item, str) or "\0" in item for item in command)):
        raise ValueError("command must be a nonempty list of strings without NULs")
    if not isinstance(spec.get("cwd"), str) or not Path(spec["cwd"]).is_dir():
        raise ValueError("cwd must name an existing directory")
    env = spec.get("env", {})
    if (not isinstance(env, dict) or any(
        not isinstance(key, str) or not isinstance(value, str)
        or not key or "=" in key or "\0" in key or "\0" in value
        for key, value in env.items()
    )):
        raise ValueError("env must map valid names to string values")
    timeout = _positive_number(spec.get("timeout_seconds"), "timeout_seconds")
    grace = _positive_number(
        spec.get("termination_grace_seconds", min(0.5, max(0.02, timeout * 0.1), timeout / 2)),
        "termination_grace_seconds",
    )
    if grace >= timeout:
        raise ValueError("termination_grace_seconds must be smaller than timeout_seconds")
    strict = spec.get("strict_descendants", True)
    if not isinstance(strict, bool):
        raise ValueError("strict_descendants must be a boolean")
    paths = {}
    for field in ("stdout_path", "stderr_path", "result_path", "pid_path"):
        value = spec.get(field)
        if value is None and field == "pid_path":
            continue
        if not isinstance(value, str) or not value:
            raise ValueError(f"{field} must name an output file")
        path = Path(value).absolute()
        if path.exists() or path.is_symlink():
            raise FileExistsError(f"refusing to overwrite {field}")
        paths[field] = path
    if len({path.resolve() for path in paths.values()}) != len(paths):
        raise ValueError("output paths must be distinct")
    stdin_path = spec.get("stdin_path")
    if stdin_path is not None:
        if not isinstance(stdin_path, str) or not Path(stdin_path).is_file():
            raise ValueError("stdin_path must name an existing regular file")
        paths["stdin_path"] = Path(stdin_path).absolute()
    control_directory = spec.get("control_directory")
    if control_directory is not None:
        if not isinstance(control_directory, str) or not control_directory:
            raise ValueError("control_directory must name a directory")
        paths["control_directory"] = Path(control_directory).absolute()
    return dict(spec, env=env, timeout_seconds=timeout, termination_grace_seconds=grace,
                strict_descendants=strict, **paths)


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=f".{path.name}.", delete=False) as handle:
            temporary = Path(handle.name)
            json.dump(value, handle, sort_keys=True, indent=2, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def supervise(raw_spec: dict[str, Any]) -> dict[str, Any]:
    spec = _validate_spec(raw_spec)
    started = time.monotonic()
    timeout = spec["timeout_seconds"]
    grace = spec["termination_grace_seconds"]
    hard_deadline = started + timeout
    execution_deadline = hard_deadline - grace
    result: dict[str, Any] = {
        "schema_version": 1, "status": "setup_error", "exit_code": None,
        "supervisor_pid": os.getpid(), "started_at": _utc_now(),
        "started_monotonic": started, "timeout_seconds": timeout,
        "execution_timeout_seconds": timeout - grace,
        "termination_grace_seconds": grace, "strict_descendants": spec["strict_descendants"],
    }
    interrupted: list[int] = []

    def interrupt(signum: int, _frame: Any) -> None:
        if not interrupted:
            interrupted.append(signum)

    handlers = {sig: signal.signal(sig, interrupt) for sig in (signal.SIGTERM, signal.SIGINT)}
    old_sigchld = signal.getsignal(signal.SIGCHLD)
    signal.signal(signal.SIGCHLD, signal.SIG_DFL)
    process: subprocess.Popen[bytes] | None = None
    owner: LinuxOwner | PosixGroupOwner | None = None
    control: socket.socket | None = None
    control_dir: Path | None = None
    try:
        if sys.platform == "linux":
            # Never silently downgrade a broken Linux ownership boundary.
            owner = LinuxOwner()
        elif os.name == "posix" and not spec["strict_descendants"]:
            owner = PosixGroupOwner()
        else:
            raise RuntimeError("strict descendant supervision requires Linux child-subreaper support")
        if sys.platform == "linux" and spec.get("pid_path") is not None:
            # Cancellation uses an owned endpoint, never an arbitrary PID kill.
            # In particular pidfd_open is unavailable under some emulators.
            spec["result_path"].parent.mkdir(parents=True, exist_ok=True)
            control_parent = spec.get("control_directory", spec["pid_path"].parent)
            control_parent.mkdir(parents=True, exist_ok=True)
            control_dir = Path(tempfile.mkdtemp(prefix=".supervise-", dir=control_parent))
            control = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
            control.bind(str(control_dir / "control"))
            control.setblocking(False)
        for field in ("stdout_path", "stderr_path"):
            spec[field].parent.mkdir(parents=True, exist_ok=True)
        with ExitStack() as files:
            stdout = files.enter_context(spec["stdout_path"].open("xb"))
            stderr = files.enter_context(spec["stderr_path"].open("xb"))
            stdin = (files.enter_context(spec["stdin_path"].open("rb"))
                     if spec.get("stdin_path") is not None else subprocess.DEVNULL)
            if interrupted:
                result["status"] = "interrupted"
            elif time.monotonic() >= execution_deadline:
                result["status"] = "timed_out"
            else:
                process = subprocess.Popen(
                    spec["command"], cwd=spec["cwd"], env={**os.environ, **spec["env"]},
                    stdin=stdin, stdout=stdout, stderr=stderr, start_new_session=True,
                )
                result["command_pid"] = process.pid
                owned = owner.refresh()
                child = owned.get(process.pid)
                result["command_start_ticks"] = child.start_ticks if child else None
                if spec.get("pid_path") is not None:
                    _write_json(spec["pid_path"], {
                        "pid": os.getpid(), "supervisor_pid": os.getpid(),
                        "command_pid": process.pid,
                        "command_start_ticks": result["command_start_ticks"],
                        "start_time": (
                            _read_identity(os.getpid()).start_ticks if sys.platform == "linux" else None
                        ),
                        "control_path": str(control_dir / "control") if control_dir else None,
                        "result_path": str(spec["result_path"]),
                    })
                while True:
                    if control is not None:
                        try:
                            if control.recv(32) == b"terminate":
                                interrupt(signal.SIGTERM, None)
                        except BlockingIOError:
                            pass
                    owner.refresh()
                    returncode = process.poll()
                    if interrupted:
                        result["status"] = "interrupted"
                        break
                    if returncode is not None:
                        result["status"] = "completed" if returncode == 0 else "failed"
                        break
                    now = time.monotonic()
                    if now >= execution_deadline:
                        result["status"] = "timed_out"
                        break
                    time.sleep(min(0.01, execution_deadline - now))
    except Exception as exc:
        result["error"] = {"type": type(exc).__name__, "message": str(exc)}
    finally:
        try:
            if process is not None and owner is not None:
                result["cleanup"] = owner.cleanup(process, hard_deadline, grace)
                result["exit_code"] = process.poll()
                if not result["cleanup"]["success"]:
                    result["status_before_cleanup_failure"] = result["status"]
                    result["status"] = "cleanup_failed"
            else:
                result["cleanup"] = {
                    "success": True, "guarantee": owner.guarantee if owner else "unavailable",
                    "tracked": [], "survivors": [], "errors": [], "duration_seconds": 0.0,
                }
        except Exception as exc:
            result["status_before_cleanup_failure"] = result["status"]
            result["status"] = "cleanup_failed"
            result["cleanup"] = {"success": False, "error": str(exc), "guarantee": "unverified"}
        if interrupted:
            result["interruption_signal"] = interrupted[0]
            if result["status"] != "cleanup_failed":
                result["status"] = "interrupted"
        result["cleanup_complete"] = result["cleanup"]["success"]
        finished = time.monotonic()
        result.update(finished_at=_utc_now(), finished_monotonic=finished,
                      duration_seconds=finished - started)
        result["supervisor_exit_code"] = _result_exit_code(result)
        try:
            _write_json(spec["result_path"], result)
        finally:
            if control is not None:
                control.close()
            if control_dir is not None:
                (control_dir / "control").unlink(missing_ok=True)
                control_dir.rmdir()
            for sig, old in handlers.items():
                signal.signal(sig, old)
            signal.signal(signal.SIGCHLD, old_sigchld)
    return result


def _result_exit_code(result: dict[str, Any]) -> int:
    status = result["status"]
    if status == "cleanup_failed":
        return 125
    if result.get("interruption_signal") is not None:
        return 128 + result["interruption_signal"]
    if status == "completed":
        return 0
    if status == "timed_out":
        return 124
    if status == "failed" and result["exit_code"] is not None:
        code = result["exit_code"]
        return min(code, 255) if code > 0 else 128 - code
    return 2


def terminate_from_pidfile(path: str | Path) -> dict[str, Any]:
    """Request owned-supervisor cleanup and wait at most two seconds.

    The start-time check rejects stale receipts. Cancellation travels over a
    unique socket owned by that supervisor, so process exit/PID reuse between
    the check and request cannot signal a different process. No key material or
    arbitrary command can be sent through this endpoint.
    """
    started = time.monotonic()
    if sys.platform != "linux":
        raise RuntimeError("PID-file termination requires Linux identity verification")
    receipt = json.loads(Path(path).read_text())
    pid, start_time = receipt.get("pid"), receipt.get("start_time")
    if (isinstance(pid, bool) or not isinstance(pid, int) or pid <= 1
            or isinstance(start_time, bool) or not isinstance(start_time, int) or start_time <= 0):
        raise ValueError("PID receipt requires pid and Linux start_time")
    result_path = Path(receipt["result_path"])

    def completed() -> dict[str, Any] | None:
        if not result_path.exists():
            return None
        result = json.loads(result_path.read_text())
        if result.get("supervisor_pid") != pid or result.get("finished_monotonic") is None:
            raise RuntimeError("result does not identify the requested supervisor")
        return result

    existing = completed()
    if existing is not None:
        return {"status": "already_finished", "cleanup": existing.get("cleanup"),
                "supervisor_exit_code": existing.get("supervisor_exit_code")}
    live = _read_identity(pid)
    if live is None or live.start_ticks != start_time:
        raise RuntimeError("stale PID receipt: supervisor identity no longer matches")
    control_path = receipt.get("control_path")
    if not isinstance(control_path, str):
        raise ValueError("PID receipt does not contain a control endpoint")
    with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as connection:
        connection.settimeout(max(0.01, 2.0 - (time.monotonic() - started)))
        try:
            connection.sendto(b"terminate", control_path)
        except OSError:
            existing = completed()
            if existing is None:
                raise
    while time.monotonic() - started < 2.0:
        result = completed()
        live = _read_identity(pid)
        if result is not None and (live is None or live.start_ticks != start_time or live.state == "Z"):
            return {"status": "terminated", "cleanup": result.get("cleanup"),
                    "supervisor_exit_code": result.get("supervisor_exit_code")}
        time.sleep(0.01)
    return {"status": "termination_pending", "cleanup": None,
            "supervisor_exit_code": None}


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) == 2 and args[0] == "--terminate":
        try:
            receipt = terminate_from_pidfile(args[1])
            print(json.dumps(receipt, sort_keys=True))
            if receipt["status"] == "termination_pending":
                return 124
            return 0 if (receipt.get("cleanup") or {}).get("success") else 125
        except Exception as exc:
            print(f"supervisor: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 2
    if len(args) != 1:
        print("usage: python -m scicontext.supervise SPEC_JSON | --terminate PID_JSON", file=sys.stderr)
        return 2
    try:
        raw = json.loads(Path(args[0]).read_text())
        return supervise(raw)["supervisor_exit_code"]
    except Exception as exc:
        print(f"supervisor: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
