import json
import threading
from types import SimpleNamespace

import pytest

from scicontext import probes


def test_independent_probes_run_concurrently_and_record_failures(tmp_path, monkeypatch):
    for name in ("a.py", "b.py"):
        (tmp_path / name).write_text("print('probe')\n")
    barrier = threading.Barrier(2, timeout=2)
    calls = []
    def execute(command, **kwargs):
        calls.append(command)
        assert kwargs["env"]["OMP_NUM_THREADS"] == "1"
        assert command[:3] == ["timeout", "--signal=TERM", "--kill-after=3s"]
        barrier.wait()
        kwargs["stdout"].write("observed\n")
        return SimpleNamespace(returncode=1 if "p2" in str(command) else 0)
    monkeypatch.setattr(probes.subprocess, "run", execute)
    specs = [{"id": "p1", "claim_ids": ["c1"], "script": "a.py", "description": "first", "fingerprint": "a" * 64},
             {"id": "p2", "claim_ids": ["c2"], "script": "b.py", "description": "second"}]
    results = probes.run_probes(specs, tmp_path, tmp_path, 10)
    assert [r["status"] for r in results] == ["completed", "failed"]
    assert len(calls) == 2
    assert results[0]["fingerprint"] == specs[0]["fingerprint"]
    assert results[1]["fingerprint"] is None
    for result in results:
        assert len(result["script_sha256"]) == 64
        assert result["stdout_excerpt"] == "observed\n"
        assert json.loads((tmp_path / result["artifact"]).read_text()) == result


@pytest.mark.parametrize("path", ["../escape.py", "/outside.py", ".hidden.py", "a.sh", "missing.py"])
def test_invalid_probe_never_executes(tmp_path, monkeypatch, path):
    def forbidden(*args, **kwargs):
        raise AssertionError("Must not execute")
    monkeypatch.setattr(probes.subprocess, "run", forbidden)
    result = probes.run_probes([{"id": "p1", "claim_ids": ["c1"], "script": path, "description": "bad"}], tmp_path, tmp_path, 10)[0]
    assert result["status"] == "failed" and result["exit_code"] is None


def test_symlink_and_insufficient_time_do_not_run(tmp_path, monkeypatch):
    (tmp_path / "real.py").write_text("pass\n")
    (tmp_path / "link.py").symlink_to("real.py")
    monkeypatch.setattr(probes.subprocess, "run", lambda *a, **k: pytest.fail("Unexpected execution"))
    spec = {"id": "p1", "claim_ids": ["c1"], "script": "link.py", "description": "link"}
    assert probes.run_probes([spec], tmp_path, tmp_path, 10)[0]["status"] == "failed"
    spec["script"] = "real.py"
    assert probes.run_probes([spec], tmp_path, tmp_path, 1)[0]["status"] == "not_run"
