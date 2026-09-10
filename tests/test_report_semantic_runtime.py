"""Partial usage is an observation, never a completed-call total."""
import importlib.util
import json
import sys
from pathlib import Path

import pytest


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location("report_semantic_runtime", SCRIPTS / "report_semantic_runtime.py")
report = importlib.util.module_from_spec(spec)
spec.loader.exec_module(report)


def test_partial_counter_is_marked_incomplete(tmp_path):
    folder = tmp_path / "agent/extract_draft-sessions"
    folder.mkdir(parents=True)
    usage = {"input_tokens": 100, "cached_input_tokens": 60, "output_tokens": 10,
             "reasoning_output_tokens": 3, "total_tokens": 110}
    event = {"type": "event_msg", "timestamp": "synthetic", "payload": {
        "type": "token_count", "info": {"total_token_usage": usage}}}
    (folder / "session.jsonl").write_text(json.dumps(event))
    value = report.partial_usage(tmp_path, {"name": "extract_draft"})
    assert value["usage"] == usage and value["full_cost_known"] is False
    assert value["status"] == "last_observed_cumulative_counter"
    usage["total_tokens"] += 1
    (folder / "session.jsonl").write_text(json.dumps(event))
    with pytest.raises(ValueError, match="Invalid partial"):
        report.partial_usage(tmp_path, {"name": "extract_draft"})


def test_resource_sample_units_are_explicit():
    assert report.memory_bytes("1.5MiB") == 1.5 * 1024**2
    with pytest.raises(ValueError, match="Unknown Docker memory unit"):
        report.memory_bytes("1.5 unspecified")
