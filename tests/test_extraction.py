"""No-model flow checks: one budget, one enrichment call, assembly after."""
import asyncio

import scicontext.extraction as extraction
from scicontext.extraction import extraction_reserve, run_extraction


class Driver:
    def __init__(self, delay=.02, usable=True, draft_status="completed", fatal=False):
        self.delay = delay
        self.usable = usable
        self.draft_status = draft_status
        self.fatal = fatal
        self.calls = []

    async def prepare(self, seconds):
        self.calls.append("prepare")
        return {"status": "ready"}

    async def interpret(self, instruction, seconds):
        self.calls.append("interpret")
        await asyncio.sleep(self.delay)
        if self.fatal:
            return {"status": "failed", "fatal_model_error": True, "usage": {}}
        return {"status": self.draft_status, "usage": {"input_tokens": 12}}

    async def assemble(self, seconds):
        self.calls.append("assemble")
        return {"status": "usable_graph" if self.usable else "abstained", "usable": self.usable}


def test_preparation_precedes_interpretation_and_assembly():
    driver = Driver()
    result = asyncio.run(run_extraction(driver, "Inspect", 5))
    assert result["status"] == "completed"
    assert result["usable_checkpoint"] is True
    assert result["pipeline_status"] == "usable_graph"
    assert result["selected_model_call"] == "extract_draft"
    assert [c["name"] for c in result["model_calls"]] == ["extract_draft"]
    assert driver.calls == ["prepare", "interpret", "assemble"]


def test_interpretation_timeout_still_assembles_and_reports():
    driver = Driver(draft_status="timeout", usable=True)
    result = asyncio.run(run_extraction(driver, "Inspect", 5))
    assert result["status"] == "timeout"
    assert result["usable_checkpoint"] is True  # scratch-written partial annotations may exist
    assert result["selected_model_call"] == "extract_draft"
    assert result["usage"]["accounting"] == "incomplete_attempted_call"


def test_abstention_yields_no_selected_call_without_error():
    driver = Driver(usable=False)
    result = asyncio.run(run_extraction(driver, "Inspect", 5))
    assert result["status"] == "completed"
    assert result["usable_checkpoint"] is False
    assert result["pipeline_status"] == "abstained"
    assert result["selected_model_call"] is None


def test_failed_preparation_is_recorded_not_hidden():
    async def broken(seconds):
        raise RuntimeError("packet failed")
    driver = Driver()
    driver.prepare = broken
    result = asyncio.run(run_extraction(driver, "Inspect", 5))
    assert result["packet_status"] == "unavailable"
    assert any(p["name"] == "prepare" and p["status"] == "failed" for p in result["phases"])


def test_failed_model_call_is_fatal_without_repair_authorization():
    driver = Driver(fatal=True)
    result = asyncio.run(run_extraction(driver, "Inspect", 5))
    assert result["fatal_model_error"] is True
    assert result["status"] == "failed"


def test_budget_zero_skips_phases_instead_of_crashing():
    driver = Driver()
    result = asyncio.run(run_extraction(driver, "Inspect", .01))
    assert result["duration_seconds"] >= 0
    assert any(p["status"] in {"not_run", "timeout"} for p in result["phases"])


def test_reasoning_is_aggregated_separately_and_missing_is_unknown():
    calls = [{"status": "completed", "usage": {"input_tokens": 10, "cached_input_tokens": 4,
               "output_tokens": 6, "reasoning_output_tokens": 5}},
             {"status": "completed", "usage": {"input_tokens": 8, "cached_input_tokens": 3,
               "output_tokens": 4, "reasoning_output_tokens": 3}}]
    assert extraction.aggregate_usage(calls)["reasoning_output_tokens"] == 8
    del calls[0]["usage"]["reasoning_output_tokens"]
    assert extraction.aggregate_usage(calls)["reasoning_output_tokens"] is None
    assert extraction.aggregate_usage([])["input_tokens"] is None


def test_reserve_leaves_room_and_is_capped():
    assert 0 < extraction_reserve(300) <= 75
    assert extraction_reserve(600) == 75
