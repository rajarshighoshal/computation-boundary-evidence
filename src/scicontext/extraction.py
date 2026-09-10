"""One bounded public-feedback revision inside the shared extraction deadline."""
from __future__ import annotations

import asyncio
import time


def aggregate_usage(calls):
    keys = {"input_tokens", "cached_input_tokens", "output_tokens"}
    keys.update(k for c in calls for k in c.get("usage", {}) if k.endswith("_tokens"))
    complete = bool(calls) and all(c.get("status") == "completed" for c in calls)
    return {**{k: sum(c["usage"][k] for c in calls)
               if complete and all(type(c.get("usage", {}).get(k)) is int for c in calls)
               else None for k in keys},
            "accounting": "all_attempted_calls" if complete else "incomplete_attempted_call"}


async def run_extraction(driver, instruction: str, seconds: float) -> dict:
    """Reserve revision and final assembly before allowing draft work to start."""
    started = time.monotonic()
    deadline = started + seconds
    phases, calls = [], []

    def allowance(reserve=0):
        return max(0.0, deadline - time.monotonic() - seconds * reserve)

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
            return value
        except asyncio.TimeoutError:
            record["status"] = "timeout"
        except Exception as error:
            record.update(status="failed", error=f"{type(error).__name__}: {error}")
        finally:
            record["duration_seconds"] = time.monotonic() - beginning
            if model:
                receipt.update(name=name, status=record["status"], duration_seconds=record["duration_seconds"])
                receipt.setdefault("usage", {})
                if "error" in record:
                    receipt["error"] = record["error"]

    preparation = asyncio.create_task(phase("prepare", driver.prepare, min(30.0, seconds / 10)))
    try:
        draft = await phase("extract_draft", lambda s: driver.interpret(instruction, s),
                            min(240.0, seconds * .45), model=True)
        prepared = await preparation
        initial = await phase("assemble_initial", lambda s: driver.assemble(None, s), allowance(.45))
        final, observations = initial, []
        selected_call = "extract_draft" if initial and initial.get("usable") else None
        if initial and initial.get("usable") and initial.get("probes"):
            observations = await phase("probes", lambda s: driver.probe(initial["probes"], s), allowance(.35)) or []
            observed = await phase("assemble_observed", lambda s: driver.assemble(observations, s), allowance(.25))
            if observed and observed.get("usable"):
                final = observed
        # This is a planned correction, never a provider/execution retry.
        if draft and draft.get("status") == "completed" and hasattr(driver, "revise"):
            feedback = {"draft_assembly": initial, "observed_assembly": final,
                        "public_probe_results": observations,
                        "probe_phase": next((p for p in phases if p["name"] == "probes"), None)}
            revised = await phase("extract_revision", lambda s: driver.revise(instruction, feedback, s),
                                  allowance(.10), model=True)
            if revised and revised.get("status") == "completed" and revised.get("annotations_status") != "no_valid_annotations":
                assembled = await phase("assemble_final", lambda s: driver.assemble(observations, s), allowance())
                if assembled and assembled.get("usable"):
                    final = assembled
                    selected_call = "extract_revision"
        return {"status": (draft or {}).get("status", calls[0]["status"] if calls else "not_run"),
                "usage": aggregate_usage(calls), "model_calls": calls, "selected_model_call": selected_call,
                "cleanup_complete": None, "duration_seconds": time.monotonic() - started,
                "pipeline_status": (final or {}).get("status", "no_valid_annotations"),
                "usable_checkpoint": bool(final and final.get("usable")),
                "packet_status": (prepared or {}).get("status", "unavailable"), "phases": phases}
    finally:
        if not preparation.done():
            preparation.cancel()
        await asyncio.gather(preparation, return_exceptions=True)
