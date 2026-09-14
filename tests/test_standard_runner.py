import asyncio
import hashlib
import json
import os
import subprocess
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

pytest.importorskip("pier")

from pier.agents.installed.codex import Codex
from pier.models.agent.context import AgentContext
from scicontext.pier_agent import OutputCodex, ScientificCodex, timeout_launcher


@pytest.mark.parametrize("stage", ["extract_draft", "repair"])
def test_large_prompt_uses_byte_exact_stdin_through_upstream_launch(tmp_path, stage):
    # Larger than host ARG_MAX; includes shell metacharacters and multibyte text.
    payload = ('science λ\n"quotes" $HOME `not-a-command` \\\n' * 200000).encode()
    prompt = tmp_path / "prompt with spaces.txt"
    prompt.write_bytes(payload)
    binary = tmp_path / "codex"
    binary.write_text(
        "#!/usr/bin/env python3\nimport hashlib,json,sys\n"
        "print(json.dumps({'sha256':hashlib.sha256(sys.stdin.buffer.read()).hexdigest(),'argv':sys.argv[1:]}))\n")
    binary.chmod(0o755)
    agent = OutputCodex(stage=stage, prompt_path=str(prompt), logs_dir=tmp_path / "logs",
                        model_name="gpt-6-astra", extra_env={"PATH": str(tmp_path) + os.pathsep + os.environ["PATH"]})
    class Environment:
        default_user = None
        def agent_process_env(self, env):
            return env
        async def exec(self, command, **kwargs):
            if "codex exec " in command:
                assert len(command.encode()) < 8192
                assert "</dev/null" not in command
                command = command.replace("/logs/agent/" + stage + ".jsonl", str(tmp_path / "events.jsonl"))
                result = subprocess.run(["/bin/bash", "-c", command], env={**os.environ, **kwargs.get("env", {})},
                                        text=True, capture_output=True, check=True)
                self.observed = json.loads(result.stdout)
            return SimpleNamespace(return_code=0, stdout="", stderr="")
    environment = Environment()
    asyncio.run(agent.run("-", environment, AgentContext()))
    assert environment.observed["sha256"] == hashlib.sha256(payload).hexdigest()
    assert environment.observed["argv"][-2:] == ["--", "-"]


def test_reuses_upstream_run_without_reimplementing_authentication(tmp_path):
    assert OutputCodex.run is Codex.run
    auth = tmp_path / "auth.json"
    auth.write_text('{"auth_mode":"chatgpt","tokens":{"access_token":"dummy"}}')
    agent = OutputCodex(stage="extract", logs_dir=tmp_path / "logs", model_name="gpt-6-astra",
                        reasoning_effort="high", version="0.153.4",
                        extra_env={"CODEX_AUTH_JSON_PATH": str(auth)})
    class Environment:
        default_user = None
        def __init__(self):
            self.commands = []
            self.uploads = []
        def agent_process_env(self, env):
            return env
        async def exec(self, command, **kwargs):
            self.commands.append(command)
            return SimpleNamespace(return_code=0, stdout="", stderr="")
        async def upload_file(self, source, target):
            self.uploads.append((source, target))
    environment = Environment()
    asyncio.run(agent.run("Inspect scientific context", environment, AgentContext()))
    launch = next(command for command in environment.commands if "codex exec " in command)
    assert "--dangerously-bypass-approvals-and-sandbox" in launch
    assert "--enable unified_exec" in launch
    assert "--output-schema" not in launch
    assert "-o /logs/agent/extract-final.txt" in launch
    assert "model_reasoning_effort=high" in launch
    assert environment.uploads == [(auth, "/tmp/codex-secrets/auth.json")]
    assert any("rm -rf /tmp/codex-secrets" in command for command in environment.commands)
    assert all("--permission-profile" not in command for command in environment.commands)


@pytest.mark.parametrize("stage", ["extract", "extract_draft", "repair"])
def test_both_stages_use_plain_final_files(tmp_path, stage):
    agent = OutputCodex(stage=stage, logs_dir=tmp_path, model_name="gpt-6-astra")
    assert "--output-schema" not in agent.build_cli_flags()
    assert stage + "-final.txt" in agent.build_cli_flags()
    assert agent.build_cli_flags() == Codex.build_cli_flags(agent) + f" -o /logs/agent/{stage}-final.txt"


def test_deadline_uses_standard_timeout_not_custom_supervisor():
    script = timeout_launcher("/opt/codex/bin/codex")
    assert "timeout --signal=TERM --kill-after=3s" in script
    assert "SCICONTEXT_STAGE_SECONDS" in script
    assert "scicontext.supervise" not in script and "/proc" not in script


@pytest.mark.parametrize("stage", ["extract", "extract_draft", "repair"])
def test_launcher_replaces_pier_bypass_only_for_extraction(tmp_path, stage):
    binary = tmp_path / "codex"
    binary.write_text('#!/bin/sh\nprintf "%s\\n" "$@"\n')
    binary.chmod(0o755)
    original = ["exec", "--dangerously-bypass-approvals-and-sandbox", "--json", "task with spaces"]
    result = subprocess.run(["/bin/sh", "-c", timeout_launcher(str(binary)), "launcher", *original],
                            env={**os.environ, "SCICONTEXT_STAGE_NAME": stage, "SCICONTEXT_STAGE_SECONDS": ""},
                            text=True, capture_output=True, check=True)
    actual = result.stdout.splitlines()
    expected = (["exec", "--sandbox", "read-only", "-c", 'approval_policy="never"', *original[2:]]
                if stage.startswith("extract") else original)
    assert actual == expected
    assert not ("--sandbox" in actual and "--dangerously-bypass-approvals-and-sandbox" in actual)




@pytest.mark.parametrize("model_cap", [None, 360])
def test_each_call_uses_extraction_environment_distinct_logs_and_sessions(tmp_path, monkeypatch, model_cap):
    import scicontext.pier_agent as module
    launched = []
    class Environment:
        def __init__(self):
            self.files = {}
            self.dirs = []
        async def upload_file(self, local, remote):
            self.files[remote] = local.read_text()
        async def download_file(self, remote, local):
            local.write_text(self.files[remote])
        async def download_dir(self, remote, local):
            self.dirs.append(remote)
    environment = Environment()
    async def run(agent, instruction, env, context):
        assert env is environment
        assert instruction == "-"
        assert env.files[agent.prompt_path] == "draft"
        duration = float(agent._extra_env["SCICONTEXT_STAGE_SECONDS"].removesuffix("s"))
        assert duration == 360 if model_cap is not None else duration > 360
        launched.append((agent.stage, str(agent._REMOTE_CODEX_HOME), agent._OUTPUT_FILENAME))
        env.files[f"/logs/agent/{agent.stage}.jsonl"] = json.dumps({"type": "turn.completed", "usage": {
            "input_tokens": 3, "cached_input_tokens": 1, "output_tokens": 2}}) + "\n"
        env.files[f"/logs/agent/{agent.stage}-exit.txt"] = "0"
        env.files[f"/logs/agent/{agent.stage}-final.txt"] = "{}"
    monkeypatch.setattr(Codex, "run", run)
    d = SimpleNamespace(extract_environment=environment, environment=object(), root="/app/task_058",
                        extraction_model_seconds=model_cap,
                        config=SimpleNamespace(model="gpt-6-astra", reasoning_effort="high", codex_version="0.153.4"),
                        logs_dir=tmp_path, auth_file=tmp_path / "dummy-auth.json")
    d.checked = AsyncMock(return_value="/usr/bin")
    async def check():
        first = await ScientificCodex._run_codex(d, "extract_draft", "draft", 600)
        assert first["status"] == "completed"
        assert first["usage"]["input_tokens"] == 3
    asyncio.run(check())
    assert [home for _, home, _ in launched] == ["/tmp/scicontext-codex-extract_draft"]
    assert [filename for _, _, filename in launched] == ["extract_draft.jsonl"]
    assert environment.dirs == ["/logs/agent/extract_draft-sessions"]
    assert all((tmp_path / f"{name}-process.json").is_file() for name, _, _ in launched)
    assert all("rm -rf /logs/agent" not in c.args[1] for c in d.checked.await_args_list)


@pytest.mark.parametrize("outer_cancel", [False, True])
def test_upstream_finally_cannot_hold_call_past_deadline(tmp_path, monkeypatch, outer_cancel):
    async def check():
        release = asyncio.Event()
        entered = asyncio.Event()
        async def run(*args):
            try:
                entered.set()
                await asyncio.sleep(10)
            finally:
                # Simulate an upstream artifact/auth cleanup awaiting remote I/O.
                await release.wait()
        monkeypatch.setattr(Codex, "run", run)
        env = SimpleNamespace(upload_file=AsyncMock(), download_file=AsyncMock(side_effect=OSError("unavailable")),
                              download_dir=AsyncMock())
        d = SimpleNamespace(extract_environment=env, environment=env, root="/app/task_058",
                            extraction_model_seconds=None, config=SimpleNamespace(model="gpt-6-astra", reasoning_effort="high", codex_version="0.153.4"),
                            logs_dir=tmp_path, auth_file=tmp_path / "dummy", checked=AsyncMock(return_value="/usr/bin"))
        started = time.monotonic()
        task = asyncio.create_task(ScientificCodex._run_codex(d, "extract_draft", "task", .12))
        await entered.wait()
        try:
            if outer_cancel:
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task
                result = json.loads((tmp_path / "extract_draft-process.json").read_text())
                assert result["status"] == "interrupted"
            else:
                result = await task
                assert result["status"] == "timeout"
            assert time.monotonic() - started < .3
            assert result["fatal_model_error"] and result["upstream_cleanup_pending"]
            assert d._fatal_model_error  # survives cancellation before a receipt can be returned
            assert result["usage"]["input_tokens"] is None
        finally:
            release.set()
            await asyncio.gather(*d._pending_codex_io, return_exceptions=True)
    asyncio.run(check())


def test_artifact_downloads_cannot_hold_call_past_deadline(tmp_path, monkeypatch):
    async def check():
        monkeypatch.setattr(Codex, "run", AsyncMock())
        async def stalled(*args):
            await asyncio.sleep(10)
        env = SimpleNamespace(upload_file=AsyncMock(), download_file=stalled, download_dir=stalled)
        d = SimpleNamespace(extract_environment=env, environment=env, root="/app/task_058",
                            extraction_model_seconds=None, config=SimpleNamespace(model="gpt-6-astra", reasoning_effort="high", codex_version="0.153.4"),
                            logs_dir=tmp_path, auth_file=tmp_path / "dummy", checked=AsyncMock(return_value="/usr/bin"))
        started = time.monotonic()
        result = await ScientificCodex._run_codex(d, "extract_draft", "task", .1)
        assert time.monotonic() - started < .3
        assert "collection deadline exceeded" in result["artifact_collection_errors"]
        assert result["fatal_model_error"] and result["usage"]["input_tokens"] is None
    asyncio.run(check())


@pytest.mark.parametrize("stage", ["extract_draft", "repair"])
def test_provider_failure_receipt_is_fatal_for_every_call(tmp_path, monkeypatch, stage):
    async def check():
        async def run(*args):
            raise RuntimeError("provider quota exceeded")
        monkeypatch.setattr(Codex, "run", run)
        async def download(remote, local):
            if remote.endswith("-exit.txt"):
                local.write_text("1")
            elif remote.endswith(".jsonl"):
                local.write_text('{"type":"error","message":"quota exceeded"}\n')
            else:
                raise OSError("missing")
        env = SimpleNamespace(upload_file=AsyncMock(), download_file=download, download_dir=AsyncMock())
        d = SimpleNamespace(extract_environment=env, environment=env, root="/app/task_058",
                            extraction_model_seconds=None, config=SimpleNamespace(model="gpt-6-astra", reasoning_effort="high", codex_version="0.153.4"),
                            logs_dir=tmp_path, auth_file=tmp_path / "dummy", checked=AsyncMock(return_value="/usr/bin"))
        result = await ScientificCodex._run_codex(d, stage, "task", 1)
        assert result["status"] == "failed" and result["fatal_model_error"]
        assert "quota exceeded" in result["error"]
        assert json.loads((tmp_path / f"{stage}-process.json").read_text()) == result
        assert "quota exceeded" in (tmp_path / f"{stage}.jsonl").read_text()
    asyncio.run(check())
