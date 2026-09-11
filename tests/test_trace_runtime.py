"""Workflow tracer: synthetic trace, observables, predicates, caps."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from scicontext.trace_runtime import _Tracer, _parse_predicates


def test_predicate_parsing_forms():
    text = (
        "import numpy as np\n"
        "def f(x):\n"
        "    assert x == y\n"
        "    assert x != z\n"
        "    assert np.allclose(a, b, atol=1e-9)\n"
        "    assert (x >= 0.0).all()\n"
        "    assert (x < 1.0).all()\n"
    )
    forms = _parse_predicates(text)
    kinds = {form["kind"] for form in forms}
    assert kinds == {"equality", "inequality", "closeness", "bounds"}
    assert len(forms) == 5


def _run_trace(tmp_path: Path, script_text: str) -> Path:
    script = tmp_path / "reproduce.py"
    script.write_text(script_text)
    out = tmp_path / "trace"
    tracer = _Tracer(tmp_path, script, out, observe=False)
    tracer.run(60)
    return out


def test_trace_records_repo_frames_only(tmp_path):
    out = _run_trace(tmp_path, "import numpy as np\n\ndef double(x):\n    return np.asarray(x) * 2\n\nresult = double([1.0, 2.0])\nassert result[0] == 2.0\n")
    records = [json.loads(line) for line in (out / "trace.jsonl").read_text().splitlines() if line]
    names = {record["name"] for record in records}
    assert "double" in names
    assert any("reproduce.py" in record["file"] for record in records)


def test_trace_fingerprints_args_and_returns(tmp_path):
    out = _run_trace(tmp_path, "def scale(x, factor):\n    return x * factor\n\nscale(2.0, 3.0)\n")
    records = [json.loads(line) for line in (out / "trace.jsonl").read_text().splitlines() if line]
    call = next(record for record in records if record["name"] == "scale")
    assert call["inputs"]["x"]["exact"] == call["inputs"]["x"]["exact"]
    assert call["inputs"]["factor"]["exact"]
    assert call["return_fp"]["exact"]
    assert call["parent_seq"] is not None or call["file"] == "reproduce.py"


def test_trace_captures_script_observables_and_predicate_evaluations(tmp_path):
    out = _run_trace(tmp_path, "import numpy as np\n\na = np.array([1.0, 2.0])\nb = np.array([1.0, 2.0])\nassert np.allclose(a, b)\n")
    observables = json.loads((out / "script_observables.json").read_text())
    assert {entry["name"] for entry in observables} >= {"a", "b"}
    predicates = json.loads((out / "script_predicates.json").read_text())
    assert predicates["declared"]
    assert any(evaluation["evaluated"] for evaluation in predicates["evaluations"])
    run = json.loads((out / "run.json").read_text())
    assert run["status"] == "completed" and run["instances"] >= 1


def test_trace_cli_runs_end_to_end(tmp_path):
    script = tmp_path / "reproduce.py"
    script.write_text("def f(x):\n    return x + 1\n\nf(41)\n")
    result = subprocess.run([sys.executable, "-m", "scicontext.trace_runtime",
                             "--root", str(tmp_path), "--script", str(script),
                             "--out", str(tmp_path / "trace-out"), "--seconds", "30"],
                            capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stderr
    records = list((tmp_path / "trace-out" / "trace.jsonl").read_text().splitlines())
    assert any(json.loads(line)["name"] == "f" for line in records if line)
