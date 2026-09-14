import asyncio
import copy
import json

import pytest

from scicontext.deepseek_agent import DeepSeekAgent
from scicontext import deepseek_agent as module
from scicontext.science_tools import ScienceStore
from scicontext.controller import read_usage


def call(name, args, identifier):
    return {"id": identifier, "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}


def agent(tmp_path, condition="science"):
    key = tmp_path / "key.json"
    key.write_text(json.dumps({"api_key": "test-not-a-credential"}))
    value = DeepSeekAgent(logs_dir=tmp_path / "logs", model_name="deepseek-flash", condition=condition,
                          workspace=tmp_path, deepseek_key_file=key)
    value.logs_dir.mkdir()
    value.root = "/app/task_test"
    return value


def test_same_agent_queries_records_then_repairs_with_enforced_tools(tmp_path, monkeypatch):
    model = agent(tmp_path)
    root = tmp_path / "task"
    root.mkdir()
    (root / "m.py").write_text('def step(q, flux, dt):\n    """Positive flux leaves storage."""\n    return q-flux*dt\n')
    store = ScienceStore(root, tmp_path / "science")
    store.prepare()
    queries, commands, snapshots = [], [], []
    async def science(request, seconds, prepare=False):
        result = store.dispatch(request)
        queries.append((request, result))
        return result
    model._science_command = science
    class Env:
        async def download_dir(self, *args): pass
    model.environment = Env()
    async def checked(environment, command, **kwargs):
        commands.append(command)
        return "42"
    model.checked = checked
    async def api(key, name, messages, **kwargs):
        assert kwargs["reasoning_effort"] == "high"
        snapshots.append(copy.deepcopy(messages))
        available = [t["function"]["name"] for t in kwargs["tools"]]
        step = len(snapshots)
        assert available == (["science"] if step <= 3 else ["science", "shell"])
        if step == 1:
            calls = [call("shell", {"command": "must-not-run"}, "bad"),
                     call("science", {"action": "find", "query": "storage"}, "find")]
        elif step == 2:
            calls = [call("science", {"action": "inspect", "target": "m.py#step"}, "inspect")]
        elif step == 3:
            result = queries[-1][1]
            cid = result["computations"][0]["id"]
            sid = result["sources"][0]["id"]
            claim = {"text": "Stored quantity changes by outward flux times elapsed duration.", "source_ids": [sid]}
            working = {"purpose": claim, "expected_change": claim, "preserve": [claim],
                "computations": [{"computation_id": cid, "meaning": claim, "quantities": [], "conventions": [], "assumptions": []}]}
            calls = [call("science", {"action": "record_model", "model": working}, "record"),
                     call("shell", {"command": "echo 42"}, "shell")]
        else:
            calls = None
        return {"choices": [{"message": {"content": "DONE" if not calls else None, "tool_calls": calls},
                              "finish_reason": "tool_calls" if calls else "stop"}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "prompt_cache_hit_tokens": 8,
                          "prompt_cache_miss_tokens": 2, "completion_tokens_details": {"reasoning_tokens": 3}}}
    monkeypatch.setattr(module, "_api_completion", api)
    result = asyncio.run(model._run_deepseek_repair("TASK", 30))
    assert commands == ["echo 42"]
    assert result["scientific_model_recorded"]
    assert all(snapshot[0] == {"role": "user", "content": "TASK"} for snapshot in snapshots)
    assert any("must-not-run" in json.dumps(snapshot) for snapshot in snapshots[1:])
    assert (tmp_path / "science/scientific-model.json").is_file()
    usage = read_usage(tmp_path / "logs/repair.jsonl")
    assert (usage["input_tokens"], usage["cached_input_tokens"], usage["output_tokens"], usage["reasoning_output_tokens"]) == (40, 32, 20, 12)


def test_baseline_never_receives_science_tool(tmp_path, monkeypatch):
    model = agent(tmp_path, "baseline")
    async def api(*args, **kwargs):
        assert [t["function"]["name"] for t in kwargs["tools"]] == ["shell"]
        return {"choices": [{"message": {"content": "DONE"}, "finish_reason": "stop"}], "usage": {}}
    monkeypatch.setattr(module, "_api_completion", api)
    result = asyncio.run(model._run_deepseek_repair("ORIGINAL TASK", 30))
    assert result["scientific_model_recorded"] is None


def test_science_named_call_cannot_smuggle_shell_command(tmp_path):
    model = agent(tmp_path)
    async def command(request, seconds):
        assert request["action"] == "find"
        return {"status": "ok", "matches": []}
    model._science_command = command
    output, event = asyncio.run(model._execute_tool(call("science", {"action": "find", "query": "energy", "command": "do-not-execute"}, "x"), 10))
    assert event["type"] == "science_tool"
    assert not model._science_model_recorded


def test_preparation_has_zero_model_calls(tmp_path):
    model = agent(tmp_path)
    async def science(request, seconds, prepare=False):
        assert prepare and request is None
        return {"status": "prepared", "task_map": [], "files_indexed": 2}
    model._science_command = science
    result = asyncio.run(model.prepare(10))
    assert result["model_calls"] == []
    assert result["usage"]["input_tokens"] == result["usage"]["output_tokens"] == 0
