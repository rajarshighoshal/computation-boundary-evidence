from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time

import pytest

from scicontext import supervise


def make_spec(tmp_path, code, *, timeout=3.0, **extra):
    script = tmp_path / "command.py"
    script.write_text(code)
    spec = {
        "command": [sys.executable, str(script)], "cwd": str(tmp_path),
        "env": {"SUPERVISOR_TEST_VALUE": "present"}, "timeout_seconds": timeout,
        "stdout_path": str(tmp_path / "stdout.jsonl"),
        "stderr_path": str(tmp_path / "stderr.log"),
        "result_path": str(tmp_path / "result.json"),
        "pid_path": str(tmp_path / "pid.json"),
        "control_directory": tempfile.gettempdir(),
        "strict_descendants": sys.platform == "linux", **extra,
    }
    path = tmp_path / "spec.json"
    path.write_text(json.dumps(spec))
    return path, spec


def launch(spec_path):
    env = dict(os.environ)
    source = str(Path(supervise.__file__).resolve().parents[1])
    env["PYTHONPATH"] = source + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.Popen(
        [sys.executable, "-m", "scicontext.supervise", str(spec_path)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env,
    )


def finish(process, spec, *, expected_code):
    stdout, stderr = process.communicate(timeout=8)
    assert process.returncode == expected_code, (stdout, stderr)
    result = json.loads(Path(spec["result_path"]).read_text())
    assert result["supervisor_exit_code"] == expected_code
    assert result["cleanup"]["success"], result
    assert result["cleanup_complete"]
    assert result["finished_monotonic"] >= result["started_monotonic"]
    return result


def await_pid(path):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if path.exists():
            return json.loads(path.read_text())
        time.sleep(0.01)
    pytest.fail("supervisor did not publish its PID receipt")


def test_completed_preserves_raw_streams_and_environment(tmp_path):
    spec_path, spec = make_spec(tmp_path, """
import os,sys
sys.stdout.buffer.write(b'{"event":"test"}\\n\\xff')
sys.stderr.buffer.write(b'stderr-only\\n')
assert os.environ['SUPERVISOR_TEST_VALUE'] == 'present'
""")
    result = finish(launch(spec_path), spec, expected_code=0)
    assert result["status"] == "completed"
    assert result["exit_code"] == 0
    assert Path(spec["stdout_path"]).read_bytes() == b'{"event":"test"}\n\xff'
    assert Path(spec["stderr_path"]).read_bytes() == b"stderr-only\n"
    pid = json.loads(Path(spec["pid_path"]).read_text())
    assert pid["pid"] == pid["supervisor_pid"]
    assert pid["command_pid"] != pid["supervisor_pid"]
    if sys.platform == "linux":
        assert pid["start_time"] > 0
        assert pid["command_start_ticks"] > 0
        assert result["cleanup"]["guarantee"] == "linux_subreaper"
    else:
        assert result["cleanup"]["guarantee"] == "process_group_only"
        assert "setsid" in result["cleanup"]["limitation"]


def test_command_failure_keeps_exit_code(tmp_path):
    path, spec = make_spec(tmp_path, "import sys; print('before failure'); sys.exit(7)")
    result = finish(launch(path), spec, expected_code=7)
    assert result["status"] == "failed"
    assert result["exit_code"] == 7


def test_stdin_path_is_forwarded_without_reencoding(tmp_path):
    prompt = tmp_path / "prompt.txt"
    prompt.write_bytes(b"prompt\n\xff\n")
    path, spec = make_spec(tmp_path, "import sys; sys.stdout.buffer.write(sys.stdin.buffer.read())", stdin_path=str(prompt))
    finish(launch(path), spec, expected_code=0)
    assert Path(spec["stdout_path"]).read_bytes() == prompt.read_bytes()


def test_timeout_kills_term_ignoring_command_within_total_allowance(tmp_path):
    path, spec = make_spec(tmp_path, """
import signal,time
signal.signal(signal.SIGTERM, signal.SIG_IGN)
print('started', flush=True)
time.sleep(30)
""", timeout=0.8, termination_grace_seconds=0.25)
    result = finish(launch(path), spec, expected_code=124)
    assert result["status"] == "timed_out"
    assert result["duration_seconds"] <= spec["timeout_seconds"] + 0.15
    assert result["exit_code"] == -signal.SIGKILL
    assert result["execution_timeout_seconds"] == pytest.approx(0.55)
    assert Path(spec["stdout_path"]).read_text() == "started\n"


@pytest.mark.parametrize("signum", [signal.SIGTERM, signal.SIGINT])
def test_interruption_cleans_child_and_preserves_logs(tmp_path, signum):
    path, spec = make_spec(tmp_path, """
import time
print('ready', flush=True)
time.sleep(30)
""", timeout=5.0)
    process = launch(path)
    pid = await_pid(Path(spec["pid_path"]))
    deadline = time.monotonic() + 3
    while not Path(spec["stdout_path"]).read_bytes() and time.monotonic() < deadline:
        time.sleep(0.01)
    process.send_signal(signum)
    result = finish(process, spec, expected_code=128 + signum)
    assert result["status"] == "interrupted"
    assert result["interruption_signal"] == signum
    assert Path(spec["stdout_path"]).read_text() == "ready\n"
    if sys.platform == "linux":
        assert supervise._read_identity(pid["command_pid"]) is None


@pytest.mark.skipif(sys.platform != "linux", reason="Linux subreaper guarantee")
@pytest.mark.parametrize("main_wait", [False, True])
def test_setsid_double_fork_cannot_write_after_supervisor_returns(tmp_path, main_wait):
    path, spec = make_spec(tmp_path, f"""
import os,signal,time
from pathlib import Path
pid = os.fork()
if pid == 0:
    os.setsid()
    pid = os.fork()
    if pid != 0:
        os._exit(0)
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    Path('background-pid').write_text(str(os.getpid()))
    time.sleep(1.6)
    Path('escaped-write').write_text('escaped')
    os._exit(0)
while not Path('background-pid').exists():
    time.sleep(0.005)
if {main_wait!r}:
    time.sleep(30)
""", timeout=0.8, termination_grace_seconds=0.3)
    result = finish(launch(path), spec, expected_code=124 if main_wait else 0)
    background_pid = int((tmp_path / "background-pid").read_text())
    assert any(item["pid"] == background_pid for item in result["cleanup"]["tracked"])
    assert any(item["pid"] == background_pid for item in result["cleanup"]["sigkill"])
    assert supervise._read_identity(background_pid) is None
    time.sleep(1.7)
    assert not (tmp_path / "escaped-write").exists()


@pytest.mark.skipif(sys.platform != "linux", reason="Linux child ownership")
def test_existing_sibling_process_is_not_signalled(tmp_path):
    unrelated = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        path, spec = make_spec(tmp_path, "import time; time.sleep(30)", timeout=0.5)
        finish(launch(path), spec, expected_code=124)
        assert unrelated.poll() is None
    finally:
        unrelated.terminate()
        unrelated.wait(timeout=3)


@pytest.mark.skipif(sys.platform != "linux", reason="Linux cancellation identity")
def test_pidfile_termination_uses_owned_endpoint_and_waits_for_cleanup(tmp_path):
    path, spec = make_spec(tmp_path, "import time; print('live', flush=True); time.sleep(30)", timeout=5)
    process = launch(path)
    pid = await_pid(Path(spec["pid_path"]))
    started = time.monotonic()
    cancellation = subprocess.run(
        [sys.executable, "-m", "scicontext.supervise", "--terminate", spec["pid_path"]],
        env={**os.environ, "PYTHONPATH": str(Path(supervise.__file__).resolve().parents[1])},
        capture_output=True, text=True, timeout=3,
    )
    assert cancellation.returncode == 0, cancellation.stderr
    receipt = json.loads(cancellation.stdout)
    assert time.monotonic() - started < 2.15
    assert receipt["status"] == "terminated"
    assert receipt["cleanup"]["success"]
    result = finish(process, spec, expected_code=143)
    assert result["status"] == "interrupted"
    assert not Path(pid["control_path"]).exists()
    assert supervise.terminate_from_pidfile(spec["pid_path"])["status"] == "already_finished"


@pytest.mark.skipif(sys.platform != "linux", reason="Linux cancellation identity")
def test_stale_pidfile_never_interrupts_live_supervisor(tmp_path):
    path, spec = make_spec(tmp_path, "import time; time.sleep(30)", timeout=5)
    process = launch(path)
    pid = await_pid(Path(spec["pid_path"]))
    stale = tmp_path / "stale.json"
    stale.write_text(json.dumps({**pid, "start_time": pid["start_time"] + 1}))
    try:
        with pytest.raises(RuntimeError, match="stale PID"):
            supervise.terminate_from_pidfile(stale)
        assert process.poll() is None
    finally:
        supervise.terminate_from_pidfile(spec["pid_path"])
        finish(process, spec, expected_code=143)


def test_pid_reuse_and_nonchild_identity_are_never_signalled(monkeypatch):
    owner = object.__new__(supervise.LinuxOwner)
    owner.pid = 100
    owner.term, owner.kill, owner.errors = set(), set(), []
    old = supervise.ProcessIdentity(222, 1000, 100, "S")
    signalled = []
    monkeypatch.setattr(os, "kill", lambda *args: signalled.append(args))
    monkeypatch.setattr(supervise, "_read_identity", lambda pid: supervise.ProcessIdentity(pid, 1001, 100, "S"))
    owner.signal_child(old, signal.SIGTERM)
    monkeypatch.setattr(supervise, "_read_identity", lambda pid: supervise.ProcessIdentity(pid, 1000, 999, "S"))
    owner.signal_child(old, signal.SIGTERM)
    assert not signalled


def test_strict_mode_fails_closed_on_unsupported_platform(tmp_path, monkeypatch):
    _, spec = make_spec(tmp_path, "raise RuntimeError('must not execute')", strict_descendants=True)
    monkeypatch.setattr(supervise.sys, "platform", "unsupported-test-platform")
    result = supervise.supervise(spec)
    assert result["status"] == "setup_error"
    assert result["supervisor_exit_code"] == 2
    assert "requires Linux" in result["error"]["message"]
    assert not Path(spec["stdout_path"]).exists()


def test_subreaper_failure_is_not_silently_downgraded(tmp_path, monkeypatch):
    _, spec = make_spec(tmp_path, "pass", strict_descendants=False)
    monkeypatch.setattr(supervise.sys, "platform", "linux")

    def fail():
        raise OSError("subreaper unavailable")

    monkeypatch.setattr(supervise, "LinuxOwner", fail)
    result = supervise.supervise(spec)
    assert result["status"] == "setup_error"
    assert "subreaper unavailable" in result["error"]["message"]


def test_invalid_spec_and_existing_logs_are_not_overwritten(tmp_path):
    _, spec = make_spec(tmp_path, "pass")
    Path(spec["stdout_path"]).write_text("preserved")
    with pytest.raises(FileExistsError):
        supervise.supervise(spec)
    assert Path(spec["stdout_path"]).read_text() == "preserved"
    spec["stdout_path"] = str(tmp_path / "new.log")
    spec["timeout_seconds"] = float("nan")
    with pytest.raises(ValueError, match="positive finite"):
        supervise.supervise(spec)


def test_missing_executable_returns_result_and_logs(tmp_path):
    _, spec = make_spec(tmp_path, "pass")
    spec["command"] = [str(tmp_path / "missing-executable")]
    result = supervise.supervise(spec)
    assert result["status"] == "setup_error"
    assert result["exit_code"] is None
    assert result["cleanup"]["success"]
    assert Path(spec["stdout_path"]).read_bytes() == b""
    assert json.loads(Path(spec["result_path"]).read_text()) == result


def test_cleanup_failure_is_explicit(tmp_path, monkeypatch):
    _, spec = make_spec(tmp_path, "pass", strict_descendants=False)
    monkeypatch.setattr(supervise.sys, "platform", "darwin")
    original = supervise.PosixGroupOwner.cleanup

    def incomplete(self, *args):
        result = original(self, *args)
        result["success"] = False
        result["survivors"] = [{"pid": 999999, "start_ticks": 123}]
        return result

    monkeypatch.setattr(supervise.PosixGroupOwner, "cleanup", incomplete)
    result = supervise.supervise(spec)
    assert result["status"] == "cleanup_failed"
    assert result["status_before_cleanup_failure"] == "completed"
    assert result["supervisor_exit_code"] == 125
