import asyncio
import json
import time

import pytest

from scicontext.controller import TrialConfig, read_usage, run_trial, verify_smoke
from scicontext.configuration import codex_config


class FakeDriver:
    def __init__(self, graph=None, delay=0):
        self.graph = graph
        self.delay = delay
        self.calls = []
        self.finished = False
        self.cleaned = False
        self.collected = False

    async def run_stage(self, name, instruction, seconds):
        self.calls.append((name, instruction, seconds))
        await asyncio.sleep(self.delay)
        return {"status": "completed", "cleanup_complete": True, "usage": {"input_tokens": 5, "cached_input_tokens": 2, "output_tokens": 1}}

    async def collect_graph(self, seconds):
        self.collected = True
        return self.graph

    async def finish_extraction(self):
        self.finished = True

    async def cleanup(self):
        self.cleaned = True


def test_baseline_is_one_unassisted_session(tmp_path):
    d = FakeDriver()
    r = asyncio.run(run_trial(d, TrialConfig(total_seconds=2, extraction_seconds=.5), "002", "baseline", "Fix this", tmp_path))
    assert [x[0] for x in d.calls] == ["repair"]
    assert d.calls[0][1] == "Fix this"
    assert r["status"] == "completed" and d.cleaned


def test_science_handoff_and_remaining_time(tmp_path):
    d = FakeDriver({"graph_sha256": "a" * 64, "handoff": "scientific detail", "graph": {}}, delay=.03)
    r = asyncio.run(run_trial(d, TrialConfig(total_seconds=2, extraction_seconds=.5), "002", "science", "Fix", tmp_path))
    assert [x[0] for x in d.calls] == ["extract", "repair"]
    assert "scientific detail" not in d.calls[0][1]
    assert "scientific detail" in d.calls[1][1]
    assert d.calls[1][2] < 2 and d.finished and d.cleaned
    assert r["extraction_status"] == "usable_graph"


def test_failed_extraction_falls_back_without_extra_time(tmp_path):
    d = FakeDriver(delay=.15)
    r = asyncio.run(run_trial(d, TrialConfig(total_seconds=.5, extraction_seconds=.1), "077", "science", "Fix", tmp_path))
    assert r["graph_sha256"] is None
    assert d.calls[-1][1] == "Fix"
    assert d.calls[-1][2] < .5
    assert d.finished and d.cleaned
    assert d.collected
    assert r["stages"][0]["status"] == "timeout"
    assert r["stages"][0]["usage"]["input_tokens"] is None


def test_timeout_retains_record(tmp_path):
    d = FakeDriver(delay=1)
    r = asyncio.run(run_trial(d, TrialConfig(total_seconds=.08, extraction_seconds=.02), "002", "baseline", "Fix", tmp_path))
    assert r["status"] == "timeout" and d.cleaned
    assert r["stages"][0]["status"] == "timeout"
    assert json.loads((tmp_path / "run.json").read_text())["finished_at"]


def test_checkpoint_survives_extract_stage_timeout(tmp_path):
    d = FakeDriver({"graph_sha256": "b" * 64, "handoff": "saved evidence", "graph": {}}, delay=.15)
    r = asyncio.run(run_trial(d, TrialConfig(total_seconds=.5, extraction_seconds=.1), "077", "science", "Fix", tmp_path))
    assert r["extraction_status"] == "usable_graph"
    assert "saved evidence" in d.calls[-1][1]
    assert r["stages"][0]["usage"]["output_tokens"] is None


def test_refuse_overwriting_attempt(tmp_path):
    (tmp_path / "run.json").write_text("{}")
    with pytest.raises(FileExistsError):
        asyncio.run(run_trial(FakeDriver(), TrialConfig(), "002", "baseline", "Fix", tmp_path))


def test_usage_missing_is_not_zero(tmp_path):
    assert read_usage(tmp_path / "absent")["input_tokens"] is None
    p = tmp_path / "events.jsonl"
    p.write_text('broken\n' + json.dumps({"type": "turn.completed", "usage": {"input_tokens": 10, "cached_input_tokens": 7, "output_tokens": 2}}) + '\n')
    assert read_usage(p)["input_tokens"] == 10
    assert read_usage(p)["malformed_log_lines"] == 1


def test_configuration_contains_no_custom_sandbox_policy():
    import tomllib
    c = tomllib.loads(codex_config("gpt-6-astra", "high"))
    assert c["forced_login_method"] == "chatgpt"
    assert "permissions" not in c and "default_permissions" not in c
    assert "sandbox_mode" not in c
    assert c["model_reasoning_effort"] == "high"


def test_smoke_needs_real_tool_execution_and_completed_turn(tmp_path):
    events, final = tmp_path / "events.jsonl", tmp_path / "final.txt"
    assert not verify_smoke(events, final)
    final.write_text("READY\n")
    events.write_text(json.dumps({"type": "turn.completed", "usage": {
        "input_tokens": 10, "cached_input_tokens": 0, "output_tokens": 5}}) + "\n")
    assert not verify_smoke(events, final)
    with events.open("a") as stream:
        stream.write(json.dumps({"type": "item.completed", "item": {
            "type": "command_execution", "exit_code": 0, "aggregated_output": "42\n"}}) + "\n")
    assert verify_smoke(events, final)
    final.write_text("Unable to connect")
    assert not verify_smoke(events, final)
