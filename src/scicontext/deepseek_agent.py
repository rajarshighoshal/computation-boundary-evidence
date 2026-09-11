"""DeepSeek-backed experiment agent: same harness interface, host-side API calls.

Subclasses ScientificCodex so packet preparation, assembly, artifact
collection, cleanup and run_trial wiring stay identical. Only the model-call
paths change:

- Extraction: one direct DeepSeek chat call with the focused payload embedded
  inline (no tools; the payload is already the bounded selection). The
  annotations are schema-checked by the standard assembly step.
- Repair: a bounded DeepSeek function-calling loop with a single ``shell``
  tool executed in the task container. Same prompt composition, same budget
  and same receipts shape as the Codex route.

API calls run on the host; only shell commands execute inside containers, so
no provider credential ever enters a task container.
"""
from __future__ import annotations

import asyncio
import json
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .assets import prepare_helpers
from .extraction import extraction_reserve, run_extraction
from .io import digest_file, read_json, write_json
from .pier_agent import CONTROL, HELPER, REMOTE, SCRATCH, ScientificCodex, bounded_call

API = "https://api.deepseek.com/chat/completions"
MAX_OUTPUT_TOKENS = 65536
MAX_TOOL_OUTPUT_CHARS = 60_000
MAX_TOOL_SECONDS = 120
MAX_LOOP_ITERATIONS = 60
MAX_CONVERSATION_TOOL_CHARS = 300_000
MAX_ANNOTATION_CHARS = 65_536


async def _api_completion(api_key: str, model: str, messages: list, *,
                          tools=None, response_format=None, max_tokens=MAX_OUTPUT_TOKENS,
                          timeout_sec: float, temperature: float = 0.0) -> dict:
    body = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature}
    if tools:
        body["tools"] = tools
    if response_format:
        body["response_format"] = response_format

    def send():
        request = urllib.request.Request(API, data=json.dumps(body).encode(), method="POST", headers={
            "Authorization": f"Bearer {api_key}", "Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=min(300, timeout_sec)) as response:
            return json.load(response)

    return await asyncio.to_thread(send)


def _compact_tools(messages: list) -> None:
    """Replace oldest tool outputs once cumulative tool text exceeds the budget."""
    total = sum(len(m.get("content", "")) for m in messages if m.get("role") == "tool")
    for message in messages:
        if total <= MAX_CONVERSATION_TOOL_CHARS:
            return
        if message.get("role") == "tool":
            content = message["content"]
            dropped = len(content)
            message["content"] = "[earlier output omitted to stay within context budget]"
            total -= dropped


class DeepSeekAgent(ScientificCodex):
    def __init__(self, *args, deepseek_key_file=None, **kwargs):
        if not deepseek_key_file:
            raise ValueError("deepseek_key_file is required for the DeepSeek route")
        # The parent requires an existing auth-file path; the DeepSeek key file
        # satisfies that check without ever being read by the Codex path.
        super().__init__(*args, auth_file=deepseek_key_file, **kwargs)
        self.deepseek_key = read_json(Path(deepseek_key_file).expanduser())["api_key"]
        self.model = self.config.model
        self.shell_tools = [{"type": "function", "function": {
            "name": "shell", "description": (
                "Execute a command in the task repository container and return combined stdout/stderr "
                "(capped). Use it to inspect files, run tests and make edits with standard tools."),
            "parameters": {"type": "object",
                           "properties": {"command": {"type": "string",
                                                      "description": "Single bash command line to run."}},
                           "required": ["command"]}}}]

    async def _setup_environment(self, environment, stage):
        await self.checked(environment, f"mkdir -p {CONTROL} {REMOTE}/src {REMOTE}/context {SCRATCH}/checkpoints {self.root}/outputs")
        await environment.upload_dir(self.helper_deps, REMOTE + "/deps")
        source_root = self.frozen_source / "scicontext" if self.frozen_source else self.workspace / "src/scicontext"
        await environment.upload_dir(source_root, REMOTE + "/src/scicontext")
        if self.condition == "science":
            from .object_context import enrichment_schema
            await self._put(environment, "object-enrichment.schema.json", json.dumps(enrichment_schema()),
                            CONTROL + "/object-enrichment.schema.json")
        statement = (environment.environment_dir.parent / "instruction.md").read_text()
        await self._put(environment, "task_statement.md", statement, REMOTE + "/context/task_statement.md")
        probe = "import os; print(open('/proc/%s/statm' % os.getpid()).read().strip())"
        if self.task_id == "002":
            probe += "; from pyscf import lib; print(lib.current_memory())"
        output = await self.checked(environment, "python -c " + json.dumps(probe))
        (self.logs_dir / f"runtime-{stage}.log").write_text(output)
        await self.checked(environment, f"PYTHONPATH={REMOTE}/src:{REMOTE}/deps python -c 'from scicontext.object_context import enrichment_schema; print(enrichment_schema()[\"type\"])'")

    async def setup(self, environment):
        from pier.environments.docker.docker import DockerEnvironment
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
        pyminor = (await self.checked(environment, "python -c 'import sys; print(str(sys.version_info.major)+str(sys.version_info.minor))'")).strip()
        self.helper_deps = await asyncio.to_thread(prepare_helpers, self.workspace / ".cache", pyminor)
        self._baseline_tree = (await self.checked(environment, "git rev-parse HEAD", cwd=self.root)).strip()
        self.codex_package = None
        self.extract_codex_package = None
        self.extraction_architecture = None
        await self._setup_environment(environment, "repair")
        if self.condition == "science":
            from pier.models.trial.paths import TrialPaths
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
            "agent": "deepseek", "model": self.model,
            "harness_architecture": "x64", "scientific_image_architecture": "amd64",
            "environment_image": environment.task_env_config.docker_image,
            "execution": "host_side_deepseek_api_with_in_container_shell_tools",
            "extractor": "scientific_objects_v1", "frozen_source": self.frozen_source is not None,
            "claim_cap": None, "probe_cap": 0,
            "extraction_model_call_cap": 1 if self.condition == "science" else 0,
            "extraction_model_seconds": self.extraction_model_seconds,
            "extraction_harness_architecture": "host_api",
            "extraction_access_mode": "read-only" if self.condition == "science" else None,
            "interpretation_cap_seconds": (self.config.extraction_seconds - min(60, self.config.extraction_seconds / 6)
                - extraction_reserve(self.config.extraction_seconds - min(60, self.config.extraction_seconds / 6))),
            "revision_policy": "one_scientific_interpretation_call; no probe/refinement loop",
            "python_minor": pyminor, "baseline_tree": self._baseline_tree,
            "docker_memory_bytes": int(info[0]), "docker_cpus": int(info[1]),
            "task_requested_memory_mb": environment.task_env_config.memory_mb,
            "host_memory_below_task_request": int(info[0]) < environment.task_env_config.memory_mb * 1024 * 1024,
            "helper_hashes": {p.name: digest_file(p) for p in sorted((self.workspace / "src/scicontext").glob("*.py"))},
            "max_output_tokens": MAX_OUTPUT_TOKENS, "temperature": 0.0,
        })
        if self.smoke:
            check = await self.checked(environment, "python -c 'from pyscf import lib; print(7*6)'")
            if check.strip() != "42":
                raise RuntimeError("Smoke dependency check failed")

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
        return await self._run_deepseek_repair(prompt, seconds)

    async def _interpret_call(self, instruction, seconds):
        template = ((self.frozen_source / "prompts" / "enrich_objects.md") if self.frozen_source
                    else (self.workspace / "prompts/enrich_objects.md")).read_text()
        model_seconds = max(0.0, seconds - min(10.0, seconds / 5) - min(3.0, seconds / 10) - min(1.0, seconds / 10))
        if self.extraction_model_seconds is not None:
            model_seconds = min(model_seconds, self.extraction_model_seconds)
        now = datetime.now(timezone.utc)
        clock = lambda duration: (now + timedelta(seconds=max(0, duration))).strftime("%H:%M:%S UTC")
        prompt = template.format(root=self.root, scratch=SCRATCH, runtime=CONTROL,
                                 seconds=max(1, int(model_seconds)), explore_until=clock(model_seconds * .60),
                                 save_by=clock(model_seconds * .80), finish_by=clock(model_seconds * .95),
                                 instruction=instruction)
        local_scratch = self.logs_dir / "extract-scratch"
        local_scratch.mkdir(parents=True, exist_ok=True)
        payload_path = local_scratch / "scientific-context-input.json"
        try:
            await bounded_call(self.extract_environment.download_file(
                SCRATCH + "/scientific-context-input.json", payload_path), 30, set())
        except Exception as error:
            result = {"status": "failed", "fatal_model_error": True,
                      "error": f"payload download failed: {error}", "usage": {}}
            write_json(self.logs_dir / "extract_draft-process.json", result)
            return result
        payload = read_json(payload_path)
        prompt += ("\n\nThis call has no shell tools and no file access. The scientific context input is "
                   "embedded inline below; annotate at most the 40 most task-relevant objects and return "
                   "compact, complete annotations JSON directly as your response.\n\nSCIENTIFIC CONTEXT INPUT\n"
                   + json.dumps(payload, ensure_ascii=False))
        started = time.monotonic()
        try:
            completion = await _api_completion(self.deepseek_key, self.model,
                                               [{"role": "user", "content": prompt}],
                                               response_format={"type": "json_object"},
                                               timeout_sec=model_seconds)
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            result = {"status": "failed", "fatal_model_error": True,
                      "error": f"DeepSeek transport failure: {error}", "usage": {}}
            write_json(self.logs_dir / "extract_draft-process.json", result)
            return result
        usage = completion.get("usage", {})
        content = completion["choices"][0]["message"].get("content") or ""
        result = {"status": "completed", "usage": {"input_tokens": usage.get("prompt_tokens"),
                                                   "cached_input_tokens": None,
                                                   "output_tokens": usage.get("completion_tokens"),
                                                   "reasoning_output_tokens": None},
                  "duration_seconds": time.monotonic() - started,
                  "finish_reason": completion["choices"][0].get("finish_reason"),
                  "prompt_chars": len(prompt)}
        (self.logs_dir / "extract_draft-final.txt").write_text(content)
        if len(content.encode()) > MAX_ANNOTATION_CHARS:
            result.update(annotations_status="no_valid_annotations",
                          annotations_error="Compact annotations exceed 64 KiB")
            write_json(self.logs_dir / "extract_draft-process.json", result)
            return result
        try:
            annotations = json.loads(content)
        except ValueError as error:
            result.update(annotations_status="no_valid_annotations", annotations_error=str(error))
            write_json(self.logs_dir / "extract_draft-process.json", result)
            return result
        self._annotations_remote = SCRATCH + "/extract_draft-annotations.json"
        await self._put(self.extract_environment, "extract_draft-annotations.json", json.dumps(annotations),
                        self._annotations_remote)
        result["annotations_status"] = "received"
        write_json(self.logs_dir / "extract_draft-process.json", result)
        return result

    async def _run_deepseek_repair(self, prompt, seconds):
        deadline = time.monotonic() + seconds
        messages = [{"role": "user", "content": prompt}]
        usage = {"input_tokens": 0, "output_tokens": 0}
        events = []
        result = {"status": "timeout", "usage": usage, "cleanup_complete": None}
        try:
            for _ in range(MAX_LOOP_ITERATIONS):
                remaining = deadline - time.monotonic()
                if remaining <= 1:
                    break
                completion = await _api_completion(self.deepseek_key, self.model, messages,
                                                   tools=self.shell_tools, timeout_sec=remaining)
                usage["input_tokens"] += completion.get("usage", {}).get("prompt_tokens", 0)
                usage["output_tokens"] += completion.get("usage", {}).get("completion_tokens", 0)
                message = completion["choices"][0]["message"]
                messages.append(message)
                events.append({"type": "turn.started"})
                if message.get("tool_calls"):
                    for call in message["tool_calls"]:
                        tool_remaining = max(0.0, deadline - time.monotonic())
                        if tool_remaining <= 0:
                            break
                        output = "Tool budget exhausted."
                        command = ""
                        exit_code = 1
                        arguments = {}
                        try:
                            arguments = json.loads(call["function"].get("arguments") or "{}")
                            command = arguments.get("command", "")
                        except ValueError as error:
                            output = f"Malformed tool arguments refused: {error}"
                        if arguments and command:
                            try:
                                output = await bounded_call(self.checked(
                                    self.environment, command, cwd=self.root,
                                    timeout_sec=min(MAX_TOOL_SECONDS, max(0.05, tool_remaining))),
                                    min(MAX_TOOL_SECONDS, max(1.0, tool_remaining)), set())
                                exit_code = 0
                            except Exception as error:
                                output = f"Command failed: {type(error).__name__}: {error}"
                                exit_code = 1
                        elif arguments and not command:
                            output = "Empty shell command refused."
                        events.append({"type": "item.completed", "item": {
                            "id": call["id"], "type": "command_execution", "command": command,
                            "exit_code": exit_code,
                            "aggregated_output": output[-MAX_TOOL_OUTPUT_CHARS:]}})
                        messages.append({"role": "tool", "tool_call_id": call["id"],
                                         "content": output[-MAX_TOOL_OUTPUT_CHARS:]})
                    _compact_tools(messages)
                    continue
                content = message.get("content") or ""
                (self.logs_dir / "repair-final.txt").write_text(content)
                events.append({"type": "turn.completed", "usage": {
                    "input_tokens": usage["input_tokens"], "cached_input_tokens": 0,
                    "output_tokens": usage["output_tokens"], "reasoning_output_tokens": None}})
                result.update(status="completed", finish_reason=completion["choices"][0].get("finish_reason"))
                break
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            result.update(status="failed", fatal_model_error=True, error=f"DeepSeek transport failure: {error}")
            self._fatal_model_error = True
        finally:
            if "usage" in result and events and events[-1]["type"] != "turn.completed":
                events.append({"type": "turn.completed", "usage": {
                    "input_tokens": usage["input_tokens"], "cached_input_tokens": 0,
                    "output_tokens": usage["output_tokens"], "reasoning_output_tokens": None}})
            write_json(self.logs_dir / "repair-process.json", result)
            (self.logs_dir / "repair.jsonl").write_text("\n".join(json.dumps(e, ensure_ascii=False) for e in events) + "\n")
        return result
