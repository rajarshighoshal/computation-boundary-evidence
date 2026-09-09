"""Native Codex adapter with one total deadline and separated extraction workspace."""
from __future__ import annotations

import asyncio
import json
import math
import os
import platform
import shlex
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from pier.agents.base import BaseAgent
from pier.environments.base import BaseEnvironment
from pier.environments.docker.docker import DockerEnvironment
from pier.models.agent.context import AgentContext
from pier.models.agent.network import NetworkAllowlist
from pier.models.trial.paths import TrialPaths

from .assets import prepare_codex, prepare_helpers
from .configuration import codex_config
from .controller import TrialConfig, read_usage, run_trial, verify_smoke
from .graph import graph_schema
from .io import digest_file, digest_json, read_json, write_json

REMOTE = "/opt/scicontext"
CONTROL = REMOTE + "/control"
SCRATCH = REMOTE + "/scratch"
HELPER = f"SCICONTEXT_CONTEXT_ROOT={REMOTE}/context PYTHONPATH={REMOTE}/src:{REMOTE}/deps python -m scicontext.tool_cli"


def _quoted(command: list[str]) -> str:
    return shlex.join(command)


def _runtime_env(home: str) -> dict[str, str]:
    return {"CODEX_HOME": home, "HOME": REMOTE + "/client-home",
            "PYTHONDONTWRITEBYTECODE": "1", "TMPDIR": SCRATCH + "/tmp",
            "TMP": SCRATCH + "/tmp", "TEMP": SCRATCH + "/tmp",
            "XDG_CACHE_HOME": SCRATCH + "/cache", "MPLCONFIGDIR": SCRATCH + "/cache/matplotlib",
            "NUMBA_CACHE_DIR": SCRATCH + "/cache/numba"}


class ScientificCodex(BaseAgent):
    SUPPORTS_ATIF = False

    def __init__(self, *args, condition="baseline", total_seconds=1800,
                 extraction_seconds=360, reasoning_effort="high", codex_version="0.153.4",
                 workspace=None, auth_file=None, smoke=False, **kwargs):
        super().__init__(*args, **kwargs)
        if condition not in {"baseline", "science"}:
            raise ValueError("Unknown experiment condition")
        if codex_version != "0.153.4":
            raise ValueError("This adapter is verified for Codex 0.153.4 only")
        self.condition = condition
        self.config = TrialConfig(self.model_name or "gpt-6-astra", reasoning_effort,
                                  codex_version, float(total_seconds), float(extraction_seconds))
        self.workspace = Path(workspace or Path.cwd()).resolve()
        self.auth_file = Path(auth_file or os.environ.get("SCICONTEXT_AUTH_FILE", "")).expanduser()
        if not self.auth_file.is_file():
            raise ValueError("A private Codex subscription auth-file path is required; no API fallback")
        self.smoke = str(smoke).lower() in {"true", "1"}
        self.extract_environment = None
        self.environment = None
        self._finished_extraction = False
        self._active_stage = None
        self._private = tempfile.TemporaryDirectory(prefix="scicontext-client-")
        os.chmod(self._private.name, 0o700)
        self._temporary = Path(self._private.name)
        self._auth_cache = self._temporary / "auth.json"
        shutil.copyfile(self.auth_file, self._auth_cache)
        self._auth_cache.chmod(0o600)

    @staticmethod
    def name():
        return "scicontext-codex"

    def version(self):
        return "0.1.0"

    def network_allowlist(self):
        # Client service traffic only. Native tool commands have network=false.
        return NetworkAllowlist(domains=["chatgpt.com", "auth.openai.com", "auth0.openai.com", "api.openai.com"])

    async def checked(self, environment, command, **kwargs):
        result = await environment.exec(command, **kwargs)
        if result.return_code:
            raise RuntimeError(f"Command failed ({result.return_code}): {command[:180]}\n{(result.stderr or result.stdout or '')[-1500:]}")
        return result.stdout or ""

    async def _put(self, environment, name: str, text: str, destination: str):
        path = self._temporary / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        await environment.upload_file(path, destination)

    async def _setup_environment(self, environment, profile):
        root = self.root
        owner = (await self.checked(environment, "python -c 'import os; print(str(os.getuid())+\":\"+str(os.getgid()))'")).strip()
        self._guest_owners[profile] = owner
        await self.checked(environment, f"mkdir -p {CONTROL}/{profile}/home {SCRATCH}/checkpoints {SCRATCH}/tmp {SCRATCH}/cache/matplotlib {SCRATCH}/cache/numba {REMOTE}/client-home {REMOTE}/context {REMOTE}/src {root}/outputs")
        await environment.upload_dir(self.codex_package, REMOTE + "/codex")
        await environment.upload_dir(self.helper_deps, REMOTE + "/deps")
        await environment.upload_dir(self.workspace / "src/scicontext", REMOTE + "/src/scicontext")
        config_text = codex_config(root, SCRATCH, CONTROL, profile, self.config.model, self.config.reasoning_effort)
        home = f"{CONTROL}/{profile}/home"
        await self._put(environment, profile + "-config.toml", config_text, home + "/config.toml")
        await self._put(environment, "schema.json", json.dumps(graph_schema()), CONTROL + "/schema.json")
        task_statement = (environment.environment_dir.parent / "instruction.md").read_text()
        await self._put(environment, "task_statement.md", task_statement, REMOTE + "/context/task_statement.md")
        await self._put(environment, "dummy-secret", "dummy", CONTROL + "/dummy-secret")
        await self._put(environment, "permission-marker", "probe", root + "/.scicontext-permission-probe")
        # Compose cp retains the host uid. The native sandbox's user namespace
        # cannot write a host-owned fixture, even when the task root is writable.
        await self.checked(environment, _quoted(["chown", owner, root + "/.scicontext-permission-probe"]))
        env = _runtime_env(home)
        version = await self.checked(environment, _quoted([self.binary, "--version"]), env=env)
        if version.strip() != "codex-cli " + self.config.codex_version:
            raise RuntimeError("Guest Codex version mismatch")
        probe = await environment.exec(_quoted([self.binary, "sandbox", "--permission-profile", profile,
                                      "--cd", root, "--", "python", REMOTE + "/src/scicontext/permission_probe.py",
                                      profile, root, SCRATCH, CONTROL]), env=env, timeout_sec=30)
        (self.logs_dir / f"sandbox-{profile}.log").write_text((probe.stdout or "") + (probe.stderr or ""))
        await self.checked(environment, _quoted(["rm", "-f", root + "/.scicontext-permission-probe"]))
        if probe.return_code:
            raise RuntimeError(f"Native {profile} sandbox probe failed; see sandbox-{profile}.log. Credentials were not uploaded.")
        report = json.loads((probe.stdout or "").strip().splitlines()[-1])
        if not all(report["checks"].values()):
            raise RuntimeError("Sandbox checks did not establish the required boundaries")
        await self.checked(environment, f"PYTHONPATH={REMOTE}/src:{REMOTE}/deps python -c 'from scicontext.graph import graph_schema; print(graph_schema()[\"type\"])'")
        # Only after no-model enforcement has passed do we introduce real auth.
        await environment.upload_file(self._auth_cache, home + "/auth.json")
        await self.checked(environment, _quoted(["chown", owner, home + "/auth.json"]))
        await self.checked(environment, _quoted(["chmod", "600", home + "/auth.json"]))
        self._homes[profile] = home

    async def setup(self, environment: BaseEnvironment):
        if not isinstance(environment, DockerEnvironment):
            raise RuntimeError("Initial adapter supports the documented Docker backend")
        self.environment = environment
        self.root = environment.task_env_config.workdir
        if not self.root or not self.root.startswith("/app/task_"):
            raise ValueError("Expected an explicit benchmark workdir")
        self.task_id = self.root.rsplit("_", 1)[-1]
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self._homes = {}
        self._guest_owners = {}
        daemon_info = subprocess.run(["docker", "info", "--format", "{{.Architecture}} {{.MemTotal}} {{.NCPU}}"], check=True, text=True, capture_output=True).stdout.split()
        daemon_arch = daemon_info[0]
        self.harness_arch = "arm64" if daemon_arch in {"arm64", "aarch64"} else "x64"
        self.codex_package = await asyncio.to_thread(prepare_codex, self.workspace / ".cache", self.harness_arch)
        triple = "aarch64-unknown-linux-musl" if self.harness_arch == "arm64" else "x86_64-unknown-linux-musl"
        self.binary = REMOTE + f"/codex/vendor/{triple}/bin/codex"
        pyminor = (await self.checked(environment, "python -c 'import sys; print(str(sys.version_info.major)+str(sys.version_info.minor))'")).strip()
        self.helper_deps = await asyncio.to_thread(prepare_helpers, self.workspace / ".cache", pyminor)
        await self._setup_environment(environment, "repair")
        if self.condition == "science":
            extract_paths = TrialPaths(trial_dir=self.logs_dir.parent / "extraction_environment")
            self.extract_environment = DockerEnvironment(
                environment_dir=environment.environment_dir,
                environment_name=environment.environment_name + "-extract",
                session_id=environment.session_id + "-extract",
                trial_paths=extract_paths,
                task_env_config=environment.task_env_config.model_copy(deep=True),
                network_allowlist=self.network_allowlist(), default_user=environment.default_user,
            )
            await self.extract_environment.start(force_build=False)
            await self._setup_environment(self.extract_environment, "extract")
        self._baseline_tree = (await self.checked(environment, "git rev-parse HEAD", cwd=self.root)).strip()
        write_json(self.logs_dir / "setup.json", {
            "codex_version": self.config.codex_version, "harness_architecture": self.harness_arch,
            "scientific_image_architecture": "amd64", "environment_image": environment.task_env_config.docker_image,
            "python_minor": pyminor, "baseline_tree": self._baseline_tree,
            "docker_memory_bytes": int(daemon_info[1]), "docker_cpus": int(daemon_info[2]),
            "task_requested_memory_mb": environment.task_env_config.memory_mb,
            "host_memory_below_task_request": int(daemon_info[1]) < environment.task_env_config.memory_mb * 1024 * 1024,
            "helper_hashes": {p.name: digest_file(p) for p in sorted((self.workspace / "src/scicontext").glob("*.py"))},
            "codex_receipt": read_json(self.codex_package.parent / "receipt.json"),
        })

    async def run_stage(self, name: str, instruction: str, seconds: float):
        stage_deadline = time.monotonic() + seconds
        environment = self.extract_environment if name == "extract" else self.environment
        profile = "extract" if name == "extract" else "repair"
        home = self._homes[profile]
        # Refresh transfer is private, serialized, and never enters the task tree.
        await environment.upload_file(self._auth_cache, home + "/auth.json")
        await self.checked(environment, _quoted(["chown", self._guest_owners[profile], home + "/auth.json"]))
        if name == "extract":
            template = (self.workspace / "prompts/extract.md").read_text()
            prompt = template.format(helper=HELPER, root=self.root, scratch=SCRATCH,
                                     seconds=max(1, int(seconds)), instruction=instruction)
        else:
            prompt = instruction + f"\n\nTime allowance remaining: at most {max(1, int(seconds))} seconds."
        prompt_path = f"{CONTROL}/{profile}/prompt.txt"
        await self._put(environment, profile + "-prompt.txt", prompt, prompt_path)
        # Prompt enters via stdin in the supervisor; it is not accessible to task commands.
        command = [self.binary, "exec", "--model", self.config.model, "--json", "--color", "never",
                   "--skip-git-repo-check", "-C", self.root, "-o", f"/logs/agent/{name}-final.txt"]
        if name == "extract":
            command += ["--output-schema", CONTROL + "/schema.json"]
        command.append("-")
        client_env = {**_runtime_env(home),
                        "PYTHONPATH": self.root + ":" + self.root + "/source",
                        "SCICONTEXT_PROMPT_FILE": prompt_path}
        # DockerEnvironment.exec does not inject Pier's service egress proxy.
        # Native command networking remains separately disabled by the profile.
        spec = {"command": command, "cwd": self.root,
                "env": environment.agent_process_env(client_env),
                "stdin_path": prompt_path,
                "timeout_seconds": max(0.05, stage_deadline - time.monotonic() - min(10.0, seconds / 5)),
                "stdout_path": f"/logs/agent/{name}.jsonl", "stderr_path": f"/logs/agent/{name}.stderr",
                "result_path": f"/logs/agent/{name}-process.json", "pid_path": f"{CONTROL}/{profile}/pid.json",
                "strict_descendants": True}
        await self._put(environment, profile + "-spec.json", json.dumps(spec), f"{CONTROL}/{profile}/spec.json")
        self._active_stage = (environment, profile)
        try:
            result = await environment.exec(f"PYTHONPATH={REMOTE}/src python -m scicontext.supervise {CONTROL}/{profile}/spec.json", timeout_sec=max(1, math.ceil(seconds)), cwd=self.root)
            if result.return_code not in {0, 124, 130, 143}:
                self.logger.warning("Stage supervisor return code: %s", result.return_code)
        finally:
            await self._terminate_active()
            destination = self.logs_dir
            for filename in (f"{name}.jsonl", f"{name}.stderr", f"{name}-final.txt", f"{name}-process.json"):
                try:
                    await environment.download_file("/logs/agent/" + filename, destination / filename)
                except Exception:
                    pass
            try:
                await environment.download_dir(home + "/sessions", self.logs_dir / f"{name}-sessions")
            except Exception:
                pass
            try:
                await environment.download_file(home + "/auth.json", self._auth_cache)
                self._auth_cache.chmod(0o600)
            except Exception:
                pass
        process_path = self.logs_dir / f"{name}-process.json"
        if not process_path.is_file():
            raise RuntimeError(f"{name} supervisor did not preserve a completion/cleanup receipt")
        process = read_json(process_path)
        if process.get("status") == "timed_out":
            process["status"] = "timeout"
        process["usage"] = read_usage(self.logs_dir / f"{name}.jsonl")
        if process.get("exit_code") not in {0, None} and process.get("status") not in {"timeout", "interrupted"}:
            raise RuntimeError(f"Codex {name} exited unsuccessfully; inspect its stderr receipt")
        return process

    async def _terminate_active(self):
        if self._active_stage is None:
            return
        environment, profile = self._active_stage
        try:
            await environment.exec(f"PYTHONPATH={REMOTE}/src python -m scicontext.supervise --terminate {CONTROL}/{profile}/pid.json", timeout_sec=5)
        finally:
            self._active_stage = None

    async def collect_graph(self, seconds: float):
        environment = self.extract_environment
        # Also validate the structured final response if no checkpoint call was made.
        command = (f"if test -s /logs/agent/extract-final.txt; then {HELPER} checkpoint --root {shlex.quote(self.root)} "
                   f"--graph /logs/agent/extract-final.txt --output {SCRATCH}/checkpoints; fi")
        await environment.exec(command, timeout_sec=max(1, min(10, math.ceil(seconds))))
        # Re-run validation and source grounding for every candidate; never trust an LLM-written receipt.
        collector = (
            "import json,pathlib; from scicontext.graph import validate_graph,render_graph; "
            "from scicontext.tool_cli import analyze_grounded; from scicontext.io import digest_json; "
            f"root=pathlib.Path({self.root!r}); directory=pathlib.Path({(SCRATCH + '/checkpoints')!r}); "
            "candidates=sorted(directory.glob('*.json'),key=lambda p:(p.stat().st_mtime_ns,p.name),reverse=True); selected=None\n"
            "for p in candidates[:64]:\n"
            " try:\n"
            f"  raw=json.loads(p.read_text()); g=raw['graph']; v=validate_graph(g,root,context_root=pathlib.Path({(REMOTE + '/context')!r}))\n"
            f"  if not v['valid'] or g['task_id'] != {self.task_id!r}: continue\n"
            "  a=analyze_grounded(g,root); selected={'graph':g,'validation':v,'analysis':a,'graph_sha256':digest_json(g),'handoff':render_graph(g,a)}; break\n"
            " except (ValueError,KeyError,TypeError,OSError): continue\n"
            f"pathlib.Path({(CONTROL + '/selected-graph.json')!r}).write_text(json.dumps(selected))\n"
        )
        await self._put(environment, "collect.py", collector, CONTROL + "/collect.py")
        await self.checked(environment, f"PYTHONPATH={REMOTE}/src:{REMOTE}/deps python {CONTROL}/collect.py", timeout_sec=max(1, math.ceil(seconds)))
        await environment.download_file(CONTROL + "/selected-graph.json", self._temporary / "selected-graph.json")
        await environment.download_dir(SCRATCH, self.logs_dir / "extract-scratch")
        graph = json.loads((self._temporary / "selected-graph.json").read_text())
        return graph

    async def finish_extraction(self):
        if self.extract_environment and not self._finished_extraction:
            await self._terminate_active()
            await self.extract_environment.stop(delete=False)
            self._finished_extraction = True

    async def cleanup(self):
        await self._terminate_active()
        await self.finish_extraction()
        if self.environment:
            # Remove only our exact private runtime subtree, after all owned children stop.
            await self.environment.exec(_quoted(["rm", "-rf", CONTROL]), timeout_sec=5)

    async def run(self, instruction: str, environment: BaseEnvironment, context: AgentContext):
        if self.smoke:
            instruction = "This is an infrastructure smoke. Run python -c 'print(7*6)' using the shell tool, then reply READY. Do not edit task source."
        try:
            record = await run_trial(self, self.config, self.task_id, self.condition, instruction, self.logs_dir.parent)
            record["harness_architecture"] = self.harness_arch
            record["environment_image"] = environment.task_env_config.docker_image
            record["experiment_kind"] = "subscription_smoke" if self.smoke else "development_pilot"
            if self.smoke:
                record["smoke_success"] = record["status"] == "completed" and verify_smoke(
                    self.logs_dir / "repair.jsonl", self.logs_dir / "repair-final.txt")
                if not record["smoke_success"]:
                    record["status"] = "infrastructure_failure"
                    record["error"] = "Subscription smoke did not complete the requested shell command and final response"
            write_json(self.logs_dir.parent / "run.json", record)
            usages = [s.get("usage", {}) for s in record["stages"]]
            for source, target in (("input_tokens", "n_input_tokens"), ("cached_input_tokens", "n_cache_tokens"), ("output_tokens", "n_output_tokens")):
                values = [u.get(source) for u in usages]
                setattr(context, target, sum(values) if values and all(isinstance(v, int) for v in values) else None)
            context.metadata = {"scicontext": record}
            # Preserve refreshed runner credentials privately for the next serialized trial.
            shutil.copyfile(self._auth_cache, self.auth_file)
            self.auth_file.chmod(0o600)
            if self.smoke and not record["smoke_success"]:
                raise RuntimeError(record["error"])
        finally:
            self._private.cleanup()
