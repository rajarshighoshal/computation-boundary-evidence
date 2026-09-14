"""One continuous DeepSeek agent with on-demand scientific evidence and repair tools.

Preparation builds a graph without model calls. Science queries and an optional
working model accompany ordinary tools; all stages share one task container and allowance.
Provider credentials remain on the host.
"""
from __future__ import annotations

import asyncio
import http.client
import json
import re
import subprocess
import shutil
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from pier.models.agent.network import NetworkAllowlist

from .assets import prepare_helpers
from .io import digest_file, digest_json, read_json, write_json, _safe_relative
from .pier_agent import CONTROL, REMOTE, SCRATCH, ScientificCodex, bounded_call
from .science_tools import tool_definition

API = "https://api.deepseek.com/chat/completions"
SCIENCE_STORE = REMOTE + "/context/science"
HELPER = f"SCICONTEXT_CONTEXT_ROOT={REMOTE}/context PYTHONPATH={REMOTE}/src:{REMOTE}/deps python -m scicontext.tool_cli"
MAX_OUTPUT_TOKENS = 65536
MAX_TOOL_OUTPUT_CHARS = 60_000
MAX_TOOL_SECONDS = 600
MAX_LOOP_ITERATIONS = 200
# Compaction rewrites earlier messages and invalidates the provider's
# prompt-prefix cache, where input is ~50x cheaper; keep it rare and
# leave the model's own context window as the guard.
MAX_CONVERSATION_TOOL_CHARS = 800_000
MAX_PROVIDER_ERROR_CHARS = 500
MAX_PROVIDER_BODY_CHARS = 1200
RETRYABLE_HTTP_STATUS = {429, 500, 502, 503, 504}


class DeepSeekProviderError(RuntimeError):
    """A bounded provider response failure with no credential-bearing body."""

    def __init__(self, metadata):
        self.metadata = metadata
        super().__init__(metadata.get("message", "DeepSeek provider response failure"))


def _redact_provider_text(value, api_key: str | None = None, limit=MAX_PROVIDER_ERROR_CHARS):
    text = "" if value is None else str(value)
    if api_key:
        text = text.replace(api_key, "[redacted]")
    text = re.sub(r"(?i)bearer\s+\S+", "Bearer [redacted]", text)
    text = re.sub(r"(?i)(api[_-]?key|secret|token)\s*[:=]\s*\S+", r"\1=[redacted]", text)
    return text[:limit]


def _provider_retryable(status, error):
    if status is not None and status >= 400:
        return status in RETRYABLE_HTTP_STATUS
    if not isinstance(error, dict):
        return False
    code = error.get("code")
    if isinstance(code, str) and code.isdigit():
        code = int(code)
    error_type = error.get("type")
    return (code in RETRYABLE_HTTP_STATUS if isinstance(code, int) else False) or (
        isinstance(error_type, str) and error_type in {
            "rate_limit_error", "server_error", "service_unavailable_error"})


def _response_payload(raw):
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return None


def _response_metadata(raw, *, status, attempt, max_attempts, api_key, retryable=None):
    payload = _response_payload(raw)
    error = payload.get("error") if isinstance(payload, dict) and isinstance(payload.get("error"), dict) else None
    choices = payload.get("choices") if isinstance(payload, dict) else None
    if error is not None:
        kind = "provider_error"
        error_type = error.get("type")
        code = error.get("code")
        message = error.get("message") or "DeepSeek provider returned an error"
    elif not isinstance(payload, dict) or not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        kind = "invalid_response"
        error_type = "invalid_response"
        code = None
        message = "DeepSeek response did not contain a usable choices array"
    else:
        kind = "invalid_response"
        error_type = "invalid_response"
        code = None
        message = "DeepSeek response did not contain a usable assistant message"
    body = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else str(raw or "")
    metadata = {
        "kind": kind,
        "status": status,
        "attempt": attempt,
        "max_attempts": max_attempts,
        "retryable": bool(retryable),
        "type": _redact_provider_text(error_type, api_key, 120),
        "code": _redact_provider_text(code, api_key, 120) if code is not None else None,
        "message": _redact_provider_text(message, api_key),
        "body": _redact_provider_text(body, api_key, MAX_PROVIDER_BODY_CHARS),
    }
    return metadata


async def _api_completion(api_key: str, model: str, messages: list, *,
                          tools=None, response_format=None, max_tokens=MAX_OUTPUT_TOKENS,
                          timeout_sec: float, temperature: float = 0.0, max_attempts: int = 2,
                          reasoning_effort="high") -> dict:
    body = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature}
    body["reasoning_effort"] = reasoning_effort
    if tools:
        body["tools"] = tools
    if response_format:
        body["response_format"] = response_format

    def send():
        last_error = None
        deadline = time.monotonic() + timeout_sec
        for attempt in range(max_attempts):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("Provider request exhausted its remaining task allowance")
            request = urllib.request.Request(API, data=json.dumps(body).encode(), method="POST", headers={
                "Authorization": f"Bearer {api_key}", "Content-Type": "application/json"})
            try:
                # Deadline-governed: no short hard cap, large tool-loop
                # contexts can legitimately take minutes.
                with urllib.request.urlopen(request, timeout=remaining) as response:
                    raw = response.read()
                    payload = _response_payload(raw)
                    if (isinstance(payload, dict) and not payload.get("error") and isinstance(payload.get("choices"), list)
                            and payload["choices"] and isinstance(payload["choices"][0], dict)
                            and isinstance(payload["choices"][0].get("message"), dict)):
                        return {**payload, "_api_attempts": attempt + 1}
                    error = payload.get("error") if isinstance(payload, dict) else None
                    retryable = _provider_retryable(response.status, error)
                    metadata = _response_metadata(raw, status=response.status, attempt=attempt + 1,
                                                  max_attempts=max_attempts, api_key=api_key,
                                                  retryable=retryable)
                    if retryable and attempt + 1 < max_attempts and deadline - time.monotonic() > 2:
                        time.sleep(2)
                        continue
                    raise DeepSeekProviderError(metadata)
            except urllib.error.HTTPError as error:
                raw = error.read()
                retryable = _provider_retryable(error.code, _response_payload(raw).get("error")
                                                if isinstance(_response_payload(raw), dict) else None)
                metadata = _response_metadata(raw, status=error.code, attempt=attempt + 1,
                                              max_attempts=max_attempts, api_key=api_key,
                                              retryable=retryable)
                if retryable and attempt + 1 < max_attempts and deadline - time.monotonic() > 2:
                    time.sleep(2)
                    continue
                raise DeepSeekProviderError(metadata)
            except (urllib.error.URLError, TimeoutError, OSError,
                    http.client.HTTPException, ConnectionError) as error:
                last_error = error
                if attempt + 1 < max_attempts and deadline - time.monotonic() > 2:
                    time.sleep(2)
        raise last_error

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


def _provider_response_error(completion, api_key=None):
    """Return a bounded, secret-safe receipt for a non-completion response."""
    if not isinstance(completion, dict):
        return {"kind": "invalid_response", "type": "invalid_response", "code": None,
                "message": "DeepSeek response was not a JSON object"}
    error = completion.get("error")
    if isinstance(error, dict):
        values = {key: error.get(key) for key in ("type", "code", "message")}
        message = str(values["message"] or "DeepSeek provider returned an error")
        # Error messages are provider-controlled; keep receipts useful without
        # allowing accidental credential/token echo into run artifacts.
        return {"kind": "provider_error", "type": _redact_provider_text(values["type"] or "provider_error", api_key, 120),
                "code": _redact_provider_text(values["code"], api_key, 120) if values["code"] is not None else None,
                "message": _redact_provider_text(message, api_key)}
    choices = completion.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        return {"kind": "invalid_response", "type": "missing_choices", "code": None,
                "message": "DeepSeek response did not contain a usable choices array"}
    return None


def _mark_usage_incomplete(usage):
    """Retain known completion-prefix usage while marking the failed call unknown."""
    usage["known_input_tokens"] = usage.get("input_tokens")
    usage["known_output_tokens"] = usage.get("output_tokens")
    fields = ("input_tokens", "output_tokens", "cached_input_tokens", "cache_hit_tokens",
              "cache_miss_tokens", "reasoning_output_tokens")
    usage["known_usage"] = {key: usage.get(key) for key in fields}
    for key in fields:
        usage[key] = None
    usage["accounting"] = "known_completed_calls_plus_unknown_inflight"
    usage["unknown_inflight_request"] = True


class DeepSeekAgent(ScientificCodex):
    interactive_science = True

    def network_allowlist(self):
        # Inference runs on the host. Empty allowlist selects Pier's standard
        # offline container mode, without an unnecessary OpenAI egress proxy.
        return NetworkAllowlist()

    def __init__(self, *args, deepseek_key_file=None, **kwargs):
        if not deepseek_key_file:
            raise ValueError("deepseek_key_file is required for the DeepSeek route")
        # The parent requires an existing auth-file path; the DeepSeek key file
        # satisfies that check without ever being read by the Codex path.
        kwargs.setdefault("extractor", "interactive_science")
        if kwargs["extractor"] != "interactive_science":
            raise ValueError("Use extractor=interactive_science; the forced interpretation workflow is retired")
        super().__init__(*args, auth_file=deepseek_key_file, **kwargs)
        self.deepseek_key = read_json(Path(deepseek_key_file).expanduser())["api_key"]
        self.model = self.config.model
        self._science_model_recorded = False
        self.shell_tools = [{"type": "function", "function": {
            "name": "shell", "description": (
                "Execute a command in the task repository container and return combined stdout/stderr "
                "(capped). Use it to inspect files, run tests and make edits with standard tools."),
            "parameters": {"type": "object",
                           "properties": {"command": {"type": "string",
                                                      "description": "Single bash command line to run."}},
                           "required": ["command"]}}}]

    async def _setup_environment(self, environment, stage):
        if self.condition == "science":
            await self.checked(environment, f"mkdir -p {CONTROL} {REMOTE}/src {REMOTE}/context {SCRATCH}/checkpoints {self.root}/outputs")
            await environment.upload_dir(self.helper_deps, REMOTE + "/deps")
            source_root = self.frozen_source / "scicontext" if self.frozen_source else self.workspace / "src/scicontext"
            await environment.upload_dir(source_root, REMOTE + "/src/scicontext")
            from .object_context import enrichment_schema
            await self._put(environment, "object-enrichment.schema.json", json.dumps(enrichment_schema()),
                            CONTROL + "/object-enrichment.schema.json")
            statement = (environment.environment_dir.parent / "instruction.md").read_text()
            await self._put(environment, "task_statement.md", statement, REMOTE + "/context/task_statement.md")
        else:
            # Plain repair uses only the task container and host-side API.
            # Do not expose method sources/dependencies or task-context files
            # that the baseline can mine despite not having the science tool.
            await self.checked(environment, f"mkdir -p {self.root}/outputs")
        probe = "import os; print(open('/proc/%s/statm' % os.getpid()).read().strip())"
        if self.task_id == "002":
            probe += "; from pyscf import lib; print(lib.current_memory())"
        output = await self.checked(environment, "python -c " + json.dumps(probe))
        (self.logs_dir / f"runtime-{stage}.log").write_text(output)
        if self.condition == "science":
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
        if self.condition == "science":
            self.helper_deps = await asyncio.to_thread(prepare_helpers, self.workspace / ".cache", pyminor)
        self._baseline_tree = (await self.checked(environment, "git rev-parse HEAD", cwd=self.root)).strip()
        self.codex_package = None
        self.extract_codex_package = None
        self.extraction_architecture = None
        await self._setup_environment(environment, "repair")
        write_json(self.logs_dir / "setup.json", {
            "agent": "deepseek", "model": self.model,
            "harness_architecture": "host_api", "scientific_image_architecture": "amd64",
            "environment_image": environment.task_env_config.docker_image,
            "execution": "host_side_deepseek_api_with_in_container_shell_tools",
            "extractor": "interactive_science_v1", "frozen_source": self.frozen_source is not None,
            "claim_cap": None, "probe_cap": 0,
            "extraction_model_call_cap": 0,
            "extraction_model_seconds": self.extraction_model_seconds,
            "extraction_harness_architecture": "host_api",
            "extraction_access_mode": "read-only" if self.condition == "science" else None,
            "revision_policy": "one_continuous_agent; shell_from_start; optional_revisable_scientific_model",
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

    async def prepare(self, seconds):
        # Code-derived construction first, before any model call: observe the
        # public workflow, build the static packet, merge execution-derived
        # loci into the objects graph. A failed trace degrades to the static
        # graph and never fails preparation.
        started = time.monotonic()
        construction = min(max(0.0, seconds) * 0.5, 600.0)
        report = {"status": "skipped", "budget_seconds": round(construction, 1)}
        if construction >= 30:
            report = await self._build_scientific_context(construction)
        remaining = max(1.0, seconds - (time.monotonic() - started))
        result = await self._science_command(None, remaining, prepare=True)
        if result.get("status") != "prepared":
            raise RuntimeError("Science index preparation failed: " + json.dumps(result))
        if not (result.get("scientific_graph") or {}).get("nodes"):
            # A file inventory is not the treatment: refuse index-only science
            # instead of silently repairing without the prepared graph.
            raise RuntimeError("Prepared scientific graph missing; refusing index-only science: "
                               + json.dumps({"construction": report,
                                             "graph": result.get("scientific_graph")}))
        if getattr(self, "extraction_only", False):
            # No-model query-path verification on the real task.
            try:
                check = await self._science_command(None, min(60.0, max(1.0, seconds - (time.monotonic() - started))),
                                                    self_check=True)
            except Exception as error:
                check = {"status": "error", "error": f"{type(error).__name__}: {error}"}
            write_json(self.logs_dir / "self-check.json", check)
            result["self_check"] = check
        self._science_prepared = result
        return {"status": "completed", "usage": {"input_tokens": 0, "cached_input_tokens": 0,
                "output_tokens": 0, "reasoning_output_tokens": 0}, "model_calls": [],
                "index": result, "construction": report}

    async def _helper(self, command, seconds):
        import shlex
        bounded = f"timeout --signal=TERM --kill-after=2s {max(.05, seconds - 3)}s bash -c {shlex.quote(command)}"
        output = await self.checked(self.environment, bounded, cwd=REMOTE, timeout_sec=max(1, seconds))
        return json.loads(output)

    async def _build_scientific_context(self, budget):
        import shlex
        deadline = time.monotonic() + budget
        report = {"status": "completed", "budget_seconds": round(budget, 1), "steps": {}}

        async def step(name, command, share):
            left = deadline - time.monotonic()
            seconds = min(max(5.0, budget * share), max(0.0, left))
            if left <= 5.0:
                report["steps"][name] = {"status": "skipped_budget"}
                return False
            try:
                report["steps"][name] = await self._helper(command, seconds)
                return True
            except Exception as error:
                report["steps"][name] = {"status": "failed", "error": f"{type(error).__name__}: {error}"[:300]}
                return False

        await self.checked(self.environment, f"mkdir -p {SCIENCE_STORE}", cwd=REMOTE)
        # trace: observe the public reproducer; the execution evidence layer.
        trace_seconds = max(10.0, budget * 0.4)
        traced = await step("trace",
            f"{HELPER} trace --root {self.root} --script {self.root}/reproduce.py "
            f"--out {SCIENCE_STORE}/trace --seconds {trace_seconds:.0f} --observe "
            f"--shims-dir {REMOTE}/src/scicontext/shims/out", share=0.45)
        # packet: static public-source evidence, seeded by the trace when present.
        packet_ok = await step("packet",
            f"{HELPER} packet --root {self.root} --context-root {REMOTE}/context --task-id {self.task_id} "
            f"--output {SCIENCE_STORE}/packet.json --catalog {SCIENCE_STORE}/catalog.md "
            f"--objects-output {SCIENCE_STORE}/scientific-objects.json "
            f"--enrichment-input {SCIENCE_STORE}/scientific-context-input.json "
            f"--trace-out {SCIENCE_STORE}/trace", share=0.35)
        # merge: execution-derived loci and quantity graph into the objects graph.
        merged = False
        if traced and packet_ok:
            merged = await step("merge",
                f"{HELPER} merge-dynamic --root {self.root} --graph {SCIENCE_STORE}/scientific-objects.json "
                f"--packet {SCIENCE_STORE}/packet.json --trace-out {SCIENCE_STORE}/trace "
                f"--output {SCIENCE_STORE}/scientific-objects.json "
                f"--enrichment-input {SCIENCE_STORE}/scientific-context-input.json", share=0.2)
        report["status"] = "completed" if packet_ok else "failed"
        report["traced"] = bool(traced)
        report["merged"] = bool(merged)
        write_json(self.logs_dir / "construction.json", report)
        return report

    async def collect_graph(self, seconds):
        from .io import digest_json
        if not getattr(self, "_science_prepared", None):
            return None
        template = ((self.frozen_source / "prompts/scientific_repair.md") if self.frozen_source
                    else self.workspace / "prompts/scientific_repair.md").read_text()
        index = self._science_prepared
        return {"graph_sha256": digest_json(index), "analysis": {"coverage": {}},
                "graph": {key: (index.get("scientific_graph") or {}).get(key)
                          for key in ("nodes", "edges", "findings", "bytes")},
                "construction": index.get("construction"),
                "handoff": template + "\nTask map: " + json.dumps(index["task_map"])}

    async def _science_command(self, request, seconds, prepare=False, self_check=False):
        import base64, shlex
        command = (f"PYTHONPATH={REMOTE}/src:{REMOTE}/deps PYTHONDONTWRITEBYTECODE=1 "
                   f"python -m scicontext.science_tools --root {shlex.quote(self.root)} "
                   f"--store {SCIENCE_STORE} ")
        if prepare:
            command += "--prepare"
        elif self_check:
            command += "--self-check"
        else:
            command += "--request " + shlex.quote(base64.b64encode(json.dumps(request).encode()).decode())
        started = time.monotonic()
        raw = await bounded_call(self.checked(self.environment, command, cwd=REMOTE,
                            timeout_sec=max(1, seconds)), max(1, seconds), set())
        result = json.loads(raw)
        wanted = result.get("backend_request")
        if wanted and shutil.which("joern-parse") and shutil.which("joern"):
            result = await self._analyze_query(command, result, wanted, max(1, seconds-(time.monotonic()-started)))
        elif wanted:
            result["analysis_gaps"] = [{"backend": "joern", "reason": "not_installed_on_host"}]
        return result

    async def _analyze_query(self, command, result, wanted, seconds):
        import shlex
        path = wanted["path"]
        if _safe_relative(path):
            raise ValueError("Invalid analysis source")
        directory = self.logs_dir / "source-analysis" / digest_json(wanted)[:20]
        source = directory / "source" / path
        output = directory / "backend"
        receipt = output / "receipt.json"
        try:
            if not receipt.exists():
                source.parent.mkdir(parents=True, exist_ok=True)
                await self.environment.download_file(self.root + "/" + path, source)
                if digest_file(source) != wanted["sha256"]:
                    raise ValueError("Source changed during query; request a fresh inspection")
                input_file = directory / "request.json"
                write_json(input_file, {"context": {"analysis_regions": [wanted]}})
                with (directory / "analyzer.log").open("w") as log:
                    process = await asyncio.create_subprocess_exec(sys.executable, "-m", "scicontext.source_backends",
                        "--root", str(directory / "source"), "--output", str(output), "--input", str(input_file),
                        stdout=log, stderr=asyncio.subprocess.STDOUT, start_new_session=True)
                    try:
                        code = await asyncio.wait_for(process.wait(), max(1, seconds * .8))
                    except BaseException:
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
                        raise RuntimeError("Analyzer failed; see preserved analyzer.log")
            remote = CONTROL + "/analysis-" + digest_json(wanted)[:20] + ".json"
            await self.environment.upload_file(receipt, remote)
            raw = await self.checked(self.environment, command + " --analysis " + shlex.quote(remote), cwd=REMOTE,
                                     timeout_sec=max(1, seconds * .2))
            return json.loads(raw)
        except Exception as error:
            result["analysis_gaps"] = [{"backend": "joern", "reason": str(error)}]
            return result

    async def finish_extraction(self):
        # Persist the science store (prepared graph, queries, recorded model) as
        # an artifact even when no repair stage ran, e.g. extraction-only checks.
        if self.condition != "science" or getattr(self, "environment", None) is None:
            return
        if (self.logs_dir / "science" / "state.json").is_file():
            return
        try:
            await bounded_call(self.environment.download_dir(REMOTE + "/context/science",
                                                             self.logs_dir / "science"), 10, set())
        except Exception as error:
            write_json(self.logs_dir / "science-download-error.json",
                       {"error": f"{type(error).__name__}: {error}"})

    async def run_stage(self, name, instruction, seconds):
        if name in {"prepare", "extract"}:
            return await self.prepare(seconds)
        prompt = instruction + f"\n\nTime allowance remaining: at most {max(1, int(seconds))} seconds."
        return await self._run_deepseek_repair(prompt, seconds)

    async def _execute_tool(self, call, seconds):
        function = call.get("function", {})
        name = function.get("name")
        event = {"type": "science_tool" if name == "science" else "command_execution", "exit_code": 1}
        try:
            arguments = json.loads(function.get("arguments") or "{}")
            if not isinstance(arguments, dict):
                raise ValueError("Tool arguments must be an object")
            if name == "science":
                if self.condition != "science":
                    raise ValueError("Science tool is not enabled in the baseline")
                event.update(action=arguments.get("action"), target=arguments.get("target"), query=arguments.get("query"))
                result = await self._science_command(arguments, min(MAX_TOOL_SECONDS, seconds))
                if arguments.get("action") == "record_model" and result.get("status") == "recorded":
                    write_json(self.logs_dir / "scientific-model-submitted.json", arguments["model"])
                    self._science_model_recorded = True
                event.update(exit_code=0 if result.get("status") != "error" else 1,
                             result_status=result.get("status"),
                             model_recorded=self._science_model_recorded)
                return json.dumps(result, ensure_ascii=False), event
            if name != "shell":
                raise ValueError("Unknown tool name")
            command = arguments.get("command")
            if not isinstance(command, str) or not command.strip():
                raise ValueError("Empty shell command refused")
            event["command"] = command
            output = await bounded_call(self.checked(self.environment, command, cwd=self.root,
                        timeout_sec=min(MAX_TOOL_SECONDS, max(0.05, seconds))), min(MAX_TOOL_SECONDS, max(0.05, seconds)), set())
            event["exit_code"] = 0
            return output[-MAX_TOOL_OUTPUT_CHARS:], event
        except Exception as error:
            return f"Tool error: {type(error).__name__}: {error}", event

    async def _run_deepseek_repair(self, prompt, seconds):
        (self.logs_dir / "repair-prompt.txt").write_text(prompt)
        deadline = time.monotonic() + seconds
        messages = [{"role": "user", "content": prompt}]
        usage = {"input_tokens": 0, "output_tokens": 0, "cached_input_tokens": 0,
                 "cache_hit_tokens": 0, "cache_miss_tokens": 0, "reasoning_output_tokens": 0}
        events = []
        session_log = []
        session_stream = (self.logs_dir / "repair-session.jsonl").open("a")
        result = {"status": "timeout", "usage": usage, "cleanup_complete": None,
                  "loop_exit": "iteration_cap"}
        try:
            for iteration in range(MAX_LOOP_ITERATIONS):
                remaining = deadline - time.monotonic()
                if remaining <= 1:
                    result["loop_exit"] = "time_cap"
                    break
                available_tools = list(self.shell_tools)
                if self.condition == "science":
                    available_tools.append(tool_definition())
                completion = await _api_completion(self.deepseek_key, self.model, messages,
                    tools=available_tools, timeout_sec=remaining, reasoning_effort=self.config.reasoning_effort)
                provider_error = _provider_response_error(completion, self.deepseek_key)
                if provider_error is not None:
                    event = {"type": "provider_error", "error": provider_error}
                    events.append(event)
                    session_stream.write(json.dumps(event, ensure_ascii=False) + "\n")
                    session_stream.flush()
                    _mark_usage_incomplete(usage)
                    result.update(status="failed", loop_exit="provider_error", fatal_model_error=True,
                                  error_kind=provider_error["kind"],
                                  error="DeepSeek provider response did not contain a usable completion",
                                  provider_error=provider_error)
                    self._fatal_model_error = True
                    break
                attempts = completion.get("_api_attempts", 1)
                if attempts > 1:
                    result["api_retry_requests"] = result.get("api_retry_requests", 0) + attempts - 1
                call_usage = completion.get("usage", {}) or {}
                usage["input_tokens"] += call_usage.get("prompt_tokens", 0)
                usage["output_tokens"] += call_usage.get("completion_tokens", 0)
                usage["cache_hit_tokens"] += call_usage.get("prompt_cache_hit_tokens", 0)
                usage["cache_miss_tokens"] += call_usage.get("prompt_cache_miss_tokens", 0)
                for key, value in (("cached_input_tokens", call_usage.get("prompt_cache_hit_tokens", call_usage.get("prompt_tokens_details", {}).get("cached_tokens"))),
                                   ("reasoning_output_tokens", call_usage.get("completion_tokens_details", {}).get("reasoning_tokens"))):
                    usage[key] = usage[key] + value if usage[key] is not None and type(value) is int else None
                message = completion["choices"][0]["message"]
                messages.append(message)
                step_record = {"step": len(session_log) + 1,
                               "api_attempts": attempts,
                               "provider_model": completion.get("model"),
                               "provider_fingerprint": completion.get("system_fingerprint"),
                               "content": message.get("content"),
                               "reasoning": message.get("reasoning_content"),
                               "tool_calls": message.get("tool_calls"),
                               "finish_reason": completion["choices"][0].get("finish_reason"),
                               "usage": completion.get("usage", {})}
                session_log.append(step_record)
                session_stream.write(json.dumps(step_record, ensure_ascii=False) + "\n")
                session_stream.flush()
                events.append({"type": "turn.started"})
                if message.get("tool_calls"):
                    for call in message["tool_calls"]:
                        tool_remaining = max(0.0, deadline - time.monotonic())
                        if tool_remaining <= 0:
                            break
                        output, event = await self._execute_tool(call, tool_remaining)
                        events.append({"type": "item.completed", "item": {"id": call["id"], **event,
                                      "aggregated_output": output}})
                        session_stream.write(json.dumps({"tool_result": call["id"], "event": event,
                                                          "output": output}, ensure_ascii=False) + "\n")
                        session_stream.flush()
                        messages.append({"role": "tool", "tool_call_id": call["id"], "content": output})
                    _compact_tools(messages)
                    continue
                content = message.get("content") or ""
                (self.logs_dir / "repair-final.txt").write_text(content)
                events.append({"type": "turn.completed", "usage": {
                    "input_tokens": usage["input_tokens"], "cached_input_tokens": usage["cached_input_tokens"],
                    "output_tokens": usage["output_tokens"], "reasoning_output_tokens": usage["reasoning_output_tokens"]}})
                result.update(status="completed", loop_exit="final_message",
                              finish_reason=completion["choices"][0].get("finish_reason"))
                break
        except DeepSeekProviderError as error:
            _mark_usage_incomplete(usage)
            event = {"type": "provider_error", "error": error.metadata}
            events.append(event)
            session_stream.write(json.dumps(event, ensure_ascii=False) + "\n")
            session_stream.flush()
            result.update(status="failed", loop_exit="provider_error", fatal_model_error=True,
                          error_kind=error.metadata.get("kind", "provider_error"),
                          error="DeepSeek provider response did not contain a usable completion",
                          provider_error=error.metadata)
            self._fatal_model_error = True
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            _mark_usage_incomplete(usage)
            result.update(status="failed", fatal_model_error=True, error=f"DeepSeek transport failure: {error}")
            self._fatal_model_error = True
        finally:
            if result.get("api_retry_requests") and not usage.get("unknown_inflight_request"):
                _mark_usage_incomplete(usage)
                if events and events[-1]["type"] == "turn.completed":
                    events[-1]["usage"] = {key: usage[key] for key in
                        ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens")}
            if ("usage" in result and events
                    and events[-1]["type"] not in {"turn.completed", "provider_error"}):
                events.append({"type": "turn.completed", "usage": {
                    "input_tokens": usage["input_tokens"], "cached_input_tokens": usage["cached_input_tokens"],
                    "output_tokens": usage["output_tokens"], "reasoning_output_tokens": usage["reasoning_output_tokens"]}})
            result["scientific_model_recorded"] = self._science_model_recorded if self.condition == "science" else None
            if self.condition == "science":
                try:
                    remaining = max(0.05, deadline-time.monotonic())
                    await bounded_call(self.environment.download_dir(REMOTE + "/context/science", self.logs_dir / "science"),
                                       min(20, remaining), set())
                except Exception as error:
                    result["science_artifact_error"] = str(error)
            session_stream.close()
            write_json(self.logs_dir / "repair-process.json", result)
            (self.logs_dir / "repair.jsonl").write_text("\n".join(json.dumps(e, ensure_ascii=False) for e in events) + "\n")
            write_json(self.logs_dir / "repair-session.json", {"messages": session_log,
                                                               "usage": usage, "status": result.get("status")})
        return result
