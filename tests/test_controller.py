import asyncio
import json
import time

import pytest

from scicontext.controller import TrialConfig, read_usage, run_trial, verify_smoke
from scicontext.configuration import codex_config


def test_usage_preserves_optional_reasoning_without_double_counting(tmp_path):
    import json
    path = tmp_path / "usage.jsonl"
    usages = [{"input_tokens": 30, "cached_input_tokens": 20, "output_tokens": 10,
               "reasoning_output_tokens": 4},
              {"input_tokens": 40, "cached_input_tokens": 30, "output_tokens": 12,
               "reasoning_output_tokens": 5}]
    path.write_text("\n".join(json.dumps({"type": "turn.completed", "usage": u}) for u in usages))
    result = read_usage(path)
    assert result["input_tokens"] == 70 and result["output_tokens"] == 22
    assert result["reasoning_output_tokens"] == 9
    del usages[0]["reasoning_output_tokens"]
    path.write_text("\n".join(json.dumps({"type": "turn.completed", "usage": u}) for u in usages))
    assert read_usage(path)["reasoning_output_tokens"] is None


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


@pytest.mark.parametrize("extraction_only", [False, True])
def test_fatal_extraction_model_failure_does_not_launch_repair(tmp_path, extraction_only):
    d = FakeDriver()
    original = d.run_stage
    async def failed(name, instruction, seconds):
        result = await original(name, instruction, seconds)
        return {**result, "fatal_model_error": True, "model_calls": [
            {"name": "extract_draft", "status": "completed", "usage": result["usage"]},
            {"name": "extract_revision", "status": "failed", "usage": {}, "error": "provider unavailable"}]}
    d.run_stage = failed
    with pytest.raises(RuntimeError, match="No further model call"):
        asyncio.run(run_trial(d, TrialConfig(total_seconds=2, extraction_seconds=.5),
                             "synthetic", "science", "Inspect", tmp_path, extraction_only=extraction_only))
    assert [c[0] for c in d.calls] == ["extract"]
    assert d.finished and d.cleaned
    assert json.loads((tmp_path / "run.json").read_text())["status"] == "infrastructure_failure"


def test_fatal_repair_provider_failure_is_infrastructure_failure(tmp_path):
    d = FakeDriver()
    original = d.run_stage
    async def failed(name, instruction, seconds):
        result = await original(name, instruction, seconds)
        return {**result, "status": "failed", "fatal_model_error": True}
    d.run_stage = failed
    with pytest.raises(RuntimeError, match="schedule must stop"):
        asyncio.run(run_trial(d, TrialConfig(total_seconds=2, extraction_seconds=.5),
                             "synthetic", "baseline", "Inspect", tmp_path))
    assert len(d.calls) == 1
    assert json.loads((tmp_path / "run.json").read_text())["status"] == "infrastructure_failure"


def test_stage_timeout_preserves_driver_fatal_state_before_repair(tmp_path):
    d = FakeDriver()
    async def cancelled(name, instruction, seconds):
        d.calls.append((name, instruction, seconds))
        try:
            await asyncio.sleep(10)
        finally:
            d._fatal_model_error = True
    d.run_stage = cancelled
    with pytest.raises(RuntimeError, match="No further model call"):
        asyncio.run(run_trial(d, TrialConfig(total_seconds=1, extraction_seconds=.12),
                             "synthetic", "science", "Inspect", tmp_path))
    assert [c[0] for c in d.calls] == ["extract"]
    assert d.finished and d.cleaned


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


def test_extraction_only_never_launches_repair(tmp_path):
    d = FakeDriver({"graph_sha256": "c" * 64, "handoff": "context", "graph": {}})
    r = asyncio.run(run_trial(d, TrialConfig(total_seconds=2, extraction_seconds=.5), "002", "science", "Inspect", tmp_path, extraction_only=True))
    assert [c[0] for c in d.calls] == ["extract"]
    assert r["extraction_only"] and r["extraction_status"] == "usable_graph"
    assert d.finished and d.cleaned


def test_extraction_shutdown_is_bounded_and_cannot_be_reported_completed(tmp_path):
    class SlowShutdown(FakeDriver):
        async def finish_extraction(self):
            await asyncio.sleep(1)
        async def cleanup(self):
            await asyncio.sleep(1)
    start = time.monotonic()
    r = asyncio.run(run_trial(SlowShutdown(), TrialConfig(total_seconds=.1, extraction_seconds=.05),
                              "002", "science", "Inspect", tmp_path, extraction_only=True))
    assert time.monotonic() - start < .2
    assert r["extraction_status"] == "shutdown_timeout"
    assert r["status"] != "completed"
    assert "cleanup_error" in r


def test_collection_leaves_shutdown_time(tmp_path):
    class SlowCollection(FakeDriver):
        async def collect_graph(self, seconds):
            self.collection_allowance = seconds
            await asyncio.sleep(1)
        async def finish_extraction(self):
            await asyncio.sleep(.002)
            self.finished = True
    d = SlowCollection()
    r = asyncio.run(run_trial(d, TrialConfig(total_seconds=.3, extraction_seconds=.1),
                              "002", "science", "Inspect", tmp_path, extraction_only=True))
    assert d.collection_allowance < .095
    assert d.finished and r["extraction_status"] == "timeout"


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
