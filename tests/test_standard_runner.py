import asyncio
from types import SimpleNamespace

import pytest

pytest.importorskip("pier")

from pier.agents.installed.codex import Codex
from pier.models.agent.context import AgentContext
from scicontext.pier_agent import OutputCodex, timeout_launcher


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


@pytest.mark.parametrize("stage", ["extract", "repair"])
def test_both_stages_use_plain_final_files(tmp_path, stage):
    agent = OutputCodex(stage=stage, logs_dir=tmp_path, model_name="gpt-6-astra")
    assert "--output-schema" not in agent.build_cli_flags()
    assert stage + "-final.txt" in agent.build_cli_flags()


def test_deadline_uses_standard_timeout_not_custom_supervisor():
    script = timeout_launcher("/opt/codex/bin/codex")
    assert "timeout --signal=TERM --kill-after=3s" in script
    assert "SCICONTEXT_STAGE_SECONDS" in script
    assert "scicontext.supervise" not in script and "/proc" not in script
