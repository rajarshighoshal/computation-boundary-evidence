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
from pier.agents.installed.codex import Codex
from pier.environments.docker.docker import DockerEnvironment
from pier.models.agent.context import AgentContext
from pier.models.agent.network import NetworkAllowlist
from pier.models.trial.paths import TrialPaths

from .assets import prepare_codex, prepare_helpers
from .configuration import codex_config
from .controller import TrialConfig, read_usage, run_trial, verify_smoke
from .extraction import extraction_reserve, run_extraction
from .io import digest_file, read_json, write_json

REMOTE = "/opt/scicontext"
CONTROL = REMOTE + "/runtime"
SCRATCH = REMOTE + "/scratch"
HELPER = f"SCICONTEXT_CONTEXT_ROOT={REMOTE}/context PYTHONPATH={REMOTE}/src:{REMOTE}/deps python -m scicontext.tool_cli"


async def bounded_call(operation, seconds, pending):
    """Bound even cancellation-resistant I/O without waiting on its finally forever."""
    if seconds <= 0:
        operation.close()
        raise asyncio.TimeoutError
    task = asyncio.create_task(operation)
    pending.add(task)
    def finished(value):
        pending.discard(value)
        if not value.cancelled():
            value.exception()  # Retrieve late failures from bounded-out operations.
    task.add_done_callback(finished)
    grace = min(1.0, max(0.0, seconds) / 10)
    try:
        done, _ = await asyncio.wait({task}, timeout=max(0.0, seconds - grace))
        if done:
            return task.result()
        task.cancel()
        await asyncio.wait({task}, timeout=grace)
        raise asyncio.TimeoutError
    except asyncio.CancelledError:
        task.cancel()
        raise


class OutputCodex(Codex):
    """Keep upstream launch/auth/cleanup; add final output and file-backed stdin."""

    def __init__(self, *args, stage: str, prompt_path: str | None = None, **kwargs):
        if stage not in {"extract", "extract_draft", "repair"}:
            raise ValueError("Unknown Codex stage")
        self.stage = stage
        self.prompt_path = prompt_path
        super().__init__(*args, **kwargs)
        # Upstream copies sessions out and removes this home after each run.
        # Separate homes also prevent leakage after interrupted cleanup.
        self._REMOTE_CODEX_HOME = Path("/tmp") / ("scicontext-codex-" + stage)
        self._OUTPUT_FILENAME = stage + ".jsonl"

    def build_cli_flags(self):
        return super().build_cli_flags() + f" -o /logs/agent/{self.stage}-final.txt"

    async def exec_as_agent(self, environment, command, **kwargs):
        if self.prompt_path is not None and "codex exec " in command:
            # Pier 0.3.0 redirects stdin to /dev/null. Keep its launch and auth
            # lifecycle, changing only that redirection; `codex exec -` reads it.
            if command.count("</dev/null") != 1:
                raise RuntimeError("Pinned Pier Codex stdin redirection changed")
            command = command.replace("</dev/null", "< " + shlex.quote(self.prompt_path))
        return await super().exec_as_agent(environment, command, **kwargs)


def timeout_launcher(binary: str) -> str:
    """Use native read-only Codex for extraction and GNU timeout for all stages."""
    return f'''#!/bin/sh
case "${{SCICONTEXT_STAGE_NAME:-}}" in extract|extract_draft) readonly_extract=1 ;; *) readonly_extract=0 ;; esac
if [ "$readonly_extract" = 1 ] && [ "${{1:-}}" = exec ] && [ "${{2:-}}" = --dangerously-bypass-approvals-and-sandbox ]; then
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
                 workspace=None, auth_file=None, smoke=False, extraction_only=False,
                 extractor="scientific_objects", extraction_model_seconds=None, frozen_source_dir=None,
                 flexible_budget=False, **kwargs):
        super().__init__(*args, **kwargs)
        if condition not in {"baseline", "science"}:
            raise ValueError("Unknown experiment condition")
        if codex_version != "0.153.4":
            raise ValueError("This experiment pins Codex 0.153.4")
        if extractor != "scientific_objects":
            raise ValueError("Only the scientific-objects extractor is supported")
        self.condition = condition
        self.extraction_model_seconds = float(extraction_model_seconds) if extraction_model_seconds is not None else None
        if self.extraction_model_seconds is not None and not (0 < self.extraction_model_seconds < float("inf")):
            raise ValueError("extraction_model_seconds must be finite and positive")
        self.frozen_source = (Path(frozen_source_dir).resolve() if frozen_source_dir else None)
        self.config = TrialConfig(self.model_name or "gpt-6-astra", reasoning_effort,
                                  codex_version, float(total_seconds), float(extraction_seconds),
                                  flexible_budget)
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
        source_root = self.frozen_source / "scicontext" if self.frozen_source else self.workspace / "src/scicontext"
        await environment.upload_dir(source_root, REMOTE + "/src/scicontext")
        await self._put(environment, "codex-launcher", timeout_launcher(binary), REMOTE + "/bin/codex")
        await self.checked(environment, f"chmod 755 {REMOTE}/bin/codex; command -v timeout")
        if self.condition == "science":
            from .object_context import enrichment_schema
            await self._put(environment, "object-enrichment.schema.json", json.dumps(enrichment_schema()),
                            CONTROL + "/object-enrichment.schema.json")
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
        await self.checked(environment, f"PYTHONPATH={REMOTE}/src:{REMOTE}/deps python -c 'from scicontext.object_context import enrichment_schema; print(enrichment_schema()[\"type\"])'")

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
            "extractor": "scientific_objects_v1",
            "frozen_source": self.frozen_source is not None,
            "claim_cap": None, "probe_cap": 0,
            "extraction_model_call_cap": 1 if self.condition == "science" else 0,
            "extraction_model_seconds": self.extraction_model_seconds,
            "extraction_harness_architecture": self.extraction_architecture,
            "extraction_access_mode": "read-only" if self.condition == "science" else None,
            "extraction_codex_receipt": read_json(self.extract_codex_package.parent / "receipt.json") if self.extract_codex_package else None,
            "interpretation_cap_seconds": (self.config.extraction_seconds - min(60, self.config.extraction_seconds / 6)
                - extraction_reserve(self.config.extraction_seconds - min(60, self.config.extraction_seconds / 6))),
            "revision_policy": "one_scientific_interpretation_call; no probe/refinement loop",
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
            try:
                result = await run_extraction(self, instruction, seconds)
            except asyncio.CancelledError:
                write_json(self.logs_dir / "extraction-phases.json", {
                    "status": "interrupted", "model_calls": getattr(self, "extraction_model_calls", []),
                    "phases": getattr(self, "extraction_phases", [])})
                raise
            write_json(self.logs_dir / "extraction-phases.json", result)
            return result
        prompt = instruction + f"\n\nTime allowance remaining: at most {max(1, int(seconds))} seconds."
        return await self._run_codex(name, prompt, seconds)

    async def _helper(self, command, seconds):
        bounded = f"timeout --signal=TERM --kill-after=2s {max(.05, seconds - 3)}s bash -c {shlex.quote(command)}"
        output = await self.checked(self.extract_environment, bounded, cwd=REMOTE,
                                    timeout_sec=max(1, math.ceil(seconds)))
        return json.loads(output)

    async def prepare(self, seconds):
        # Science arm: observe the public reproducer first (the trace is the
        # evidence layer), then build the static packet, then merge the
        # execution-derived constraint loci into the graph and the enrichment
        # input. A failed trace never blocks the static pipeline.
        if self.condition == "science" and seconds >= 60:
            try:
                await self._helper(
                    f"{HELPER} trace --root {self.root} --script {self.root}/reproduce.py --out {SCRATCH}/trace "
                    f"--seconds {max(10.0, seconds * 0.5)} --observe --shims-dir {REMOTE}/src/scicontext/shims/out",
                    max(15.0, seconds * 0.55))
            except Exception as error:
                # A failed trace (missing reproduce.py, crashed script, etc.)
                # degrades to static-only extraction; the attempt continues.
                write_json(self.logs_dir / "trace-failure.json",
                           {"status": "failed", "error": f"{type(error).__name__}: {error}"})
        result = await self._helper(
            f"{HELPER} packet --root {self.root} --context-root {REMOTE}/context --task-id {self.task_id} "
            f"--output {SCRATCH}/packet.json --catalog {SCRATCH}/catalog.md "
            f"--objects-output {SCRATCH}/scientific-objects.json --enrichment-input {SCRATCH}/scientific-context-input.json",
            max(10.0, seconds * 0.4))
        if self.condition == "science" and seconds >= 60:
            try:
                await self._helper(
                    f"{HELPER} merge-dynamic --root {self.root} --graph {SCRATCH}/scientific-objects.json "
                    f"--packet {SCRATCH}/packet.json --trace-out {SCRATCH}/trace "
                    f"--output {SCRATCH}/scientific-objects.json "
                    f"--enrichment-input {SCRATCH}/scientific-context-input.json",
                    max(10.0, seconds * 0.2))
            except Exception:
                pass
        return result

    async def interpret(self, instruction, seconds):
        started = time.monotonic()
        # Source analysis (Joern) available offline; not a live pipeline step.
                # await self._augment_source_analysis()
        return await self._interpret_call(instruction, max(1, seconds - (time.monotonic() - started)))

    async def _augment_source_analysis(self):
        """Run installed analyzers on the host against the exact public source slice."""
        import sys
        from . import evidence
        from .source_backends import attach_source_analysis
        local = self.logs_dir / "source-analysis"
        local.mkdir(parents=True, exist_ok=True)
        input_file = local / "input.json"
        await self.extract_environment.download_file(SCRATCH + "/scientific-context-input.json", input_file)
        payload = read_json(input_file)
        if not payload.get("context"):
            return
        root = local / "source"
        paths = sorted({item["path"] for key in ("function_bodies", "code_passages", "analysis_sources")
                        for item in payload["context"].get(key, []) if not item["path"].startswith("@context/")})
        for path in paths:
            if evidence._blocked(Path(path)) or Path(path).is_absolute() or ".." in Path(path).parts:
                raise ValueError("Invalid public analysis path")
            destination = root / path
            destination.parent.mkdir(parents=True, exist_ok=True)
            await self.extract_environment.download_file(self.root + "/" + path, destination)
            expected = {item["sha256"] for key in ("function_bodies", "code_passages", "analysis_sources")
                        for item in payload["context"].get(key, []) if item["path"] == path and item.get("sha256")}
            if expected and expected != {digest_file(destination)}:
                raise ValueError("Analysis source differs from the extracted source: " + path)
        output = local / "backend"
        command = [sys.executable, "-m", "scicontext.source_backends", "--root", str(root), "--output", str(output)]
        with (local / "backend.log").open("w") as log:
            process = await asyncio.create_subprocess_exec(*command, stdout=log,
                        stderr=asyncio.subprocess.STDOUT, start_new_session=True)
            try:
                code = await process.wait()
            except asyncio.CancelledError:
                import os, signal
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                    await asyncio.wait_for(process.wait(), 3)
                except asyncio.TimeoutError:
                    os.killpg(process.pid, signal.SIGKILL)
                    await process.wait()
                except ProcessLookupError:
                    pass
                raise
            if code:
                raise RuntimeError(f"Source analysis exited {code}; see {local / 'backend.log'}")
        result = read_json(output / "receipt.json")
        payload = attach_source_analysis(payload, result)
        write_json(input_file, payload)
        await self.extract_environment.upload_file(input_file, SCRATCH + "/scientific-context-input.json")
        self._source_analysis_file = output / "receipt.json"

    async def _interpret_call(self, instruction, seconds):
        now = datetime.now(timezone.utc)
        clock = lambda duration: (now + timedelta(seconds=max(0, duration))).strftime("%H:%M:%S UTC")
        prompt_file = (self.frozen_source / "prompts" / "enrich_objects.md") if self.frozen_source else (self.workspace / "prompts/enrich_objects.md")
        template = prompt_file.read_text()
        # Prompt milestones are earlier soft targets, not extra process cutoffs.
        # Allow for the existing CLI collection/termination work when reporting
        # the actual time available to the model, including small test budgets.
        model_seconds = max(0.0, seconds - min(10.0, seconds / 5)
                            - min(3.0, seconds / 10) - min(1.0, seconds / 10))
        if self.extraction_model_seconds is not None:
            model_seconds = min(model_seconds, self.extraction_model_seconds)
        prompt = template.format(root=self.root, scratch=SCRATCH, runtime=CONTROL,
                                 seconds=max(1, int(model_seconds)), explore_until=clock(model_seconds * .60),
                                 save_by=clock(model_seconds * .80), finish_by=clock(model_seconds * .95),
                                 instruction=instruction)
        prompt += (f"\n\nRead {SCRATCH}/scientific-context-input.json. Task root: {self.root}. "
                   "Return the JSON response; the caller saves it. Access is read-only.")
        result = await self._run_codex("extract_draft", prompt, seconds)
        if result.get("fatal_model_error"):
            return result
        # Codex returns one compact JSON response; orchestration owns file writes.
        try:
            final_path = self.logs_dir / "extract_draft-final.txt"
            if final_path.stat().st_size > 65536:
                raise ValueError("Compact annotations exceed 64 KiB")
            annotations = read_json(final_path)
        except (OSError, ValueError) as error:
            # File persistence belongs to the caller, not the read-only model.
            result.update(annotations_status="no_valid_annotations", annotations_error=str(error))
            write_json(self.logs_dir / "extract_draft-process.json", result)
            return result
        if result.get("status") == "completed":
            self._annotations_remote = SCRATCH + "/extract_draft-annotations.json"
            await self._put(self.extract_environment, "extract_draft-annotations.json", json.dumps(annotations),
                            self._annotations_remote)
        result["annotations_status"] = "received"
        return result

    async def assemble(self, seconds):
        sequence = getattr(self, "_assembly_sequence", 0) + 1
        self._assembly_sequence = sequence
        target = CONTROL + f"/assembly-{sequence}.json"
        annotations = getattr(self, "_annotations_remote", SCRATCH + "/extract_draft-annotations.json")
        result = await self._helper(
            f"{HELPER} assemble-objects --graph {SCRATCH}/scientific-objects.json "
            f"--annotations {annotations} --context-input {SCRATCH}/scientific-context-input.json --output {target}", seconds)
        if result.get("usable"):
            self._selected_remote = target
        result["artifact"] = target
        write_json(self.logs_dir / f"assembly-{sequence}.json", result)
        return result

    async def _run_codex(self, name, prompt, seconds):
        started = time.monotonic()
        deadline = started + seconds
        self._pending_codex_io = getattr(self, "_pending_codex_io", set())
        pending = self._pending_codex_io
        environment = self.extract_environment if name in {"extract", "extract_draft"} else self.environment
        collection_reserve = min(10.0, seconds / 5)
        duration = max(0.05, seconds - collection_reserve - min(3.0, seconds / 10) - min(1.0, seconds / 10))
        error = None
        cancelled = False
        timed_out = False
        upstream_pending = False
        collection_errors = []
        try:
            prompt_file = self.logs_dir / f"{name}-prompt.txt"
            prompt_file.write_text(prompt, encoding="utf-8")
            prompt_path = CONTROL + f"/{name}-prompt.txt"
            await bounded_call(environment.upload_file(prompt_file, prompt_path),
                               max(0, deadline - time.monotonic() - collection_reserve), pending)
            path = (await bounded_call(self.checked(environment, "printenv PATH"),
                                      max(0, deadline - time.monotonic() - collection_reserve), pending)).strip()
            duration = max(0.05, deadline - time.monotonic() - collection_reserve - min(3.0, seconds / 10) - min(1.0, seconds / 10))
            if name.startswith("extract") and self.extraction_model_seconds is not None:
                duration = min(duration, self.extraction_model_seconds)
            stage_agent = OutputCodex(
                stage=name, prompt_path=prompt_path, logs_dir=self.logs_dir / name, model_name=self.config.model,
                version=self.config.codex_version, reasoning_effort=self.config.reasoning_effort,
                config_toml=codex_config(self.config.model, self.config.reasoning_effort),
                extra_env={"CODEX_AUTH_JSON_PATH": str(self.auth_file), "PATH": REMOTE + "/bin:" + path,
                           "PYTHONPATH": self.root + ":" + self.root + "/source", "PYTHONDONTWRITEBYTECODE": "1",
                           "SCICONTEXT_STAGE_SECONDS": str(duration) + "s", "SCICONTEXT_STAGE_NAME": name},
            )
            await bounded_call(stage_agent.run("-", environment, AgentContext()),
                               max(0, deadline - time.monotonic() - collection_reserve), pending)
        except asyncio.TimeoutError:
            timed_out = True
        except asyncio.CancelledError:
            cancelled = True
        except Exception as caught:
            error = caught
        finally:
            upstream_pending = any(not task.done() for task in pending)
            async def collect_file(remote):
                try:
                    await environment.download_file("/logs/agent/" + remote, self.logs_dir / remote)
                except Exception as caught:
                    collection_errors.append(f"{remote}: {type(caught).__name__}")
            async def collect():
                await asyncio.gather(*(collect_file(remote) for remote in
                    (f"{name}.jsonl", f"{name}-final.txt", f"{name}-exit.txt")))
                # Do not race upstream's shared session copy if cleanup is still pending.
                if not upstream_pending:
                    try:
                        await self.checked(environment, f"if [ -d /logs/agent/sessions ]; then mv /logs/agent/sessions /logs/agent/{name}-sessions; fi")
                        await environment.download_dir(f"/logs/agent/{name}-sessions", self.logs_dir / f"{name}-sessions")
                    except Exception as caught:
                        collection_errors.append(f"sessions: {type(caught).__name__}")
            if not cancelled:
                try:
                    await bounded_call(collect(), max(0, deadline - time.monotonic()), pending)
                except asyncio.TimeoutError:
                    collection_errors.append("collection deadline exceeded")
                except asyncio.CancelledError:
                    cancelled = True
        exit_path = self.logs_dir / f"{name}-exit.txt"
        try:
            code = int(exit_path.read_text().strip()) if exit_path.is_file() else None
        except ValueError:
            code = None
        status = "interrupted" if cancelled else "timeout" if timed_out or code in {124, 137} else "completed" if code == 0 and error is None else "failed"
        io_pending = any(not task.done() for task in pending)
        result = {"status": status, "exit_code": code,
                  "duration_seconds": time.monotonic() - started, "timeout_seconds": duration,
                  "cleanup_complete": None,
                  "upstream_cleanup_pending": upstream_pending,
                  "artifact_io_pending": io_pending,
                  "artifact_collection_errors": collection_errors,
                  "fatal_model_error": status == "failed" or upstream_pending or io_pending,
                  "cleanup_scope": "GNU timeout foreground process group; no detached-descendant guarantee",
                  "usage": read_usage(self.logs_dir / f"{name}.jsonl")}
        # This survives an outer phase/stage timeout that prevents returning the receipt.
        self._fatal_model_error = getattr(self, "_fatal_model_error", False) or result["fatal_model_error"]
        if error is not None or code is None:
            result["error"] = str(error) if error else "Missing GNU timeout/Pier exit receipt"
        write_json(self.logs_dir / f"{name}-process.json", result)
        if cancelled:
            raise asyncio.CancelledError
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
        if not bundle["assembly"]["usable"]:
            return None
        if bundle["graph"].get("schema_version") == "scientific-objects-1.0":
            from .object_context import render_guide
            from .io import digest_json
            files = {
                "scientific-graph.json": json.dumps(bundle["graph"], ensure_ascii=False) + "\n",
                "scientific-guide.md": render_guide(bundle["graph"]),
                "scientific-sources.json": json.dumps(bundle.get("context"), ensure_ascii=False) + "\n",
            }
            if getattr(self, "_source_analysis_file", None):
                files["source-analysis.json"] = self._source_analysis_file.read_text()
            for name, text in files.items():
                local = self.logs_dir / name
                local.write_text(text, encoding="utf-8")
                await self.environment.upload_file(local, REMOTE + "/context/" + name)
            bundle["handoff_files"] = {name: REMOTE + "/context/" + name for name in files}
            bundle["guide_markdown"] = files["scientific-guide.md"]
            bundle["handoff"] = (
                "The complete object graph is /opt/scicontext/context/scientific-graph.json and the public "
                "source passages are /opt/scicontext/context/scientific-sources.json; look objects up by ID "
                "when you need their full relationships.")
            write_json(self.logs_dir / "handoff-files.json", {
                "paths": bundle["handoff_files"], "graph_sha256": digest_json(bundle["graph"]),
                "file_bytes": {name: len(text.encode("utf-8")) for name, text in files.items()},
            })
        return bundle

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
