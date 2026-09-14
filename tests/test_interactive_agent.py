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


@pytest.mark.parametrize("condition", ["baseline", "science"])
def test_host_api_agent_uses_pier_offline_mode_without_egress_proxy(tmp_path, monkeypatch, condition):
    from types import SimpleNamespace
    from pier.environments.docker import docker as docker_module

    model = agent(tmp_path, condition)
    allowlist = model.network_allowlist()
    assert allowlist.domains == [], "Host-side DeepSeek calls need no in-container OpenAI proxy"
    env = SimpleNamespace(network_allowlist=allowlist,
                          task_env_config=SimpleNamespace(allow_internet=False),
                          _egress_proxy_compose_path=None)
    def unexpected_proxy(**kwargs):
        pytest.fail("An offline task must not create a per-trial inference proxy")
    monkeypatch.setattr(docker_module, "write_docker_proxy_compose", unexpected_proxy)
    docker_module.DockerEnvironment._prepare_egress_proxy_compose(env)
    assert env._egress_proxy_compose_path is None
    env._use_prebuilt = True
    env._resources_compose_path = None
    env._is_windows_container = False
    env._mounts_compose_path = None
    env._environment_docker_compose_path = tmp_path / "absent-compose.yaml"
    cls = docker_module.DockerEnvironment
    for name in ("_DOCKER_COMPOSE_BASE_PATH", "_DOCKER_COMPOSE_PREBUILT_PATH",
                 "_DOCKER_COMPOSE_NO_NETWORK_PATH"):
        setattr(env, name, getattr(cls, name))
    assert cls._docker_compose_paths.fget(env)[-1] == cls._DOCKER_COMPOSE_NO_NETWORK_PATH


def test_plain_baseline_setup_does_not_expose_science_assets(tmp_path, monkeypatch):
    model = agent(tmp_path, "baseline")
    model.task_id = "test"
    commands = []

    class Env:
        async def upload_dir(self, *args):
            pytest.fail("plain baseline must not receive scientific helper assets")

    async def checked(environment, command, **kwargs):
        commands.append(command)
        return "statm"

    model.checked = checked
    asyncio.run(model._setup_environment(Env(), "repair"))
    assert commands[0] == "mkdir -p /app/task_test/outputs"
    assert any(command.startswith("python -c ") for command in commands[1:])
    assert all("/opt/scicontext" not in command for command in commands)


def test_science_agent_has_graph_tool_and_shell_from_the_start(tmp_path, monkeypatch):
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
        assert available == ["shell", "science_find", "science_inspect", "science_note"]
        step = len(snapshots)
        if step == 1:
            calls = [call("shell", {"command": "run-public-check"}, "shell"),
                     call("science_find", {"query": "storage"}, "find")]
        elif step == 2:
            calls = [call("science_inspect", {"target": "m.py#step"}, "inspect")]
        elif step == 3:
            result = queries[-1][1]
            calls = [call("science_note", {"target": result["note_target"], "source_ids": result["note_source_ids"],
                "meaning": "Stored quantity changes by outward flux times elapsed duration.",
                "expected_change": "Fix the requested update.", "preserve": ["Outward-flux sign convention."]}, "record")]
        else:
            calls = None
        return {"choices": [{"message": {"content": "DONE" if not calls else None, "tool_calls": calls},
                              "finish_reason": "tool_calls" if calls else "stop"}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "prompt_cache_hit_tokens": 8,
                          "prompt_cache_miss_tokens": 2, "completion_tokens_details": {"reasoning_tokens": 3}}}
    monkeypatch.setattr(module, "_api_completion", api)
    result = asyncio.run(model._run_deepseek_repair("TASK", 30))
    assert commands == ["run-public-check"], "shell works before any model is recorded"
    assert result["status"] == "completed" and result["scientific_model_recorded"]
    assert all(snapshot[0] == {"role": "user", "content": "TASK"} for snapshot in snapshots)
    assert (tmp_path / "science/scientific-model.json").is_file()
    usage = read_usage(tmp_path / "logs/repair.jsonl")
    assert (usage["input_tokens"], usage["cached_input_tokens"], usage["output_tokens"], usage["reasoning_output_tokens"]) == (40, 32, 20, 12)


def test_science_run_completes_without_recorded_model(tmp_path, monkeypatch):
    model = agent(tmp_path)
    class Env:
        async def download_dir(self, *args): pass
    model.environment = Env()
    async def api(*args, **kwargs):
        assert [t["function"]["name"] for t in kwargs["tools"]] == ["shell", "science_find", "science_inspect", "science_note"]
        return {"choices": [{"message": {"content": "DONE"}, "finish_reason": "stop"}], "usage": {}}
    monkeypatch.setattr(module, "_api_completion", api)
    result = asyncio.run(model._run_deepseek_repair("TASK", 30))
    assert result["status"] == "completed"
    assert result["scientific_model_recorded"] is False


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
    output, event = asyncio.run(model._execute_tool(call("science_find", {"query": "energy", "command": "do-not-execute"}, "x"), 10))
    assert event["type"] == "science_tool"
    assert not model._science_model_recorded


def test_preparation_has_zero_model_calls(tmp_path):
    model = agent(tmp_path)
    async def science(request, seconds, prepare=False):
        assert prepare and request is None
        return {"status": "prepared", "task_map": [], "files_indexed": 2,
                "scientific_graph": {"nodes": 3, "edges": 2, "findings": 1, "bytes": 1200}}
    model._science_command = science
    result = asyncio.run(model.prepare(10))
    assert result["model_calls"] == []
    assert result["usage"]["input_tokens"] == result["usage"]["output_tokens"] == 0


def test_preparation_refuses_index_only_science(tmp_path):
    model = agent(tmp_path)
    async def science(request, seconds, prepare=False):
        return {"status": "prepared", "task_map": [], "files_indexed": 2, "scientific_graph": None}
    model._science_command = science
    with pytest.raises(RuntimeError, match="refusing index-only science"):
        asyncio.run(model.prepare(10))


def test_finish_extraction_persists_science_store_once(tmp_path):
    model = agent(tmp_path)
    calls = []
    class Env:
        async def download_dir(self, remote, local):
            calls.append((remote, local))
            local.mkdir(parents=True, exist_ok=True)
            (local / "state.json").write_text("{}")
    model.environment = Env()
    asyncio.run(model.finish_extraction())
    assert calls and calls[0][1].name == "science"
    asyncio.run(model.finish_extraction())
    assert len(calls) == 1
