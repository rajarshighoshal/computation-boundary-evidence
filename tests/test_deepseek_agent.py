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


def test_analyzer_slots_limit_concurrent_work_and_release_on_cancellation(tmp_path):
    async def exercise():
        active = peak = 0
        async def worker():
            nonlocal active, peak
            async with module.analyzer_slot(tmp_path, slots=2):
                active += 1
                peak = max(active, peak)
                await asyncio.sleep(.01)
                active -= 1
        await asyncio.gather(*(worker() for _ in range(8)))
        assert peak == 2
        async def blocked():
            async with module.analyzer_slot(tmp_path, slots=1):
                pytest.fail('Occupied analyzer slot must not be entered')
        async with module.analyzer_slot(tmp_path, slots=1):
            pending = asyncio.create_task(blocked())
            await asyncio.sleep(.01)
            pending.cancel()
            with pytest.raises(asyncio.CancelledError):
                await pending
        async with asyncio.timeout(.2):
            async with module.analyzer_slot(tmp_path, slots=1):
                pass
    asyncio.run(exercise())


def test_analyzer_allowance_includes_cached_upload_and_remote_merge(tmp_path):
    agent = DeepSeekAgent.__new__(DeepSeekAgent)
    agent.logs_dir = tmp_path
    wanted = {'path':'model.py', 'sha256':'fixture'}
    receipt = tmp_path / 'source-analysis' / module.digest_json(wanted)[:20] / 'backend/receipt.json'
    receipt.parent.mkdir(parents=True)
    receipt.write_text('{}')
    async def upload(*args):
        await asyncio.sleep(.05)
    agent.environment = SimpleNamespace(upload_file=upload)
    agent.checked = AsyncMock(return_value='{}')
    result = asyncio.run(agent._analyze_query('inspect', {'sources':['available']}, wanted, .01))
    assert result['sources'] == ['available']
    assert result['analysis_gaps'][0]['reason'].startswith('TimeoutError')
    agent.checked.assert_not_awaited()


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


def stub_transport(monkeypatch, send):
    """Stub the HTTP boundary, keeping the actual retry/response logic under test."""
    async def post(request, seconds):
        try:
            response = send(request, seconds)
            return response.status, response.read()
        except HTTPError as error:
            return error.code, error.read()
    monkeypatch.setattr(module, "_send_request", post)


class RetryClock:
    def __init__(self, monkeypatch):
        self.now = 0.0
        self.waits = []
        monkeypatch.setattr(module, "time", SimpleNamespace(monotonic=lambda: self.now))

    async def wait(self, seconds):
        self.waits.append(seconds)
        self.now += seconds


@pytest.mark.parametrize("failure_kind", ["http", "json", "transport"])
def test_five_exponential_retries_exclude_waits_from_request_budget(monkeypatch, failure_kind):
    clock = RetryClock(monkeypatch)
    timeouts = []
    payload = {"error": {"type": "service_unavailable_error", "message": "busy"}}

    def send(request, timeout):
        timeouts.append(timeout)
        clock.now += .2  # Request time is charged; retry backoff is not.
        if len(timeouts) == 6:
            return FakeHTTPResponse(200, {"choices": [{"message": {"content": "OK"}}]})
        if failure_kind == "http":
            raise http_error(503, payload)
        if failure_kind == "transport":
            raise TimeoutError("transient read failure")
        return FakeHTTPResponse(200, payload)

    stub_transport(monkeypatch, send)
    result = asyncio.run(module._api_completion("key", "deepseek-flash", [], timeout_sec=3,
                                                retry_wait=clock.wait))
    assert clock.waits == [2, 4, 8, 16, 32]
    assert timeouts == pytest.approx([3, 2.8, 2.6, 2.4, 2.2, 2])
    assert result["_api_attempts"] == 6
    assert result["_api_retry_wait_seconds"] == 62


def test_retry_exhaustion_stops_after_six_requests(monkeypatch):
    clock = RetryClock(monkeypatch)
    calls = []

    def send(request, timeout):
        calls.append(timeout)
        raise http_error(503, {"error": {"type": "service_unavailable_error"}})

    stub_transport(monkeypatch, send)
    with pytest.raises(module.DeepSeekProviderError) as raised:
        asyncio.run(module._api_completion("key", "deepseek-flash", [], timeout_sec=1,
                                           retry_wait=clock.wait))
    assert calls == [1] * 6
    assert clock.waits == [2, 4, 8, 16, 32]
    assert raised.value.metadata["attempt"] == raised.value.metadata["max_attempts"] == 6
    assert raised.value.metadata["retry_wait_seconds"] == 62


def test_cancellation_during_backoff_never_sends_next_request(monkeypatch):
    calls = []

    def send(request, timeout):
        calls.append(timeout)
        raise http_error(503, {"error": {"type": "service_unavailable_error"}})

    stub_transport(monkeypatch, send)

    async def check():
        waiting = asyncio.Event()

        async def wait(seconds):
            waiting.set()
            await asyncio.sleep(seconds)

        request = asyncio.create_task(module._api_completion("key", "deepseek-flash", [],
                                      timeout_sec=3, retry_wait=wait))
        await waiting.wait()
        request.cancel()
        with pytest.raises(asyncio.CancelledError):
            await request

    asyncio.run(check())
    assert len(calls) == 1


@pytest.mark.parametrize("transport", [False, True])
def test_spent_work_budget_does_not_start_another_retry(monkeypatch, transport):
    clock = RetryClock(monkeypatch)
    calls = []

    def send(request, timeout):
        calls.append(timeout)
        clock.now += 1
        if transport:
            raise TimeoutError("request spent its work allowance")
        raise http_error(503, {"error": {"type": "service_unavailable_error"}})

    stub_transport(monkeypatch, send)
    with pytest.raises((module.DeepSeekProviderError, TimeoutError)):
        asyncio.run(module._api_completion("key", "deepseek-flash", [], timeout_sec=1,
                                           retry_wait=clock.wait))
    assert calls == [1]
    assert clock.waits == []


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
        return SimpleNamespace(return_code=0, stdout="ok 42", stderr="")


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

    stub_transport(monkeypatch, fake_urlopen)
    result = asyncio.run(module._api_completion("actual-key", "deepseek-flash", [{"role": "user", "content": "x"}],
                                                timeout_sec=30, max_attempts=2))
    assert result["choices"][0]["message"]["content"] == "OK"
    assert len(calls) == 2
    assert result["_api_attempts"] == 2


@pytest.mark.parametrize("status", [400, 401, 402, 422])
def test_api_does_not_retry_permanent_http_errors(monkeypatch, status):
    calls = []

    def fake_urlopen(request, timeout):
        calls.append(timeout)
        raise http_error(status, {"error": {"type": "auth_error", "code": "permanent",
                                           "message": "Account rate limit requires a valid key or balance"}})

    stub_transport(monkeypatch, fake_urlopen)
    with pytest.raises(module.DeepSeekProviderError) as raised:
        asyncio.run(module._api_completion("actual-key", "deepseek-flash", [{"role": "user", "content": "x"}],
                                           timeout_sec=30, max_attempts=2))
    assert len(calls) == 1
    assert raised.value.metadata["status"] == status


def test_api_retries_http_200_rate_limit_error_then_success(monkeypatch):
    responses = [FakeHTTPResponse(200, {"error": {"type": "rate_limit_error", "code": "busy", "message": "later"}}),
                 FakeHTTPResponse(200, {"choices": [{"message": {"content": "OK", "tool_calls": None}}]})]
    stub_transport(monkeypatch, lambda request, timeout: responses.pop(0))
    result = asyncio.run(module._api_completion("actual-key", "deepseek-flash", [{"role": "user", "content": "x"}],
                                                timeout_sec=30, max_attempts=2))
    assert result["choices"][0]["message"]["content"] == "OK"


def test_api_malformed_response_preserves_bounded_metadata_and_redacts_key(monkeypatch):
    key = "actual-secret-key"
    payload = {"type": key, "message": f"quoted '{key}' and Bearer {key}", "extra": "x" * 5000}
    stub_transport(monkeypatch, lambda request, timeout: FakeHTTPResponse(200, payload))
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
    assert usage["input_tokens"] is None and usage["output_tokens"] is None
    assert usage["cached_input_tokens"] is None and usage["reasoning_output_tokens"] is None
    assert usage["accounting"] == "known_completed_calls_plus_unknown_inflight"
    process = json.loads((tmp_path / "logs/repair-process.json").read_text())
    assert process["usage"]["unknown_inflight_request"] is True


def test_fallback_error_redacts_the_actual_key_in_every_field():
    key = "test-key-unique-value"
    error = module._provider_response_error({"error": {"type": key, "code": key,
                                                       "message": f"Invalid credential '{key}'"}}, key)
    assert key not in json.dumps(error)


def test_success_after_retry_keeps_prefix_usage_but_not_false_total(tmp_path, monkeypatch):
    agent = make_agent(tmp_path, condition="baseline")
    agent.environment = FakeEnvironment(tmp_path, {}, {})
    agent.root = "/app/task_058"
    agent.logs_dir.mkdir(parents=True, exist_ok=True)
    async def fake_api(*args, **kwargs):
        return {"_api_attempts": 2, "choices": [{"message": {"content": "DONE"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 3}}
    monkeypatch.setattr(module, "_api_completion", fake_api)
    result = asyncio.run(agent._run_deepseek_repair("Fix", 60))
    assert result["status"] == "completed" and result["api_retry_requests"] == 1
    assert result["usage"]["input_tokens"] is None
    assert result["usage"]["known_usage"]["input_tokens"] == 10


@pytest.mark.parametrize("error_type", [[], {}])
def test_malformed_error_type_is_not_itself_a_parser_crash(error_type):
    assert module._provider_retryable(200, {"type": error_type}) is False


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


@pytest.mark.parametrize("condition", ["baseline", "science"])
def test_retry_then_tool_and_final_survive_all_work_timers(tmp_path, monkeypatch, condition):
    from scicontext.controller import TrialConfig, run_trial
    agent = make_agent(tmp_path, condition=condition)
    agent.environment = FakeEnvironment(tmp_path, {}, {})
    agent.root = "/app/task_synthetic"
    agent.logs_dir.mkdir(parents=True)
    agent.prepare = AsyncMock(return_value={"status": "completed"})
    agent.collect_graph = AsyncMock(return_value={"graph_sha256": "a" * 64, "handoff": "context",
                                                  "graph": {"nodes": [{"id": "synthetic"}]}})
    agent.cleanup = AsyncMock()
    # A real async backoff longer than the entire work budget; no network or paid calls.
    monkeypatch.setattr(module, "API_RETRY_DELAYS", (3, 6, 12, 24, 48))
    responses = [
        http_error(503, {"error": {"type": "service_unavailable_error"}}),
        FakeHTTPResponse(200, {"choices": [{"message": {"tool_calls": [
            {"id": "c1", "function": {"name": "shell", "arguments": '{"command":"true"}'}}]}}]}),
        FakeHTTPResponse(200, {"choices": [{"message": {"content": "DONE"}}]}),
    ]

    def send(request, timeout):
        assert 0 < timeout <= 2
        response = responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    stub_transport(monkeypatch, send)
    record = asyncio.run(run_trial(agent, TrialConfig(total_seconds=2, extraction_seconds=.5),
                                   "synthetic", condition, "Fix", tmp_path / "trial"))
    assert record["status"] == "completed"
    assert record["duration_seconds"] >= 3
    assert record["provider_retry_wait_seconds"] >= 3
    assert record["work_seconds"] < 2 and record["over_budget_seconds"] == 0
    assert responses == [] and "true" in agent.environment.commands
    process = json.loads((agent.logs_dir / "repair-process.json").read_text())
    assert process["provider_retry_wait_seconds"] >= 3
    assert process["api_retry_requests"] == 1
    waits = [json.loads(line) for line in (agent.logs_dir / "repair-session.jsonl").read_text().splitlines()
             if json.loads(line).get("type") == "provider_retry_wait"]
    assert len(waits) == 1 and waits[0]["charged_to_work_budget"] is False


def test_glm_request_preserves_reasoning_and_uses_coding_endpoint(monkeypatch):
    messages = [{"role": "assistant", "reasoning_content": "prior thought", "tool_calls": []},
                {"role": "user", "content": "Continue"}]

    def send(request, seconds):
        assert request.full_url == "https://api.z.ai/api/coding/paas/v4/chat/completions"
        body = json.loads(request.data)
        assert body["model"] == "glm-5.3-flash" and body["reasoning_effort"] == "low"
        assert body["thinking"] == {"type": "enabled", "clear_thinking": False}
        assert body["messages"] == messages
        assert request.get_header("Authorization") == "Bearer synthetic-key"
        assert "opencode" not in str(request.headers).lower()
        return FakeHTTPResponse(200, {"choices": [{"message": {"content": "OK"}}]})

    stub_transport(monkeypatch, send)
    response = asyncio.run(module._api_completion("synthetic-key", "glm-5.3-flash", messages,
                           timeout_sec=5, reasoning_effort="low", api_provider="zai-coding-plan"))
    assert response["choices"][0]["message"]["content"] == "OK"


def test_glm_top_level_error_preserves_code_without_echoing_key(monkeypatch):
    stub_transport(monkeypatch, lambda request, seconds: FakeHTTPResponse(400,
        {"code": "1113", "message": "balance unavailable synthetic-key"}))
    with pytest.raises(module.DeepSeekProviderError) as raised:
        asyncio.run(module._api_completion("synthetic-key", "glm-5.3-flash", [], timeout_sec=5,
                                           api_provider="zai-coding-plan", reasoning_effort="low"))
    assert raised.value.metadata["code"] == "1113"
    assert raised.value.metadata["attempt"] == 1
    assert "synthetic-key" not in json.dumps(raised.value.metadata)


def test_glm_usage_counts_cache_and_preserves_unknown_reasoning():
    totals = dict.fromkeys(["input_tokens", "output_tokens", "cached_input_tokens", "cache_hit_tokens",
                            "cache_miss_tokens", "reasoning_output_tokens"], 0)
    module._add_usage(totals, {"prompt_tokens": 100, "completion_tokens": 20,
                                "prompt_tokens_details": {"cached_tokens": 80}})
    assert totals == {"input_tokens": 100, "output_tokens": 20, "cached_input_tokens": 80,
                      "cache_hit_tokens": 80, "cache_miss_tokens": 20, "reasoning_output_tokens": None}
    module._add_usage(totals, {})
    assert all(value is None for value in totals.values())


@pytest.mark.parametrize("arguments", ['{"command":"true"}', {"command": "true"}])
def test_glm_tool_arguments_support_both_documented_shapes(tmp_path, arguments):
    agent = make_agent(tmp_path)
    agent.environment = FakeEnvironment(tmp_path, {}, {})
    agent.root = "/app/task_synthetic"
    output, event = asyncio.run(agent._execute_tool({"function": {"name": "shell", "arguments": arguments}}, 5))
    assert event["exit_code"] == 0 and "true" in agent.environment.commands


@pytest.mark.parametrize("reason", ["network_error", "sensitive", "model_context_window_exceeded"])
def test_glm_incomplete_finish_is_not_success(reason):
    error = module._provider_response_error({"choices": [{"message": {"content": "partial"}, "finish_reason": reason}]})
    assert error["code"] == reason


def test_http_request_deadline_cancels_transport_and_closes_client(monkeypatch):
    closed = []
    original = module.httpx.AsyncClient

    async def stalled(request):
        try:
            await asyncio.sleep(10)
        finally:
            closed.append("cancelled")

    client = original(transport=module.httpx.MockTransport(stalled))
    monkeypatch.setattr(module.httpx, "AsyncClient", lambda **kwargs: client)
    request = module.urllib.request.Request("https://example.invalid/completion", data=b"{}", method="POST")
    with pytest.raises(TimeoutError):
        asyncio.run(module._send_request(request, .05))
    assert closed == ["cancelled"] and client.is_closed
