"""DeepSeek agent wiring: extraction call, repair tool loop, receipts."""
import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from scicontext import deepseek_agent as module
from scicontext.deepseek_agent import DeepSeekAgent

pytest.importorskip("pier")


class FakeEnvironment:
    def __init__(self, tmp_path, payload, graph):
        self.tmp_path = tmp_path
        self.payload = payload
        self.graph = graph
        self.uploaded = {}
        self.commands = []

    async def download_file(self, remote, local):
        local.parent.mkdir(parents=True, exist_ok=True)
        if remote.endswith("scientific-context-input.json"):
            local.write_text(json.dumps(self.payload))
        else:
            local.write_text(json.dumps(self.graph))

    async def upload_file(self, local, remote):
        self.uploaded[remote] = local.read_text()

    async def exec(self, command, **kwargs):
        self.commands.append(command)
        return "ok 42"


def make_agent(tmp_path, condition="science"):
    key = tmp_path / "deepseek-key.json"
    key.write_text(json.dumps({"api_key": "secret"}))
    (tmp_path / "prompts").mkdir()
    (tmp_path / "prompts/enrich_objects.md").write_text(
        "Interpret objects. {instruction}\n{seconds} {explore_until} {save_by} {finish_by} {root} {scratch} {runtime}")
    return DeepSeekAgent(logs_dir=tmp_path / "logs", model_name="deepseek-flash",
                         condition=condition, workspace=tmp_path,
                         deepseek_key_file=str(key), frozen_source_dir=str(tmp_path))


def graph_and_payload():
    graph = {"schema_version": "scientific-objects-1.0", "task_id": "058",
             "objects": [{"id": "so_a", "kind": "code_interface", "symbol": "step",
                          "scope": "m", "path": "m.py", "source_entry_ids": ["e1"],
                          "properties": {}, "roles": []}],
             "operations": [], "links": [], "unsupported": [], "coverage": {"totals": {}}}
    payload = {"objects": graph["objects"], "operations": [], "links": [], "unsupported": [],
               "context": {"scientific_passages": [{"text": "public"}], "code_passages": []},
               "selection": {"truncated": False, "kept_objects": 1}}
    return graph, payload


def test_interpret_calls_api_inline_and_uploads_annotations(tmp_path, monkeypatch):
    graph, payload = graph_and_payload()
    agent = make_agent(tmp_path)
    env = FakeEnvironment(tmp_path, payload, graph)
    agent.extract_environment = env
    agent.root = "/app/task_058"
    agent.logs_dir.mkdir(parents=True, exist_ok=True)
    responses = [{"choices": [{"message": {"content": json.dumps(
        {"object_id": "so_a", "meaning": "solver step"}), "tool_calls": None},
        "finish_reason": "stop"}], "usage": {"prompt_tokens": 100, "completion_tokens": 20}}]
    async def fake_api(*args, **kwargs):
        assert args[0] == "secret" and args[1] == "deepseek-flash"
        assert kwargs["response_format"] == {"type": "json_object"}
        return responses.pop(0)
    monkeypatch.setattr(module, "_api_completion", fake_api)
    result = asyncio.run(agent._interpret_call("Inspect", 300))
    assert result["status"] == "completed" and result["annotations_status"] == "received"
    assert result["usage"]["input_tokens"] == 100 and result["usage"]["output_tokens"] == 20
    assert "/opt/scicontext/scratch/extract_draft-annotations.json" in env.uploaded
    assert "so_a" in env.uploaded["/opt/scicontext/scratch/extract_draft-annotations.json"]


def test_interpret_non_json_content_is_code_only_not_fatal(tmp_path, monkeypatch):
    graph, payload = graph_and_payload()
    agent = make_agent(tmp_path)
    env = FakeEnvironment(tmp_path, payload, graph)
    agent.extract_environment = env
    agent.root = "/app/task_058"
    agent.logs_dir.mkdir(parents=True, exist_ok=True)
    async def fake_api(*args, **kwargs):
        return {"choices": [{"message": {"content": "no json here"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 3}}
    monkeypatch.setattr(module, "_api_completion", fake_api)
    result = asyncio.run(agent._interpret_call("Inspect", 300))
    assert result["status"] == "completed"
    assert result["annotations_status"] == "no_valid_annotations"
    assert not result.get("fatal_model_error")


def test_repair_loop_runs_shell_tools_and_writes_final(tmp_path, monkeypatch):
    agent = make_agent(tmp_path, condition="baseline")
    env = FakeEnvironment(tmp_path, {}, {})
    agent.environment = env
    agent.root = "/app/task_058"
    agent.logs_dir.mkdir(parents=True, exist_ok=True)
    responses = [
        {"choices": [{"message": {"content": None, "tool_calls": [
            {"id": "call_1", "function": {"name": "shell", "arguments": json.dumps({"command": "pytest -q"})}}]},
            "finish_reason": "tool_calls"}], "usage": {"prompt_tokens": 50, "completion_tokens": 5}},
        {"choices": [{"message": {"content": "READY", "tool_calls": None}, "finish_reason": "stop"}],
         "usage": {"prompt_tokens": 60, "completion_tokens": 3}},
    ]
    async def fake_api(*args, **kwargs):
        assert kwargs["tools"][0]["function"]["name"] == "shell"
        return responses.pop(0)
    monkeypatch.setattr(module, "_api_completion", fake_api)
    result = asyncio.run(agent._run_deepseek_repair("Fix it", 120))
    assert result["status"] == "completed"
    assert (tmp_path / "logs/repair-final.txt").read_text() == "READY"
    assert "pytest -q" in env.commands
    assert result["usage"]["input_tokens"] == 110 and result["usage"]["output_tokens"] == 8
    events = [json.loads(line) for line in (tmp_path / "logs/repair.jsonl").read_text().splitlines()]
    assert events[-1]["type"] == "turn.completed"


def test_repair_transport_failure_is_fatal(tmp_path, monkeypatch):
    agent = make_agent(tmp_path, condition="baseline")
    agent.environment = FakeEnvironment(tmp_path, {}, {})
    agent.root = "/app/task_058"
    agent.logs_dir.mkdir(parents=True, exist_ok=True)
    async def fake_api(*args, **kwargs):
        raise TimeoutError("socket timeout")
    monkeypatch.setattr(module, "_api_completion", fake_api)
    result = asyncio.run(agent._run_deepseek_repair("Fix it", 60))
    assert result["status"] == "failed" and result["fatal_model_error"]
    assert agent._fatal_model_error


def test_agent_requires_key_file(tmp_path):
    with pytest.raises(ValueError, match="deepseek_key_file"):
        DeepSeekAgent(logs_dir=tmp_path, model_name="deepseek-flash", workspace=tmp_path)


def test_repair_events_are_counted_by_controller_read_usage(tmp_path, monkeypatch):
    from scicontext.controller import read_usage
    agent = make_agent(tmp_path, condition="baseline")
    agent.environment = FakeEnvironment(tmp_path, {}, {})
    agent.root = "/app/task_058"
    agent.logs_dir.mkdir(parents=True, exist_ok=True)
    async def fake_api(*args, **kwargs):
        return {"choices": [{"message": {"content": "READY", "tool_calls": None}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 40, "completion_tokens": 7}}
    monkeypatch.setattr(module, "_api_completion", fake_api)
    result = asyncio.run(agent._run_deepseek_repair("Fix", 60))
    assert result["status"] == "completed"
    usage = read_usage(tmp_path / "logs/repair.jsonl")
    assert usage["completed_turns"] == 1
    assert usage["input_tokens"] == 40 and usage["output_tokens"] == 7
    assert json.loads((tmp_path / "logs/repair-process.json").read_text())["status"] == "completed"


def test_repair_malformed_tool_arguments_become_tool_error_not_crash(tmp_path, monkeypatch):
    agent = make_agent(tmp_path, condition="baseline")
    agent.environment = FakeEnvironment(tmp_path, {}, {})
    agent.root = "/app/task_058"
    agent.logs_dir.mkdir(parents=True, exist_ok=True)
    responses = [
        {"choices": [{"message": {"content": None, "tool_calls": [
            {"id": "c1", "function": {"name": "shell", "arguments": "not json{"}}]},
            "finish_reason": "tool_calls"}], "usage": {"prompt_tokens": 5, "completion_tokens": 2}},
        {"choices": [{"message": {"content": "DONE", "tool_calls": None}, "finish_reason": "stop"}],
         "usage": {"prompt_tokens": 5, "completion_tokens": 2}},
    ]
    async def fake_api(*args, **kwargs):
        return responses.pop(0)
    monkeypatch.setattr(module, "_api_completion", fake_api)
    result = asyncio.run(agent._run_deepseek_repair("Fix", 60))
    assert result["status"] == "completed"
    events = [json.loads(l) for l in (tmp_path / "logs/repair.jsonl").read_text().splitlines()]
    item = next(e for e in events if e["type"] == "item.completed")
    assert item["item"]["exit_code"] == 1
    assert "Malformed tool arguments" in item["item"]["aggregated_output"]


def test_repair_tool_exec_never_runs_past_deadline(tmp_path, monkeypatch):
    agent = make_agent(tmp_path, condition="baseline")
    env = FakeEnvironment(tmp_path, {}, {})
    agent.environment = env
    agent.root = "/app/task_058"
    agent.logs_dir.mkdir(parents=True, exist_ok=True)
    async def slow_exec(command, **kwargs):
        assert kwargs["timeout_sec"] <= 2.0, kwargs["timeout_sec"]
        return "slow"
    env.exec = slow_exec
    async def slow_api(*args, **kwargs):
        await asyncio.sleep(1.2)  # leaves < 2s of a 3s budget
        return {"choices": [{"message": {"content": None, "tool_calls": [
            {"id": "c1", "function": {"name": "shell", "arguments": json.dumps({"command": "true"})}}]},
            "finish_reason": "tool_calls"}], "usage": {"prompt_tokens": 5, "completion_tokens": 2}}
    monkeypatch.setattr(module, "_api_completion", slow_api)
    result = asyncio.run(agent._run_deepseek_repair("Fix", 3))
    assert result["status"] == "timeout"
    # Receipts must exist even on timeout.
    assert (tmp_path / "logs/repair-process.json").is_file()
    assert (tmp_path / "logs/repair.jsonl").is_file()


def test_interpret_success_writes_process_receipt(tmp_path, monkeypatch):
    graph, payload = graph_and_payload()
    agent = make_agent(tmp_path)
    env = FakeEnvironment(tmp_path, payload, graph)
    agent.extract_environment = env
    agent.root = "/app/task_058"
    agent.logs_dir.mkdir(parents=True, exist_ok=True)
    async def fake_api(*args, **kwargs):
        return {"choices": [{"message": {"content": json.dumps(
            {"object_id": "so_a", "meaning": "step"})}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 3, "completion_tokens": 1}}
    monkeypatch.setattr(module, "_api_completion", fake_api)
    asyncio.run(agent._interpret_call("Inspect", 300))
    receipt = json.loads((tmp_path / "logs/extract_draft-process.json").read_text())
    assert receipt["status"] == "completed" and receipt["annotations_status"] == "received"
