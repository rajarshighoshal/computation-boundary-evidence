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
    assert [x[0] for x in d.calls] == ["prepare", "repair"]
    assert "scientific detail" not in d.calls[0][1]
    assert "scientific detail" in d.calls[1][1]
    assert "Before changing any code" not in d.calls[1][1]
    assert d.calls[1][2] < 2 and d.cleaned
    assert r["extraction_status"] == "prepared_index"


def test_fatal_repair_provider_failure_is_infrastructure_failure(tmp_path):
    d = FakeDriver()
    original = d.run_stage
    async def failed(name, instruction, seconds):
        result = await original(name, instruction, seconds)
        return {**result, "status": "failed", "fatal_model_error": True}
    d.run_stage = failed
    with pytest.raises(RuntimeError, match="this attempt's receipt"):
        asyncio.run(run_trial(d, TrialConfig(total_seconds=2, extraction_seconds=.5),
                             "synthetic", "baseline", "Inspect", tmp_path))
    assert len(d.calls) == 1
    assert json.loads((tmp_path / "run.json").read_text())["status"] == "infrastructure_failure"


def test_timeout_retains_record(tmp_path):
    d = FakeDriver(delay=1)
    r = asyncio.run(run_trial(d, TrialConfig(total_seconds=.08, extraction_seconds=.02), "002", "baseline", "Fix", tmp_path))
    assert r["status"] == "timeout" and d.cleaned
    assert r["stages"][0]["status"] == "timeout"
    assert json.loads((tmp_path / "run.json").read_text())["finished_at"]


@pytest.mark.parametrize("condition", ["baseline", "science"])
def test_retry_wait_pauses_outer_stage_and_work_budget(tmp_path, condition):
    d = FakeDriver({"graph_sha256": "a" * 64, "handoff": "context", "graph": {}})

    async def retrying(name, instruction, seconds):
        if name == "repair":
            await asyncio.sleep(.01)
            await d.wait_for_provider_retry(.15)
            await asyncio.sleep(.01)
        return {"status": "completed"}

    d.run_stage = retrying
    result = asyncio.run(run_trial(d, TrialConfig(total_seconds=.1, extraction_seconds=.02),
                                  "synthetic", condition, "Fix", tmp_path))
    assert result["status"] == "completed" and d.cleaned
    assert result["duration_seconds"] >= .15
    assert result["provider_retry_wait_seconds"] >= .15
    assert result["work_seconds"] < .1
    assert result["over_budget_seconds"] == 0
    assert result["stages"][-1]["provider_retry_wait_seconds"] >= .15
    assert getattr(d, "wait_for_provider_retry", None) is None


def test_extraction_only_never_launches_repair(tmp_path):
    d = FakeDriver({"graph_sha256": "c" * 64, "handoff": "context", "graph": {}})
    r = asyncio.run(run_trial(d, TrialConfig(total_seconds=2, extraction_seconds=.5), "002", "science", "Inspect", tmp_path, extraction_only=True))
    assert [c[0] for c in d.calls] == ["prepare"]
    assert r["extraction_only"] and r["extraction_status"] == "prepared_index"
    assert d.cleaned


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
