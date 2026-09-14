"""DeepSeek agent wiring: extraction call, repair tool loop, receipts."""
import asyncio
import io
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from urllib.error import HTTPError

import pytest

from scicontext import deepseek_agent as module
from scicontext.deepseek_agent import DeepSeekAgent

pytest.importorskip("pier")


class FakeHTTPResponse:
    def __init__(self, status, payload):
        self.status = status
        self._raw = json.dumps(payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self._raw


def http_error(status, payload):
    return HTTPError("https://api.deepseek.com/chat/completions", status, "provider error", {},
                     io.BytesIO(json.dumps(payload).encode()))


class FakeEnvironment:
    def __init__(self, tmp_path, payload, graph):
        self.tmp_path = tmp_path
        from scicontext.representation import reading_input
        self.payload = reading_input(payload)
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


def make_agent(tmp_path, condition="baseline"):
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


def test_api_retries_429_then_returns_success(monkeypatch):
    calls = []
    responses = [http_error(429, {"error": {"type": "rate_limit_error", "code": "busy", "message": "slow down"}}),
                 FakeHTTPResponse(200, {"choices": [{"message": {"content": "OK", "tool_calls": None}}]})]

    def fake_urlopen(request, timeout):
        calls.append(timeout)
        response = responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    monkeypatch.setattr(module.urllib.request, "urlopen", fake_urlopen)
    result = asyncio.run(module._api_completion("actual-key", "deepseek-flash", [{"role": "user", "content": "x"}],
                                                timeout_sec=30, max_attempts=2))
    assert result["choices"][0]["message"]["content"] == "OK"
    assert len(calls) == 2


@pytest.mark.parametrize("status", [401, 402])
def test_api_does_not_retry_permanent_http_errors(monkeypatch, status):
    calls = []

    def fake_urlopen(request, timeout):
        calls.append(timeout)
        raise http_error(status, {"error": {"type": "auth_error", "code": "permanent", "message": "no retry"}})

    monkeypatch.setattr(module.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(module.DeepSeekProviderError) as raised:
        asyncio.run(module._api_completion("actual-key", "deepseek-flash", [{"role": "user", "content": "x"}],
                                           timeout_sec=30, max_attempts=2))
    assert len(calls) == 1
    assert raised.value.metadata["status"] == status


def test_api_retries_http_200_rate_limit_error_then_success(monkeypatch):
    responses = [FakeHTTPResponse(200, {"error": {"type": "rate_limit_error", "code": "busy", "message": "later"}}),
                 FakeHTTPResponse(200, {"choices": [{"message": {"content": "OK", "tool_calls": None}}]})]
    monkeypatch.setattr(module.urllib.request, "urlopen", lambda request, timeout: responses.pop(0))
    result = asyncio.run(module._api_completion("actual-key", "deepseek-flash", [{"role": "user", "content": "x"}],
                                                timeout_sec=30, max_attempts=2))
    assert result["choices"][0]["message"]["content"] == "OK"


def test_api_malformed_response_preserves_bounded_metadata_and_redacts_key(monkeypatch):
    key = "actual-secret-key"
    payload = {"type": key, "code": key, "message": f"quoted '{key}' and Bearer {key}", "extra": "x" * 5000}
    monkeypatch.setattr(module.urllib.request, "urlopen", lambda request, timeout: FakeHTTPResponse(200, payload))
    with pytest.raises(module.DeepSeekProviderError) as raised:
        asyncio.run(module._api_completion(key, "deepseek-flash", [{"role": "user", "content": "x"}],
                                           timeout_sec=30, max_attempts=1))
    metadata = raised.value.metadata
    serialized = json.dumps(metadata)
    assert metadata["status"] == 200 and metadata["attempt"] == 1
    assert "actual-secret-key" not in serialized
    assert len(metadata["body"]) <= module.MAX_PROVIDER_BODY_CHARS
    assert metadata["kind"] == "invalid_response"


def test_failed_provider_request_marks_inflight_usage_unknown(tmp_path, monkeypatch):
    agent = make_agent(tmp_path, condition="baseline")
    agent.environment = FakeEnvironment(tmp_path, {}, {})
    agent.root = "/app/task_058"
    agent.logs_dir.mkdir(parents=True, exist_ok=True)
    metadata = {"kind": "provider_error", "status": 429, "attempt": 2, "max_attempts": 2,
                "retryable": True, "type": "rate_limit_error", "code": "busy", "message": "busy", "body": "{}"}

    async def fake_api(*args, **kwargs):
        raise module.DeepSeekProviderError(metadata)

    monkeypatch.setattr(module, "_api_completion", fake_api)
    result = asyncio.run(agent._run_deepseek_repair("Fix", 60))
    assert result["status"] == "failed" and result["fatal_model_error"] is True
    usage = result["usage"]
    assert usage["unknown_inflight_request"] is True
    assert usage["known_input_tokens"] == 0 and usage["known_output_tokens"] == 0
    assert usage["accounting"] == "known_completed_calls_plus_unknown_inflight"
    process = json.loads((tmp_path / "logs/repair-process.json").read_text())
    assert process["usage"]["unknown_inflight_request"] is True


def test_http_200_provider_error_is_receipted_without_choices_keyerror(tmp_path, monkeypatch):
    agent = make_agent(tmp_path, condition="baseline")
    agent.environment = FakeEnvironment(tmp_path, {}, {})
    agent.root = "/app/task_058"
    agent.logs_dir.mkdir(parents=True, exist_ok=True)

    async def fake_api(*args, **kwargs):
        return {"error": {"type": "rate_limit_error", "code": "busy",
                           "message": "Bearer super-secret-token overloaded"},
                "request_id": "do-not-copy"}

    monkeypatch.setattr(module, "_api_completion", fake_api)
    result = asyncio.run(agent._run_deepseek_repair("Fix", 60))

    assert result["status"] == "failed"
    assert result["fatal_model_error"] is True
    assert result["error_kind"] == "provider_error"
    assert result["provider_error"] == {
        "kind": "provider_error", "type": "rate_limit_error", "code": "busy",
        "message": "Bearer [redacted] overloaded",
    }
    process = json.loads((tmp_path / "logs/repair-process.json").read_text())
    assert process["provider_error"] == result["provider_error"]
    assert "super-secret-token" not in (tmp_path / "logs/repair-session.json").read_text()
    events = [json.loads(line) for line in (tmp_path / "logs/repair.jsonl").read_text().splitlines()]
    assert [event["type"] for event in events] == ["provider_error"]


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
    assert "JSONDecodeError" in item["item"]["aggregated_output"]


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
