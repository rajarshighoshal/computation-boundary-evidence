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
        assert set(p["name"] for p in r["phases"]) == {"prepare", "interpret", "assemble_initial", "probes", "assemble_final"}
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
            assert seconds == 188
            clock[0] += 20  # Slow enough to exceed the retired assembly cap.
            return {"status": "usable_graph", "usable": True, "probes": []}
        d.interpret, d.assemble = interpret, assemble
        result = await run_extraction(d, "task", 300)
        phase = next(p for p in result["phases"] if p["name"] == "assemble_initial")
        assert phase["allowance_seconds"] == 188
        assert phase["duration_seconds"] == 20
        assert result["usable_checkpoint"] and result["duration_seconds"] == 132
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
