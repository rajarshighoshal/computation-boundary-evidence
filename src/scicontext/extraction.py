"""Bounded scientific-object extraction: prepare, one interpretation call, assemble."""
from __future__ import annotations

import asyncio
import time


def extraction_reserve(seconds: float) -> float:
    """Leave room for assembly and artifact transfer after the model call."""
    return min(75.0, seconds / 4)


def aggregate_usage(calls):
    keys = {"input_tokens", "cached_input_tokens", "output_tokens"}
    keys.update(k for c in calls for k in c.get("usage", {}) if k.endswith("_tokens"))
    complete = bool(calls) and all(c.get("status") == "completed" for c in calls)
    return {**{k: sum(c["usage"][k] for c in calls)
               if complete and all(type(c.get("usage", {}).get(k)) is int for c in calls)
               else None for k in keys},
            "accounting": "all_attempted_calls" if complete else "incomplete_attempted_call"}


async def run_extraction(driver, instruction: str, seconds: float) -> dict:
    """One shared budget: packet/objects preparation, then a single enrichment call."""
    started = time.monotonic()
    deadline = started + seconds
    phases, calls = [], []
    driver.extraction_model_calls = calls
    driver.extraction_phases = phases

    reserve = extraction_reserve(seconds)

    def allowance(reserve_seconds=0.0):
        return max(0.0, deadline - time.monotonic() - reserve_seconds)

    async def phase(name, operation, budget, model=False):
        beginning = time.monotonic()
        record = {"name": name, "started_offset_seconds": beginning - started,
                  "allowance_seconds": max(0.0, budget)}
        phases.append(record)
        if budget <= 0:
            record.update(status="not_run", duration_seconds=0.0)
            return None
        receipt = {"name": name}
        if model:
            calls.append(receipt)
        try:
            value = await asyncio.wait_for(operation(budget), timeout=budget)
            record["status"] = value.get("status", "completed") if isinstance(value, dict) else "completed"
            if model and isinstance(value, dict):
                receipt.update(value)
                if value.get("model_attempted") is False:
                    calls.remove(receipt)
            return value
        except asyncio.TimeoutError:
            record["status"] = "timeout"
        except asyncio.CancelledError:
            record["status"] = "interrupted"
            raise
        except Exception as error:
            record.update(status="failed", error=f"{type(error).__name__}: {error}")
        finally:
            record["duration_seconds"] = time.monotonic() - beginning
            if model:
                receipt.update(name=name, status=record["status"], duration_seconds=record["duration_seconds"])
                receipt.setdefault("usage", {})
                if "error" in record:
                    receipt["error"] = record["error"]

    flexible = bool(getattr(getattr(driver, "config", None), "flexible_budget", False))
    prepare_allowance = min(1200.0, seconds * 0.6) if flexible else min(30.0, seconds / 10)
    preparation = asyncio.create_task(phase("prepare", driver.prepare, prepare_allowance))
    try:
        prepared = await preparation
        draft = await phase("extract_draft", lambda s: driver.interpret(instruction, s),
                            allowance(reserve), model=True)
        prepared = await preparation
        initial = await phase("assemble_initial", lambda s: driver.assemble(s), allowance())
        fatal = (getattr(driver, "_fatal_model_error", False)
                 or any(c.get("fatal_model_error") or c.get("status") == "failed" for c in calls))
        return {"status": "failed" if fatal else (draft or {}).get("status", calls[0]["status"] if calls else "not_run"),
                "fatal_model_error": fatal,
                "usage": aggregate_usage(calls), "model_calls": calls,
                "selected_model_call": "extract_draft" if initial and initial.get("usable") else None,
                "cleanup_complete": None, "duration_seconds": time.monotonic() - started,
                "pipeline_status": (initial or {}).get("status", "no_valid_annotations"),
                "usable_checkpoint": bool(initial and initial.get("usable")),
                "packet_status": (prepared or {}).get("status", "unavailable"), "phases": phases}
    finally:
        if not preparation.done():
            preparation.cancel()
        await asyncio.gather(preparation, return_exceptions=True)
