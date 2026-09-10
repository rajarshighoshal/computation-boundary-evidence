"""Bounded extraction phases using ordinary asyncio tasks and shared deadlines."""
from __future__ import annotations

import asyncio
import time


async def run_extraction(driver, instruction: str, seconds: float) -> dict:
    """Overlap preparation/interpretation, then assemble and execute probes.

    ``seconds`` excludes the outer controller's collection/cleanup reserve.
    Driver methods return compact receipts, not model-generated full graphs.
    """
    started = time.monotonic()
    deadline = started + seconds
    phases = []

    async def phase(name, operation, allowance):
        beginning = time.monotonic()
        record = {"name": name, "started_offset_seconds": beginning - started,
                  "allowance_seconds": max(0.0, allowance)}
        phases.append(record)
        if allowance <= 0:
            record.update(status="not_run", duration_seconds=0.0)
            return None
        try:
            value = await asyncio.wait_for(operation(allowance), timeout=allowance)
            record["status"] = value.get("status", "completed") if isinstance(value, dict) else "completed"
            return value
        except asyncio.TimeoutError:
            record["status"] = "timeout"
            return None
        except Exception as error:
            record.update(status="failed", error=f"{type(error).__name__}: {error}")
            return None
        finally:
            record["duration_seconds"] = time.monotonic() - beginning

    preparation = asyncio.create_task(phase("prepare", driver.prepare,
                                            min(30.0, seconds / 10)))
    try:
        model = await phase("interpret", lambda remaining: driver.interpret(instruction, remaining),
                            min(240.0, seconds * .8))
        prepared = await preparation
        initial = await phase("assemble_initial", lambda remaining: driver.assemble(None, remaining),
                              min(15.0, deadline - time.monotonic()))
        final = initial
        if initial and initial.get("usable") and initial.get("probes"):
            reserve = min(15.0, seconds / 10)
            results = await phase("probes", lambda remaining: driver.probe(initial["probes"], remaining),
                                  max(0.0, deadline - time.monotonic() - reserve))
            # The initial checkpoint survives if the probe/final phase is cut off.
            revised = await phase("assemble_final", lambda remaining: driver.assemble(results or [], remaining),
                                  deadline - time.monotonic())
            if revised and revised.get("usable"):
                final = revised
        unknown_usage = {"input_tokens": None, "cached_input_tokens": None, "output_tokens": None,
                         "accounting": "unavailable_after_interpretation_timeout"}
        interpretation_status = next(p["status"] for p in phases if p["name"] == "interpret")
        return {"status": (model or {}).get("status", interpretation_status),
                "usage": (model or {}).get("usage", unknown_usage),
                "cleanup_complete": None,
                "duration_seconds": time.monotonic() - started,
                "pipeline_status": (final or {}).get("status", "no_valid_annotations"),
                "usable_checkpoint": bool(final and final.get("usable")),
                "packet_status": (prepared or {}).get("status", "unavailable"),
                "phases": phases}
    finally:
        if not preparation.done():
            preparation.cancel()
        await asyncio.gather(preparation, return_exceptions=True)
