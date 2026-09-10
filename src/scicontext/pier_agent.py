"""Standard Pier Codex execution plus the bounded scientific-context pass."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import json
import math
import shlex
import subprocess
import tempfile
import time
from pathlib import Path

from pier.agents.base import BaseAgent
from pier.agents.installed.base import NonZeroAgentExitCodeError
from pier.agents.installed.codex import Codex
from pier.environments.docker.docker import DockerEnvironment
from pier.models.agent.context import AgentContext
from pier.models.agent.network import NetworkAllowlist
from pier.models.trial.paths import TrialPaths

from .assets import prepare_codex, prepare_helpers
from .annotations import annotation_schema
from .configuration import codex_config
from .controller import TrialConfig, read_usage, run_trial, verify_smoke
from .extraction import run_extraction
from .io import digest_file, read_json, write_json

REMOTE = "/opt/scicontext"
CONTROL = REMOTE + "/runtime"
SCRATCH = REMOTE + "/scratch"
HELPER = f"SCICONTEXT_CONTEXT_ROOT={REMOTE}/context PYTHONPATH={REMOTE}/src:{REMOTE}/deps python -m scicontext.tool_cli"


class OutputCodex(Codex):
    """Keep upstream launch/auth/cleanup; only add output collection flags."""

    def __init__(self, *args, stage: str, **kwargs):
        if stage not in {"extract", "repair"}:
            raise ValueError("Unknown Codex stage")
        self.stage = stage
        super().__init__(*args, **kwargs)

    def build_cli_flags(self):
        return super().build_cli_flags() + f" -o /logs/agent/{self.stage}-final.txt"


def timeout_launcher(binary: str) -> str:
    """Use native read-only Codex for extraction and GNU timeout for both stages."""
    return f'''#!/bin/sh
if [ "${{SCICONTEXT_STAGE_NAME:-}}" = extract ] && [ "${{1:-}}" = exec ] && [ "${{2:-}}" = --dangerously-bypass-approvals-and-sandbox ]; then
  shift 2
  set -- exec --sandbox read-only -c 'approval_policy="never"' "$@"
fi
if [ -z "${{SCICONTEXT_STAGE_SECONDS:-}}" ]; then
  exec {shlex.quote(binary)} "$@"
fi
timeout --signal=TERM --kill-after=3s "$SCICONTEXT_STAGE_SECONDS" {shlex.quote(binary)} "$@"
status=$?
printf '%s\\n' "$status" > "/logs/agent/$SCICONTEXT_STAGE_NAME-exit.txt"
exit "$status"
'''


class ScientificCodex(BaseAgent):
    SUPPORTS_ATIF = False

    def __init__(self, *args, condition="baseline", total_seconds=1800,
                 extraction_seconds=360, reasoning_effort="high", codex_version="0.153.4",
                 workspace=None, auth_file=None, smoke=False, extraction_only=False, **kwargs):
        super().__init__(*args, **kwargs)
        if condition not in {"baseline", "science"}:
            raise ValueError("Unknown experiment condition")
        if codex_version != "0.153.4":
            raise ValueError("This experiment pins Codex 0.153.4")
        self.condition = condition
        self.config = TrialConfig(self.model_name or "gpt-6-astra", reasoning_effort,
                                  codex_version, float(total_seconds), float(extraction_seconds))
        self.workspace = Path(workspace or Path.cwd()).resolve()
        self.auth_file = Path(auth_file or "").expanduser()
        if not self.auth_file.is_file():
            raise ValueError("A private subscription auth-file path is required; no API fallback")
        self.smoke = str(smoke).lower() in {"true", "1"}
        self.extraction_only = str(extraction_only).lower() in {"true", "1"}
        self.environment = None
        self.extract_environment = None
        self._finished_extraction = False
        self._temporary = tempfile.TemporaryDirectory(prefix="scicontext-assets-")

    @staticmethod
    def name():
        return "scicontext-codex"

    def version(self):
        return "0.3.0"

    def network_allowlist(self):
        return NetworkAllowlist(domains=["chatgpt.com", "auth.openai.com", "auth0.openai.com", "api.openai.com"])

    async def checked(self, environment, command, **kwargs):
        result = await environment.exec(command, **kwargs)
        if result.return_code:
            raise RuntimeError(f"Command failed ({result.return_code}): {command[:180]}\n{(result.stderr or result.stdout or '')[-1500:]}")
        return result.stdout or ""

    async def _put(self, environment, name, text, destination):
        path = Path(self._temporary.name) / name
        path.write_text(text)
        await environment.upload_file(path, destination)

    async def _setup_environment(self, environment, stage):
        package = self.extract_codex_package if stage == "extract" else self.codex_package
        architecture = self.extraction_architecture if stage == "extract" else "x64"
        triple = "aarch64" if architecture == "arm64" else "x86_64"
        binary = REMOTE + f"/codex/vendor/{triple}-unknown-linux-musl/bin/codex"
        await self.checked(environment, f"mkdir -p {CONTROL} {REMOTE}/bin {REMOTE}/src {REMOTE}/context {SCRATCH}/checkpoints {self.root}/outputs")
        await environment.upload_dir(package, REMOTE + "/codex")
        await environment.upload_dir(self.helper_deps, REMOTE + "/deps")
        await environment.upload_dir(self.workspace / "src/scicontext", REMOTE + "/src/scicontext")
        await self._put(environment, "codex-launcher", timeout_launcher(binary), REMOTE + "/bin/codex")
        await self.checked(environment, f"chmod 755 {REMOTE}/bin/codex; command -v timeout")
        await self._put(environment, "annotation-schema.json", json.dumps(annotation_schema()), CONTROL + "/annotation-schema.json")
        statement = (environment.environment_dir.parent / "instruction.md").read_text()
        await self._put(environment, "task_statement.md", statement, REMOTE + "/context/task_statement.md")
        version = await self.checked(environment, shlex.join([binary, "--version"]))
        if version.strip() != "codex-cli " + self.config.codex_version:
            raise RuntimeError("Guest Codex version mismatch")
        probe = "import os; print(open('/proc/%s/statm' % os.getpid()).read().strip())"
        if self.task_id == "002":
            probe += "; from pyscf import lib; print(lib.current_memory())"
        output = await self.checked(environment, shlex.join(["python", "-c", probe]))
        (self.logs_dir / f"runtime-{stage}.log").write_text(output)
        await self.checked(environment, f"PYTHONPATH={REMOTE}/src:{REMOTE}/deps python -c 'from scicontext.graph import graph_schema; print(graph_schema()[\"type\"])'")

    async def setup(self, environment):
        if not isinstance(environment, DockerEnvironment):
            raise RuntimeError("The development runner uses the standard Docker backend")
        self.environment = environment
        self.root = environment.task_env_config.workdir
        if not self.root or not self.root.startswith("/app/task_"):
            raise ValueError("Expected a benchmark workdir")
        self.task_id = self.root.rsplit("_", 1)[-1]
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        info = subprocess.run(["docker", "info", "--format", "{{.MemTotal}} {{.NCPU}} {{.Architecture}}"],
                              check=True, text=True, capture_output=True).stdout.split()
        self.codex_package = await asyncio.to_thread(prepare_codex, self.workspace / ".cache", "x64")
        self.extraction_architecture = None
        self.extract_codex_package = None
        if self.condition == "science":
            self.extraction_architecture = "arm64" if info[2].lower() in {"aarch64", "arm64"} else "x64"
            self.extract_codex_package = (self.codex_package if self.extraction_architecture == "x64" else
                await asyncio.to_thread(prepare_codex, self.workspace / ".cache", self.extraction_architecture))
        pyminor = (await self.checked(environment, "python -c 'import sys; print(str(sys.version_info.major)+str(sys.version_info.minor))'")).strip()
        self.helper_deps = await asyncio.to_thread(prepare_helpers, self.workspace / ".cache", pyminor)
        self._baseline_tree = (await self.checked(environment, "git rev-parse HEAD", cwd=self.root)).strip()
        await self._setup_environment(environment, "repair")
        if self.condition == "science":
            self.extract_environment = DockerEnvironment(
                environment_dir=environment.environment_dir,
                environment_name=environment.environment_name + "-extract",
                session_id=environment.session_id + "-extract",
                trial_paths=TrialPaths(trial_dir=self.logs_dir.parent / "extraction_environment"),
                task_env_config=environment.task_env_config.model_copy(deep=True),
                network_allowlist=self.network_allowlist(), default_user=environment.default_user,
            )
            await self.extract_environment.start(force_build=False)
            await self._setup_environment(self.extract_environment, "extract")
        write_json(self.logs_dir / "setup.json", {
            "codex_version": self.config.codex_version, "harness_architecture": "x64",
            "scientific_image_architecture": "amd64", "environment_image": environment.task_env_config.docker_image,
            "execution": "upstream_pier_codex_docker_boundary", "timeout": "GNU timeout foreground process group",
            "extractor": "task_local_annotations_v2", "claim_cap": 5, "probe_cap": 2,
            "extraction_harness_architecture": self.extraction_architecture,
            "extraction_access_mode": "read-only" if self.condition == "science" else None,
            "extraction_codex_receipt": read_json(self.extract_codex_package.parent / "receipt.json") if self.extract_codex_package else None,
            "interpretation_cap_seconds": min(240, self.config.extraction_seconds * 2 / 3),
            "python_minor": pyminor, "baseline_tree": self._baseline_tree,
            "docker_memory_bytes": int(info[0]), "docker_cpus": int(info[1]),
            "task_requested_memory_mb": environment.task_env_config.memory_mb,
            "host_memory_below_task_request": int(info[0]) < environment.task_env_config.memory_mb * 1024 * 1024,
            "helper_hashes": {p.name: digest_file(p) for p in sorted((self.workspace / "src/scicontext").glob("*.py"))},
            "codex_receipt": read_json(self.codex_package.parent / "receipt.json"),
        })

    async def run_stage(self, name, instruction, seconds):
        if name == "extract":
            self._selected_remote = None
            result = await run_extraction(self, instruction, seconds)
            write_json(self.logs_dir / "extraction-phases.json", result)
            return result
        prompt = instruction + f"\n\nTime allowance remaining: at most {max(1, int(seconds))} seconds."
        return await self._run_codex(name, prompt, seconds)

    async def _helper(self, command, seconds):
        bounded = f"timeout --signal=TERM --kill-after=2s {max(.05, seconds - 3)}s bash -c {shlex.quote(command)}"
        output = await self.checked(self.extract_environment, bounded, timeout_sec=max(1, math.ceil(seconds)))
        return json.loads(output)

    async def prepare(self, seconds):
        return await self._helper(
            f"{HELPER} packet --root {self.root} --context-root {REMOTE}/context --task-id {self.task_id} "
            f"--output {SCRATCH}/packet.json --catalog {SCRATCH}/catalog.md", seconds)

    async def interpret(self, instruction, seconds):
        now = datetime.now(timezone.utc)
        clock = lambda duration: (now + timedelta(seconds=max(0, duration))).strftime("%H:%M:%S UTC")
        template = (self.workspace / "prompts/extract.md").read_text()
        prompt = template.format(root=self.root, scratch=SCRATCH, runtime=CONTROL,
                                 seconds=max(1, int(seconds)), explore_until=clock(seconds * .75),
                                 save_by=clock(seconds * .90), finish_by=clock(seconds - 15),
                                 instruction=instruction)
        result = await self._run_codex("extract", prompt, seconds)
        # Codex returns one compact JSON response; orchestration owns file writes.
        try:
            annotations = read_json(self.logs_dir / "extract-final.txt")
        except (OSError, ValueError) as error:
            result.update(annotations_status="no_valid_annotations", annotations_error=str(error))
            write_json(self.logs_dir / "extract-process.json", result)
            return result
        await self._put(self.extract_environment, "annotations.json", json.dumps(annotations),
                        SCRATCH + "/annotations.json")
        return result

    async def assemble(self, outcomes, seconds):
        target = CONTROL + ("/initial-bundle.json" if outcomes is None else "/bounded-graph.json")
        extra = ""
        if outcomes is not None:
            await self._put(self.extract_environment, "probe-results.json", json.dumps({"results": outcomes}), SCRATCH + "/probe-results.json")
            extra = f" --probe-results {SCRATCH}/probe-results.json"
        result = await self._helper(
            f"{HELPER} assemble --root {self.root} --context-root {REMOTE}/context --packet {SCRATCH}/packet.json "
            f"--annotations {SCRATCH}/annotations.json --output {target}{extra}", seconds)
        if result.get("usable"):
            self._selected_remote = target
        write_json(self.logs_dir / ("assembly-initial.json" if outcomes is None else "assembly-final.json"), result)
        return result

    async def probe(self, specs, seconds):
        # Specs have already passed the assembler's existing path/size checks.
        for spec in specs:
            if "source" in spec:
                destination = SCRATCH + "/" + spec["script"]
                await self.checked(self.extract_environment,
                                   "mkdir -p " + shlex.quote(str(Path(destination).parent)))
                await self._put(self.extract_environment, spec["id"] + ".py",
                                spec["source"], destination)
        await self._put(self.extract_environment, "probe-specs.json", json.dumps({"probes": specs}), SCRATCH + "/probe-specs.json")
        result = await self._helper(
            f"{HELPER} run-probes --root {self.root} --scratch {SCRATCH} --specs {SCRATCH}/probe-specs.json "
            f"--seconds {max(.05, seconds - 5)} --output {SCRATCH}/probe-results.json", seconds)
        return result["results"]

    async def _run_codex(self, name, prompt, seconds):
        started = time.monotonic()
        environment = self.extract_environment if name == "extract" else self.environment
        path = (await self.checked(environment, "printenv PATH")).strip()
        duration = max(0.05, seconds - min(10.0, seconds / 5) - 3)
        stage_agent = OutputCodex(
            stage=name, logs_dir=self.logs_dir / name, model_name=self.config.model,
            version=self.config.codex_version, reasoning_effort=self.config.reasoning_effort,
            config_toml=codex_config(self.config.model, self.config.reasoning_effort),
            extra_env={"CODEX_AUTH_JSON_PATH": str(self.auth_file), "PATH": REMOTE + "/bin:" + path,
                       "PYTHONPATH": self.root + ":" + self.root + "/source", "PYTHONDONTWRITEBYTECODE": "1",
                       "SCICONTEXT_STAGE_SECONDS": str(duration) + "s", "SCICONTEXT_STAGE_NAME": name},
        )
        error = None
        try:
            await stage_agent.run(prompt, environment, AgentContext())
        except NonZeroAgentExitCodeError as caught:
            error = caught
        finally:
            for remote, local in (("codex.txt", f"{name}.jsonl"), (f"{name}-final.txt", f"{name}-final.txt"),
                                  (f"{name}-exit.txt", f"{name}-exit.txt")):
                try:
                    await environment.download_file("/logs/agent/" + remote, self.logs_dir / local)
                except Exception:
                    pass
            try:
                await environment.download_dir("/logs/agent/sessions", self.logs_dir / f"{name}-sessions")
            except Exception:
                pass
        exit_path = self.logs_dir / f"{name}-exit.txt"
        if not exit_path.is_file():
            raise RuntimeError(f"No {name} exit receipt from GNU timeout/Pier") from error
        code = int(exit_path.read_text().strip())
        if code not in {0, 124, 137}:
            raise RuntimeError(f"Codex {name} failed with exit {code}; inspect its preserved log") from error
        result = {"status": "completed" if code == 0 else "timeout", "exit_code": code,
                  "duration_seconds": time.monotonic() - started, "timeout_seconds": duration,
                  "cleanup_complete": None,
                  "cleanup_scope": "GNU timeout foreground process group; no detached-descendant guarantee",
                  "usage": read_usage(self.logs_dir / f"{name}.jsonl")}
        write_json(self.logs_dir / f"{name}-process.json", result)
        return result

    async def collect_graph(self, seconds):
        environment = self.extract_environment
        await environment.download_dir(SCRATCH, self.logs_dir / "extract-scratch")
        await environment.download_dir(self.root + "/outputs", self.logs_dir / "extract-outputs")
        if not self._selected_remote:
            return None
        selected = self.logs_dir / "compiled-graph.json"
        await environment.download_file(self._selected_remote, selected)
        bundle = read_json(selected)
        if bundle["graph"]["task_id"] != self.task_id:
            return None
        return bundle if bundle["assembly"]["usable"] else None

    async def finish_extraction(self):
        if self.extract_environment and not self._finished_extraction:
            await self.extract_environment.stop(delete=False)
            self._finished_extraction = True

    async def cleanup(self):
        await self.finish_extraction()

    async def run(self, instruction, environment, context):
        if self.smoke:
            instruction = "Infrastructure smoke only. Run python -c 'from pyscf import lib; lib.current_memory(); print(7*6)' using the shell tool, then reply READY. Do not edit task source."
        try:
            record = await run_trial(self, self.config, self.task_id, self.condition, instruction, self.logs_dir.parent,
                                     extraction_only=self.extraction_only)
            record.update({"harness_architecture": "x64", "execution": "upstream_pier_codex_docker_boundary",
                           "environment_image": environment.task_env_config.docker_image,
                           "experiment_kind": "extraction_verification" if self.extraction_only else "subscription_smoke" if self.smoke else "development_pilot"})
            if self.smoke:
                record["smoke_success"] = record["status"] == "completed" and verify_smoke(self.logs_dir / "repair.jsonl", self.logs_dir / "repair-final.txt")
                if not record["smoke_success"]:
                    record["status"] = "infrastructure_failure"
                    record["error"] = "Scientific subscription smoke did not complete"
            write_json(self.logs_dir.parent / "run.json", record)
            usages = [s.get("usage", {}) for s in record["stages"]]
            for source, target in (("input_tokens", "n_input_tokens"), ("cached_input_tokens", "n_cache_tokens"), ("output_tokens", "n_output_tokens")):
                values = [u.get(source) for u in usages]
                setattr(context, target, sum(values) if values and all(isinstance(v, int) for v in values) else None)
            context.metadata = {"scicontext": record}
            if self.smoke and not record["smoke_success"]:
                raise RuntimeError(record["error"])
        finally:
            self._temporary.cleanup()
