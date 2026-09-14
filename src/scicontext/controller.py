"""One work budget for both conditions; provider retry backoff is measured separately."""
from __future__ import annotations

import asyncio
import math
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol

from .io import digest_json, utc_now, write_json


@dataclass(frozen=True)
class TrialConfig:
    model: str = "gpt-6-astra"
    reasoning_effort: str = "high"
    codex_version: str = "0.153.4"
    total_seconds: float = 1800.0
    extraction_seconds: float = 360.0
    flexible_budget: bool = False

    def __post_init__(self):
        if not all(math.isfinite(v) and v > 0 for v in (self.total_seconds, self.extraction_seconds)):
            raise ValueError("Time allowances must be finite and positive")
        if not self.flexible_budget and self.extraction_seconds >= self.total_seconds:
            raise ValueError("Extraction must leave repair time")


class Driver(Protocol):
    async def run_stage(self, name: str, instruction: str, seconds: float) -> dict: ...
    async def collect_graph(self, seconds: float) -> dict | None: ...
    async def finish_extraction(self) -> None: ...
    async def cleanup(self) -> None: ...


def read_usage(path: Path) -> dict:
    """Only sum explicit completed-turn usage; a killed turn remains unaccounted."""
    import json

    totals = {"input_tokens": 0, "cached_input_tokens": 0, "output_tokens": 0}
    seen = 0
    malformed = 0
    reasoning = []
    cache_complete = True
    if path.is_file():
        with path.open(errors="replace") as stream:
            for line in stream:
                try:
                    event = json.loads(line)
                except ValueError:
                    malformed += 1
                    continue
                if event.get("type") == "turn.completed" and isinstance(event.get("usage"), dict):
                    usage = event["usage"]
                    if all(type(usage.get(k)) is int and usage[k] >= 0 for k in ("input_tokens", "output_tokens")):
                        for key in ("input_tokens", "output_tokens"):
                            totals[key] += usage[key]
                        if type(usage.get("cached_input_tokens")) is int and usage["cached_input_tokens"] >= 0:
                            totals["cached_input_tokens"] += usage["cached_input_tokens"]
                        else:
                            cache_complete = False
                        value = usage.get("reasoning_output_tokens")
                        reasoning.append(value if type(value) is int and 0 <= value <= usage["output_tokens"] else None)
                        seen += 1
    if not cache_complete:
        totals["cached_input_tokens"] = None
    return {**(totals if seen else {k: None for k in totals}), "completed_turns": seen,
            "reasoning_output_tokens": sum(reasoning) if reasoning and all(v is not None for v in reasoning) else None,
            "malformed_log_lines": malformed, "accounting": "completed_turn_events_only"}


def verify_smoke(events: Path, final: Path) -> bool:
    """Require a completed real turn and the requested successful shell result."""
    import json

    if not final.is_file() or final.read_text().strip() != "READY":
        return False
    if not read_usage(events)["completed_turns"]:
        return False
    for line in events.read_text(errors="replace").splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        item = event.get("item", {})
        if (event.get("type") == "item.completed" and item.get("type") == "command_execution"
                and item.get("exit_code") == 0 and item.get("aggregated_output", "").strip() == "42"):
            return True
    return False


async def run_trial(driver: Driver, config: TrialConfig, task_id: str, condition: str,
                    instruction: str, output: Path, *, extraction_only: bool = False) -> dict:
    if condition not in {"baseline", "science"}:
        raise ValueError("Unknown condition")
    if extraction_only and condition != "science":
        raise ValueError("Extraction-only verification requires the science condition")
    if (output / "run.json").exists():
        raise FileExistsError("Trial artifact already exists; preserve prior attempts")
    output.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    deadline = started + config.total_seconds
    record = {"schema_version": "1.0", "task_id": task_id, "condition": condition,
              "model": config.model, "reasoning_effort": config.reasoning_effort,
              "codex_version": config.codex_version, "config": asdict(config),
              "started_at": utc_now(), "finished_at": None, "duration_seconds": None,
              "provider_retry_wait_seconds": 0.0,
              "time_budget_basis": "work_time_excluding_provider_retry_backoff",
              "stages": [], "status": "running", "graph_sha256": None,
              "instruction_sha256": digest_json(instruction)}

    def save():
        write_json(output / "run.json", record)

    async def stage(name: str, prompt: str, seconds: float) -> dict:
        begin = time.monotonic()
        stage_wait = 0.0
        timer = asyncio.timeout(max(0.001, seconds))
        previous_wait = getattr(driver, "wait_for_provider_retry", None)

        async def wait_for_retry(delay):
            nonlocal deadline, stage_wait
            before_wait = time.monotonic()
            expires = timer.when()
            timer.reschedule(None)
            try:
                await asyncio.sleep(delay)
            finally:
                elapsed = time.monotonic() - before_wait
                deadline += elapsed
                stage_wait += elapsed
                record["provider_retry_wait_seconds"] += elapsed
                timer.reschedule(expires + elapsed)

        def timing():
            wall = time.monotonic() - begin
            return {"duration_seconds": wall, "provider_retry_wait_seconds": stage_wait,
                    "work_seconds": max(0.0, wall - stage_wait)}

        driver.wait_for_provider_retry = wait_for_retry
        try:
            async with timer:
                result = await driver.run_stage(name, prompt, seconds)
        except BaseException as error:
            # A killed/failed turn still consumed budget. Preserve its presence;
            # absent usage must not silently become zero in paired accounting.
            record["stages"].append({
                "name": name,
                "status": "timeout" if isinstance(error, asyncio.TimeoutError) else
                          "interrupted" if isinstance(error, asyncio.CancelledError) else "failed",
                **timing(),
                "cleanup_complete": None,
                "usage": {"input_tokens": None, "cached_input_tokens": None, "output_tokens": None,
                          "accounting": "unavailable_after_stage_exception"},
                "error": f"{type(error).__name__}: {error}",
            })
            save()
            raise
        finally:
            driver.wait_for_provider_retry = previous_wait
        result = {**result, "name": name, **timing()}
        record["stages"].append(result)
        save()
        if result.get("cleanup_complete") is False:
            raise RuntimeError(f"{name}: child process cleanup failed; refusing further execution")
        return result

    save()
    handoff = None
    try:
        if condition == "science":
            prepared = await stage("prepare", instruction, max(0.001, deadline - time.monotonic()))
            if prepared.get("status") != "completed":
                raise RuntimeError("Scientific source preparation failed")
            handoff = await asyncio.wait_for(driver.collect_graph(max(0.001, deadline-time.monotonic())),
                                             timeout=max(0.001, deadline-time.monotonic()))
            if handoff is None:
                raise RuntimeError("Science tool preparation did not produce a usable index")
            record["graph_sha256"] = handoff["graph_sha256"]
            record["extraction_status"] = ("prepared_graph"
                if (handoff.get("graph") or {}).get("nodes") else "prepared_index")
            record["graph_coverage"] = handoff.get("analysis", {}).get("coverage", {})
            write_json(output / "graph-bundle.json", handoff)
            save()
        remaining = deadline - time.monotonic()
        if extraction_only:
            record["status"] = "completed"
            record["extraction_only"] = True
        elif remaining > 0:
            prompt = instruction
            if handoff is not None:
                record["treatment_delivered"] = True
                guide = handoff.get("guide_markdown")
                if guide:
                    prompt += "\n\n" + guide
                prompt += "\n" + handoff["handoff"]
            result = await stage("repair", prompt, remaining)
            record["scientific_model_recorded"] = result.get("scientific_model_recorded")
            if result.get("fatal_model_error") or getattr(driver, "_fatal_model_error", False):
                raise RuntimeError("Repair model execution failed; inspect this attempt's receipt.")
            record["status"] = result.get("status", "completed")
        else:
            record["status"] = "timeout"
    except asyncio.TimeoutError:
        record["status"] = "timeout"
    except asyncio.CancelledError:
        record["status"] = "interrupted"
        raise
    except Exception as error:
        record["status"] = "infrastructure_failure"
        record["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        try:
            cleanup_deadline = deadline
            await asyncio.wait_for(driver.cleanup(), timeout=min(20.0, max(.001, cleanup_deadline - time.monotonic())))
        except Exception as error:
            record["status"] = "infrastructure_failure"
            record["cleanup_error"] = f"{type(error).__name__}: {error}"
        record["finished_at"] = utc_now()
        record["duration_seconds"] = time.monotonic() - started
        record["work_seconds"] = max(0.0, record["duration_seconds"] - record["provider_retry_wait_seconds"])
        record["over_budget_seconds"] = max(0.0, record["work_seconds"] - config.total_seconds)
        save()
    return record
