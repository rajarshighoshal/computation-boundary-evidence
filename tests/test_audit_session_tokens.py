"""Independent accounting checks use synthetic local logs only."""
import importlib.util
import json
from pathlib import Path

import pytest


spec = importlib.util.spec_from_file_location("audit_session_tokens", Path(__file__).resolve().parents[1] / "scripts/audit_session_tokens.py")
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def fixture(trial, reasoning=4, name="repair"):
    agent = trial / "agent"
    sessions = agent / f"{name}-sessions"
    sessions.mkdir(parents=True)
    usage = {"input_tokens": 100, "cached_input_tokens": 80, "output_tokens": 10, "reasoning_output_tokens": 4}
    (agent / f"{name}.jsonl").write_text(json.dumps({"type": "turn.completed", "usage": usage}) + "\n")
    counters = {**usage, "reasoning_output_tokens": reasoning, "total_tokens": 110}
    events = [{"type": "session_meta", "payload": {"source": "exec"}},
              {"type": "event_msg", "payload": {"type": "token_count", "info": {"total_token_usage": counters}}}]
    (sessions / "session.jsonl").write_text("\n".join(json.dumps(e) for e in events))
    return {"name": name, "status": "completed", "usage": usage}


def test_matches_independent_counters_without_double_counting(tmp_path):
    values = audit.audit_stage(tmp_path, fixture(tmp_path))["usage"]
    assert values["total_tokens"] == 110
    assert values["uncached_input_tokens"] == 20
    assert values["nonreasoning_output_tokens"] == 6


def test_reasoning_mismatch_is_detected(tmp_path):
    stage = fixture(tmp_path, reasoning=5)
    with pytest.raises(ValueError, match="disagree"):
        audit.audit_stage(tmp_path, stage)


def test_incomplete_stage_is_not_zero(tmp_path):
    assert audit.audit_stage(tmp_path, {"name": "extract", "status": "timeout"}) == {
        "stage": "extract", "status": "unknown_incomplete_stage"}


def multicall(trial):
    calls = [fixture(trial, name=name) for name in ("extract_draft", "extract_revision")]
    return {"name": "extract", "status": "completed", "model_calls": calls,
            "usage": {field: value * 2 for field, value in calls[0]["usage"].items()}}


def test_independent_multicall_audit_matches_leaves_and_aggregate(tmp_path):
    result = audit.audit_stage(tmp_path, multicall(tmp_path))
    assert result["status"] == "verified"
    assert result["usage"]["total_tokens"] == 220
    assert result["usage"]["reasoning_output_tokens"] == 8
    assert [call["stage"] for call in result["model_calls"]] == ["extract_draft", "extract_revision"]
    assert all(call["usage"]["total_tokens"] == 110 for call in result["model_calls"])


@pytest.mark.parametrize("missing", ["usage", "log", "session", "timeout"])
def test_missing_attempt_does_not_become_zero(tmp_path, missing):
    stage = multicall(tmp_path)
    if missing == "usage":
        stage["model_calls"][1]["usage"] = None
    elif missing == "timeout":
        stage["model_calls"][1]["status"] = "timeout"
    else:
        (tmp_path / "agent" / ("extract_revision.jsonl" if missing == "log"
                               else "extract_revision-sessions/session.jsonl")).unlink()
    result = audit.audit_stage(tmp_path, stage)
    assert result["status"] == "unknown_incomplete_stage"
    assert "usage" not in result
    assert result["model_calls"][0]["status"] == "verified"


def test_multicall_aggregate_mismatch_rejected(tmp_path):
    stage = multicall(tmp_path)
    stage["usage"]["input_tokens"] += 1
    with pytest.raises(ValueError, match="aggregate receipt"):
        audit.audit_stage(tmp_path, stage)


@pytest.mark.parametrize("calls", [None, {}, [{"name": "extract_revision"}], [{"name": "extract_draft"}] * 2])
def test_multicall_malformed_rejected(tmp_path, calls):
    with pytest.raises(ValueError, match="Malformed"):
        audit.audit_stage(tmp_path, {"name": "extract", "model_calls": calls})


def test_multicall_session_disagreement_detected(tmp_path):
    stage = multicall(tmp_path)
    path = tmp_path / "agent/extract_revision-sessions/session.jsonl"
    events = [json.loads(line) for line in path.read_text().splitlines()]
    events[-1]["payload"]["info"]["total_token_usage"]["reasoning_output_tokens"] += 1
    path.write_text("\n".join(json.dumps(event) for event in events))
    with pytest.raises(ValueError, match="disagree"):
        audit.audit_stage(tmp_path, stage)


def test_empty_calls_have_unknown_cost(tmp_path):
    result = audit.audit_stage(tmp_path, {"name": "extract", "status": "completed", "model_calls": [],
                                         "usage": {field: 0 for field in audit.FIELDS}})
    assert result["status"] == "unknown_incomplete_stage"
    assert "usage" not in result
