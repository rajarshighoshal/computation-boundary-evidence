import asyncio
import time
from types import SimpleNamespace

import scicontext.extraction as extraction
from scicontext.extraction import run_extraction


class Driver:
    def __init__(self, delay=.02, usable=True):
        self.delay = delay
        self.usable = usable
        self.prepared = asyncio.Event()
        self.interpreting = asyncio.Event()
        self.calls = []

    async def prepare(self, seconds):
        self.calls.append("prepare")
        self.prepared.set()
        await self.interpreting.wait()
        return {"status": "ready"}

    async def interpret(self, instruction, seconds):
        self.calls.append("interpret")
        self.interpreting.set()
        await self.prepared.wait()
        await asyncio.sleep(self.delay)
        return {"status": "completed", "usage": {"input_tokens": 12}}

    async def assemble(self, outcomes, seconds):
        self.calls.append(("assemble", outcomes))
        return {"status": "usable_graph" if self.usable else "abstained", "usable": self.usable,
                "probes": [{"id": "p1"}, {"id": "p2"}] if self.usable else []}

    async def probe(self, specs, seconds):
        self.calls.append("probe")
        return [{"id": p["id"], "status": "failed"} for p in specs]


def test_preparation_overlaps_interpretation_and_stops_early():
    async def check():
        d = Driver()
        r = await run_extraction(d, "task", 1)
        assert d.calls.count("interpret") == 1
        assert r["status"] == "completed" and r["usable_checkpoint"]
        assert r["duration_seconds"] < .5
        assert set(p["name"] for p in r["phases"]) == {"prepare", "extract_draft", "assemble_initial", "probes", "assemble_observed"}
        assert d.calls[-1][1] == [{"id": "p1", "status": "failed"}, {"id": "p2", "status": "failed"}]
    asyncio.run(check())


def test_interpretation_timeout_can_use_saved_annotations_without_retry():
    async def check():
        d = Driver(delay=1)
        r = await run_extraction(d, "task", .2)
        assert r["status"] == "timeout" and r["usable_checkpoint"]
        assert r["usage"]["input_tokens"] is None
        assert d.calls.count("interpret") == 1
    asyncio.run(check())


def test_abstention_does_not_launch_probes_or_refinement():
    async def check():
        d = Driver(usable=False)
        r = await run_extraction(d, "task", 1)
        assert not r["usable_checkpoint"] and r["pipeline_status"] == "abstained"
        assert "probe" not in d.calls
        assert sum(isinstance(c, tuple) for c in d.calls) == 1
    asyncio.run(check())


def test_failed_preparation_is_recorded_not_hidden():
    async def check():
        d = Driver()
        async def fail(seconds):
            d.prepared.set()
            raise ValueError("packet unavailable")
        d.prepare = fail
        r = await run_extraction(d, "task", 1)
        phase = next(p for p in r["phases"] if p["name"] == "prepare")
        assert phase["status"] == "failed" and "packet unavailable" in phase["error"]
    asyncio.run(check())


def test_probe_timeout_does_not_lose_initial_checkpoint():
    async def check():
        d = Driver()
        async def slow(specs, seconds):
            await asyncio.sleep(10)
        d.probe = slow
        start = time.monotonic()
        r = await run_extraction(d, "task", .2)
        assert time.monotonic() - start < .5
        assert r["usable_checkpoint"]
        assert next(p for p in r["phases"] if p["name"] == "probes")["status"] == "timeout"
    asyncio.run(check())


def test_initial_assembly_uses_remaining_work_budget_not_fifteen_seconds(monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(extraction, "time", SimpleNamespace(monotonic=lambda: clock[0]))

    async def check():
        d = Driver(delay=0)
        original = d.interpret
        async def interpret(instruction, seconds):
            result = await original(instruction, seconds)
            clock[0] += 112
            return result
        async def assemble(outcomes, seconds):
            assert seconds == 188  # No quota withheld for an optional model revision.
            clock[0] += 20  # Slow enough to exceed the retired assembly cap.
            return {"status": "usable_graph", "usable": True, "probes": []}
        d.interpret, d.assemble = interpret, assemble
        result = await run_extraction(d, "task", 300)
        phase = next(p for p in result["phases"] if p["name"] == "assemble_initial")
        assert phase["allowance_seconds"] == 188
        assert phase["duration_seconds"] == 20
        assert result["usable_checkpoint"] and result["duration_seconds"] == 132
    asyncio.run(check())


def test_one_revision_receives_failed_observation_and_aggregates_all_calls():
    async def check():
        d = Driver(delay=0)
        async def revise(instruction, feedback, seconds):
            d.calls.append("revise")
            assert instruction == "task"
            assert feedback["public_probe_results"][0]["status"] == "failed"
            assert feedback["draft_assembly"]["usable"]
            return {"status": "completed", "usage": {"input_tokens": 7}}
        d.revise = revise
        result = await run_extraction(d, "task", 1)
        assert d.calls.count("revise") == 1
        assert [c["name"] for c in result["model_calls"]] == ["extract_draft", "extract_revision"]
        assert result["usage"]["input_tokens"] == 19
        assert result["usage"]["output_tokens"] is None
        assert result["selected_model_call"] == "extract_revision"
        assert d.calls.count("probe") == 1  # Unchanged failed experiments are not retried.
    asyncio.run(check())


def test_invalid_or_timed_out_revision_keeps_observed_draft():
    async def check(kind):
        d = Driver(delay=0)
        async def revise(instruction, feedback, seconds):
            if kind == "timeout":
                await asyncio.sleep(10)
            if kind == "malformed":
                return {"status": "completed", "annotations_status": "no_valid_annotations", "usage": {"input_tokens": 5}}
            d.usable = False
            return {"status": "completed", "usage": {"input_tokens": 5}}
        d.revise = revise
        result = await run_extraction(d, "task", .1)
        assert result["usable_checkpoint"]
        assert result["selected_model_call"] == "extract_draft"
        assert len(result["model_calls"]) == 2
        assert any(c == ("assemble", [{"id": "p1", "status": "failed"}, {"id": "p2", "status": "failed"}]) for c in d.calls)
        assert result["usage"]["input_tokens"] == (None if kind == "timeout" else 17)
    for kind in ("timeout", "malformed", "unusable"):
        asyncio.run(check(kind))


def test_failed_provider_does_not_trigger_revision():
    async def check(raises):
        d = Driver(delay=0)
        async def interpret(instruction, seconds):
            d.interpreting.set()
            if raises:
                raise RuntimeError("provider unavailable")
            return {"status": "failed", "exit_code": 1, "usage": {"input_tokens": 4}}
        async def revise(*args):
            raise AssertionError("Provider errors must not trigger correction")
        d.interpret, d.revise = interpret, revise
        result = await run_extraction(d, "task", .2)
        assert result["status"] == "failed"
        assert result["fatal_model_error"]
        assert len(result["model_calls"]) == 1
        assert result["usage"]["input_tokens"] is None
    asyncio.run(check(False))
    asyncio.run(check(True))


def test_completed_invalid_draft_can_receive_planned_correction():
    async def check():
        d = Driver(delay=0, usable=False)
        async def revise(instruction, feedback, seconds):
            assert not feedback["draft_assembly"]["usable"]
            d.usable = True
            return {"status": "completed", "usage": {"input_tokens": 3}}
        d.revise = revise
        result = await run_extraction(d, "task", 1)
        assert result["usable_checkpoint"] and result["selected_model_call"] == "extract_revision"
        assert d.calls.count("probe") == 1  # New revision probes are actually executed.
        assert result["probe_rounds"][0]["phase"] == "revision_probes"
    asyncio.run(check())


def test_slow_draft_gets_old_revision_quota_and_finishes_probe_before_optional_revision(monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(extraction, "time", SimpleNamespace(monotonic=lambda: clock[0]))
    async def check():
        d = Driver(delay=0)
        original = d.interpret
        async def interpret(instruction, seconds):
            result = await original(instruction, seconds)
            assert seconds == 225
            assert seconds > min(240, 300 * .45)  # Reproduce the retired early cutoff.
            clock[0] += seconds
            return result
        count = [0]
        async def assemble(outcomes, seconds):
            count[0] += 1
            assert seconds >= 20
            clock[0] += 20
            return {"status": "usable_graph", "usable": True, "probes": [{"id": "p1"}]}
        async def probe(specs, seconds):
            assert seconds == 30
            clock[0] += seconds
            return [{"id": "p1", "status": "failed"}]
        async def revise(instruction, feedback, seconds):
            raise AssertionError("Optional revision must not displace the first useful artifact")
        d.interpret, d.assemble, d.probe, d.revise = interpret, assemble, probe, revise
        result = await run_extraction(d, "task", 300)
        assert count[0] == 2
        assert result["selected_model_call"] == "extract_draft"
        assert result["revision"]["reason"] == "insufficient_time_for_optional_revision_and_execution"
        assert result["duration_seconds"] <= 300
    asyncio.run(check())


def test_slow_initial_assembly_is_not_cut_short_to_fund_optional_revision():
    async def check():
        d = Driver(delay=0)
        allowances = []
        async def assemble(outcomes, seconds):
            await asyncio.sleep(10)
        async def revise(instruction, feedback, seconds):
            allowances.append(seconds)
            assert feedback["draft_assembly"] is None
            return {"status": "completed", "annotations_status": "no_valid_annotations", "usage": {}}
        d.assemble, d.revise = assemble, revise
        result = await run_extraction(d, "task", .2)
        assert not allowances
        assert next(p for p in result["phases"] if p["name"] == "assemble_initial")["status"] == "timeout"
        assert len(result["model_calls"]) == 1
        assert result["duration_seconds"] < .3
    asyncio.run(check())


def test_reasoning_is_aggregated_separately_and_missing_is_unknown():
    calls = [{"status": "completed", "usage": {"input_tokens": 2, "output_tokens": 5,
              "cached_input_tokens": 0, "reasoning_output_tokens": 3}} for _ in range(2)]
    assert extraction.aggregate_usage(calls)["reasoning_output_tokens"] == 6
    assert extraction.aggregate_usage(calls)["output_tokens"] == 10
    calls[1]["usage"]["reasoning_output_tokens"] = None
    assert extraction.aggregate_usage(calls)["reasoning_output_tokens"] is None
    assert extraction.aggregate_usage(calls)["output_tokens"] == 10


def test_revision_provider_failure_retains_draft_but_marks_trial_fatal():
    async def check():
        d = Driver(delay=0)
        async def revise(*args):
            return {"status": "failed", "fatal_model_error": True, "error": "provider quota exceeded"}
        d.revise = revise
        result = await run_extraction(d, "task", 1)
        assert result["status"] == "failed" and result["fatal_model_error"]
        assert result["usable_checkpoint"] and result["selected_model_call"] == "extract_draft"
        assert len(result["model_calls"]) == 2
        assert not any(p["name"] == "assemble_final" for p in result["phases"])
    asyncio.run(check())


def test_outer_cancellation_preserves_interrupted_call_without_keyerror():
    async def check():
        d = Driver(delay=10)
        task = asyncio.create_task(run_extraction(d, "task", 30))
        await d.interpreting.wait()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        else:
            raise AssertionError("Outer cancellation must propagate")
        assert d.extraction_model_calls[0]["status"] == "interrupted"
        assert d.extraction_model_calls[0]["usage"] == {}
        assert next(p for p in d.extraction_phases if p["name"] == "extract_draft")["status"] == "interrupted"
    asyncio.run(check())


def test_unattempted_revision_is_not_a_model_call():
    async def check():
        d = Driver(delay=0)
        async def revise(*args):
            return {"status": "not_run", "model_attempted": False, "reason": "feedback too large"}
        d.revise = revise
        result = await run_extraction(d, "task", 1)
        assert len(result["model_calls"]) == 1
        assert not result["fatal_model_error"]
        assert result["usable_checkpoint"]
        assert next(p for p in result["phases"] if p["name"] == "extract_revision")["status"] == "not_run"
    asyncio.run(check())


def test_initial_assembly_is_cancelled_at_shared_work_deadline():
    async def check():
        d = Driver(delay=0)
        cancelled = []
        async def assemble(outcomes, seconds):
            try:
                await asyncio.sleep(10)
            finally:
                cancelled.append(True)
        d.assemble = assemble
        started = time.monotonic()
        result = await run_extraction(d, "task", .08)
        phase = next(p for p in result["phases"] if p["name"] == "assemble_initial")
        assert phase["status"] == "timeout" and cancelled
        assert not result["usable_checkpoint"] and "probe" not in d.calls
        assert time.monotonic() - started < .5
    asyncio.run(check())


def test_no_assembly_starts_after_work_budget_exhaustion(monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(extraction, "time", SimpleNamespace(monotonic=lambda: clock[0]))
    async def check():
        d = Driver(delay=0)
        original = d.interpret
        async def interpret(instruction, seconds):
            result = await original(instruction, seconds)
            clock[0] = 300
            return result
        d.interpret = interpret
        result = await run_extraction(d, "task", 300)
        assert not any(isinstance(call, tuple) for call in d.calls)
        assert next(p for p in result["phases"] if p["name"] == "assemble_initial")["status"] == "not_run"
    asyncio.run(check())


def test_draft_finishes_after_retired_cutoff_without_a_second_call():
    async def check():
        d = Driver(delay=.18)
        result = await run_extraction(d, "task", .3)
        assert result["status"] == "completed"
        assert result["usable_checkpoint"]
        assert len(result["model_calls"]) == 1
        draft = next(p for p in result["phases"] if p["name"] == "extract_draft")
        assert draft["duration_seconds"] > .3 * .45
        assert draft["allowance_seconds"] > .3 * .70
    asyncio.run(check())


def test_successful_probe_without_diagnostics_skips_revision():
    async def check():
        d = Driver(delay=0)
        async def probe(specs, seconds):
            return [{"id": s["id"], "status": "completed", "exit_code": 0} for s in specs]
        async def revise(*args):
            raise AssertionError("Do not spend another call when no correction is indicated")
        d.probe, d.revise = probe, revise
        result = await run_extraction(d, "task", 1)
        assert result["selected_model_call"] == "extract_draft"
        assert result["revision"]["reason"] == "no_correction_needed"
        assert len(result["model_calls"]) == 1
    asyncio.run(check())


def test_passing_probe_does_not_hide_unresolved_scientific_bindings():
    for diagnostic in ({"unresolved": ["c: unresolved consumer 'absent'"]},
                       {"scientific_binding_uses": [{"status": "unknown"}]}):
        assert extraction.revision_reasons({"usable": True, "probes": [{"id": "p"}],
            "assembly": diagnostic}, [{"id": "p", "status": "completed"}]) == ["grounding_diagnostics"]
