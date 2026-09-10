"""Independent accounting checks use synthetic local logs only."""
import importlib.util
import json
from pathlib import Path

import pytest


spec = importlib.util.spec_from_file_location("audit_session_tokens", Path(__file__).resolve().parents[1] / "scripts/audit_session_tokens.py")
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def fixture(trial, reasoning=4):
    agent = trial / "agent"
    sessions = agent / "repair-sessions"
    sessions.mkdir(parents=True)
    usage = {"input_tokens": 100, "cached_input_tokens": 80, "output_tokens": 10, "reasoning_output_tokens": 4}
    (agent / "repair.jsonl").write_text(json.dumps({"type": "turn.completed", "usage": usage}) + "\n")
    counters = {**usage, "reasoning_output_tokens": reasoning, "total_tokens": 110}
    events = [{"type": "session_meta", "payload": {"source": "exec"}},
              {"type": "event_msg", "payload": {"type": "token_count", "info": {"total_token_usage": counters}}}]
    (sessions / "session.jsonl").write_text("\n".join(json.dumps(e) for e in events))
    return {"name": "repair", "status": "completed", "usage": usage}


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
