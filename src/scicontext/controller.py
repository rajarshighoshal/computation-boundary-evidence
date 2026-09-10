"""One monotonic budget for both conditions; backends provide execution/isolation."""
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

    def __post_init__(self):
        if not all(math.isfinite(v) and v > 0 for v in (self.total_seconds, self.extraction_seconds)):
            raise ValueError("Time allowances must be finite and positive")
        if self.extraction_seconds >= self.total_seconds:
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
                    if all(type(usage.get(k)) is int and usage[k] >= 0 for k in totals):
                        for key in totals:
                            totals[key] += usage[key]
                        seen += 1
    return {**(totals if seen else {k: None for k in totals}), "completed_turns": seen,
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
              "stages": [], "status": "running", "graph_sha256": None,
              "instruction_sha256": digest_json(instruction)}

    def save():
        write_json(output / "run.json", record)

    async def stage(name: str, prompt: str, seconds: float) -> dict:
        begin = time.monotonic()
        try:
            result = await asyncio.wait_for(driver.run_stage(name, prompt, seconds), timeout=max(0.001, seconds))
        except BaseException as error:
            # A killed/failed turn still consumed budget. Preserve its presence;
            # absent usage must not silently become zero in paired accounting.
            record["stages"].append({
                "name": name,
                "status": "timeout" if isinstance(error, asyncio.TimeoutError) else
                          "interrupted" if isinstance(error, asyncio.CancelledError) else "failed",
                "duration_seconds": time.monotonic() - begin,
                "cleanup_complete": None,
                "usage": {"input_tokens": None, "cached_input_tokens": None, "output_tokens": None,
                          "accounting": "unavailable_after_stage_exception"},
                "error": f"{type(error).__name__}: {error}",
            })
            save()
            raise
        result = {**result, "name": name, "duration_seconds": time.monotonic() - begin}
        record["stages"].append(result)
        save()
        if result.get("cleanup_complete") is False:
            raise RuntimeError(f"{name}: child process cleanup failed; refusing further execution")
        return result

    save()
    handoff = None
    try:
        if condition == "science":
            extraction_deadline = min(deadline, started + config.extraction_seconds)
            # Reserve a bounded portion for deterministic validation/copy/cleanup.
            reserve = min(60.0, config.extraction_seconds / 6)
            try:
                try:
                    await stage("extract", instruction, max(0.001, extraction_deadline - time.monotonic() - reserve))
                except asyncio.TimeoutError:
                    record["extraction_status"] = "timeout"
                # A final answer may be missing while an early checkpoint is
                # perfectly usable. Validation uses only the reserved time.
                # Artifact transfer must leave time for the ordinary container
                # shutdown as well; it cannot consume the whole reserve.
                shutdown_reserve = min(20.0, config.extraction_seconds / 12)
                left = extraction_deadline - time.monotonic() - shutdown_reserve
                if left > 0:
                    handoff = await asyncio.wait_for(driver.collect_graph(left), timeout=left)
            except asyncio.TimeoutError:
                record["extraction_status"] = "timeout"
            finally:
                try:
                    await asyncio.wait_for(driver.finish_extraction(),
                                           timeout=max(.001, extraction_deadline - time.monotonic()))
                except asyncio.TimeoutError:
                    record["extraction_status"] = "shutdown_timeout"
                    raise
            if time.monotonic() > extraction_deadline:
                handoff = None
                record["extraction_status"] = "budget_exceeded"
            if handoff is not None:
                record["graph_sha256"] = handoff["graph_sha256"]
                record["extraction_status"] = "usable_graph"
                record["graph_coverage"] = handoff.get("analysis", {}).get("coverage", {})
                write_json(output / "graph-bundle.json", handoff)
            else:
                record.setdefault("extraction_status", "no_valid_graph")
            save()
        remaining = deadline - time.monotonic()
        if extraction_only:
            record["status"] = "completed"
            record["extraction_only"] = True
        elif remaining > 0:
            prompt = instruction
            if handoff is not None:
                prompt += "\n\nSCIENTIFIC_CONTEXT_HANDOFF\n" + handoff["handoff"]
                prompt += "\nUse this fallible context when useful. Challenge inferred constraints with an evidence-based explanation."
            result = await stage("repair", prompt, remaining)
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
            cleanup_deadline = min(deadline, started + config.extraction_seconds) if extraction_only else deadline
            await asyncio.wait_for(driver.cleanup(), timeout=min(20.0, max(.001, cleanup_deadline - time.monotonic())))
        except Exception as error:
            record["status"] = "infrastructure_failure"
            record["cleanup_error"] = f"{type(error).__name__}: {error}"
        record["finished_at"] = utc_now()
        record["duration_seconds"] = time.monotonic() - started
        record["over_budget_seconds"] = max(0.0, record["duration_seconds"] - config.total_seconds)
        save()
    return record
