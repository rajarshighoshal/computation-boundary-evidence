"""Probe-first extraction with an optional correction in one shared work budget."""
from __future__ import annotations

import asyncio
import copy
import hashlib
import time


def extraction_reserve(seconds: float) -> float:
    """Leave room for assembly, a small public probe, and its observed handoff.

    This is code-owned work, not a reserved second model call. At the standard
    300-second work allowance the draft gets 225 seconds instead of 135.
    """
    return min(75.0, seconds / 4)


def matching_results(specs, results):
    """Select actual receipts for the current interpretation; retain history outside it."""
    selected = []
    for spec in specs:
        for result in reversed(results):
            if result.get("id") != spec.get("id"):
                continue
            if spec.get("fingerprint") and (
                    result.get("fingerprint") != spec["fingerprint"] or
                    result.get("script_sha256") != hashlib.sha256(spec["source"].encode()).hexdigest()):
                continue
            selected.append(result)
            break
    return selected


def revision_reasons(bundle, observations):
    if not bundle or not bundle.get("usable"):
        return ["no_usable_draft"]
    reasons = []
    if not bundle.get("probes"):
        reasons.append("no_executable_probe")
    assembly = bundle.get("assembly", {})
    if (assembly.get("rejected") or assembly.get("unresolved")
            or any(b.get("status") != "source_matched" for b in assembly.get("code_bindings", []))
            or any(b.get("status") == "unknown" for b in assembly.get("scientific_binding_uses", []))):
        reasons.append("grounding_diagnostics")
    if bundle.get("probes") and (len(observations) < len(bundle["probes"])
                                or any(r.get("status") != "completed" for r in observations)):
        # A failing assertion can be the desired bug witness. Feedback asks for
        # interpretation, not a weakened expectation or an automatic retry.
        reasons.append("probe_feedback")
    return reasons


def aggregate_usage(calls):
    keys = {"input_tokens", "cached_input_tokens", "output_tokens"}
    keys.update(k for c in calls for k in c.get("usage", {}) if k.endswith("_tokens"))
    complete = bool(calls) and all(c.get("status") == "completed" for c in calls)
    return {**{k: sum(c["usage"][k] for c in calls)
               if complete and all(type(c.get("usage", {}).get(k)) is int for c in calls)
               else None for k in keys},
            "accounting": "all_attempted_calls" if complete else "incomplete_attempted_call"}


async def run_extraction(driver, instruction: str, seconds: float) -> dict:
    """Get a useful draft and execute it first; correction is never owed a quota."""
    started = time.monotonic()
    deadline = started + seconds
    phases, calls = [], []
    driver.extraction_model_calls = calls
    driver.extraction_phases = phases

    reserve = extraction_reserve(seconds)
    assembly_reserve = min(25.0, seconds / 12)

    def allowance(reserve_seconds=0):
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

    preparation = asyncio.create_task(phase("prepare", driver.prepare, min(30.0, seconds / 10)))
    try:
        object_mode = getattr(driver, "extraction_mode", "annotations") == "scientific_objects"
        # The scientific reader needs the actual derived object graph in its
        # input. Legacy interpretation/preparation overlap remains reproducible.
        prepared = await preparation if object_mode else None
        draft = await phase("extract_draft", lambda s: driver.interpret(instruction, s),
                            allowance(reserve), model=True)
        prepared = await preparation
        initial = await phase("assemble_initial", lambda s: driver.assemble(None, s), allowance())
        final, observations = initial, []
        attempted_specs, probe_rounds = [], []
        selected_call = "extract_draft" if initial and initial.get("usable") else None

        async def execute_probes(bundle, name, assembly_name):
            nonlocal final
            specs = [s for s in bundle.get("probes", []) if s not in attempted_specs]
            if not specs:
                return
            budget = min(50.0, allowance(assembly_reserve))
            if budget > 0:
                attempted_specs.extend(copy.deepcopy(specs))
            outcomes = await phase(name, lambda s: driver.probe(specs, s), budget) or []
            probe_rounds.append({"phase": name, "specs": copy.deepcopy(specs), "results": outcomes})
            observations.extend(outcomes)
            if outcomes:
                observed = await phase(assembly_name,
                    lambda s: driver.assemble(matching_results(bundle["probes"], observations), s), allowance())
                if observed and observed.get("usable"):
                    final = observed

        if not object_mode and initial and initial.get("usable") and initial.get("probes"):
            await execute_probes(initial, "probes", "assemble_observed")
        reasons = revision_reasons(final, observations)
        revision_budget = allowance(reserve)
        revision = {"status": "not_run", "reasons": reasons, "allowance_seconds": revision_budget}
        # This is a planned correction, never a provider/execution retry.
        if (not object_mode and draft and draft.get("status") == "completed" and not draft.get("fatal_model_error")
                and not getattr(driver, "_fatal_model_error", False) and hasattr(driver, "revise")
                and reasons and revision_budget >= min(60.0, seconds / 5)):
            feedback = {"draft_assembly": initial, "observed_assembly": final,
                        "public_probe_results": copy.deepcopy(observations),
                        "revision_reasons": reasons,
                        "probe_phase": next((p for p in phases if p["name"] == "probes"), None)}
            revised = await phase("extract_revision", lambda s: driver.revise(instruction, feedback, s),
                                  revision_budget, model=True)
            revision["status"] = (revised or {}).get("status", phases[-1]["status"])
            if revised and revised.get("status") == "completed" and not revised.get("fatal_model_error") and revised.get("annotations_status") != "no_valid_annotations":
                assembled = await phase("assemble_final", lambda s: driver.assemble(list(observations), s), allowance())
                if assembled and assembled.get("usable"):
                    final = assembled
                    selected_call = "extract_revision"
                    await execute_probes(assembled, "revision_probes", "assemble_revision_observed")
        elif object_mode:
            revision["reason"] = "not_part_of_scientific_object_enrichment"
        elif not reasons:
            revision["reason"] = "no_correction_needed"
        elif revision_budget < min(60.0, seconds / 5):
            revision["reason"] = "insufficient_time_for_optional_revision_and_execution"
        else:
            revision["reason"] = "draft_not_completed_or_revision_unavailable"
        fatal = (getattr(driver, "_fatal_model_error", False)
                 or any(c.get("fatal_model_error") or c.get("status") == "failed" for c in calls))
        final_specs = (final or {}).get("probes", [])
        final_results = matching_results(final_specs, observations)
        executed_ids = [r["id"] for r in final_results if r.get("exit_code") is not None]
        return {"status": "failed" if fatal else (draft or {}).get("status", calls[0]["status"] if calls else "not_run"),
                "fatal_model_error": fatal,
                "usage": aggregate_usage(calls), "model_calls": calls, "selected_model_call": selected_call,
                "revision": revision, "probe_rounds": probe_rounds,
                "probe_delivery": {"accepted_ids": [s["id"] for s in final_specs],
                    "executed_ids": executed_ids,
                    "status": "none_retained" if not final_specs else
                        "executed" if len(executed_ids) == len(final_specs) else "partly_or_not_executed"},
                "cleanup_complete": None, "duration_seconds": time.monotonic() - started,
                "pipeline_status": (final or {}).get("status", "no_valid_annotations"),
                "usable_checkpoint": bool(final and final.get("usable")),
                "packet_status": (prepared or {}).get("status", "unavailable"), "phases": phases}
    finally:
        if not preparation.done():
            preparation.cancel()
        await asyncio.gather(preparation, return_exceptions=True)
