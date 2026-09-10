"""No-model integration of real binding, probe execution, revision and repair handoff."""
import asyncio
import copy
import shutil

import pytest

from scicontext.annotations import assemble_annotations
from scicontext.controller import TrialConfig, run_trial
from scicontext.extraction import run_extraction
from scicontext.packet import build_packet
from scicontext.probes import run_probes


class LocalDriver:
    def __init__(self, root, scratch, domain, bad_binding):
        self.root, self.scratch = root, scratch
        self.domain, self.bad_binding = domain, bad_binding
        self.ready = asyncio.Event()
        self.selected = None
        self.prompt = None
        self.revision_feedback = None
        self.finished = False

    async def prepare(self, seconds):
        self.packet = build_packet(self.root)
        self.packet["task_id"] = "synthetic"
        self.ready.set()
        return {"status": "ready"}

    def receipt(self):
        return {"status": "completed", "usage": {
            "input_tokens": 10, "cached_input_tokens": 4, "output_tokens": 3,
            "reasoning_output_tokens": 1}}

    async def interpret(self, instruction, seconds):
        await self.ready.wait()
        parameter = "distance" if self.domain == "numeric" else "edges"
        self.entity = next(e for e in self.packet["entries"]
                           if e.get("entity_role") == "parameter" and e.get("entity_symbols") == [parameter])
        returned = next(e for e in self.packet["entries"] if e["kind"] == "return")
        scientific = ("A rate of displacement", "Elapsed time is positive", "Accumulated distance-time product",
                      "Vary elapsed time at fixed displacement", "distance / elapsed") if self.domain == "numeric" else (
                      "Seed-connected spatial region", "Finite undirected neighborhood links",
                      "All nodes including disconnected regions", "Add a disconnected region", None)
        probe = ("from model import compute\nassert compute(6, 3) == 2\n" if self.domain == "numeric" else
                 "from model import compute\nassert compute([(0, 1), (4, 5)], 0) == [0, 1]\n")
        self.annotations = {"schema_version": "annotations-1.0", "quantities": [{
            "id": "q", "meaning": scientific[0],
            "entity_id": "missing_entity" if self.bad_binding else self.entity["id"]}],
            "claims": [{"id": "c", "description": "Follow the public definition, not the current buggy output",
                "scientific_object": scientific[0], "applicability": scientific[1],
                "alternative_interpretation": scientific[2], "discriminating_observation": scientific[3],
                "formula": scientific[4], "implementation_id": returned["id"], "consumer_ids": [returned["id"]],
                "quantities": ["q"], "evidence": [{"path": "paper.md", "start_line": 1, "end_line": 1}],
                "status": "explicit"}],
            "probes": [{"id": "p", "claim_ids": ["c"], "script": "check.py", "source": probe,
                        "description": "Check the expected relation from the public definition"}]}
        return self.receipt()

    async def assemble(self, outcomes, seconds):
        bundle = assemble_annotations(self.annotations, self.packet, self.root, probe_results=outcomes)
        if bundle["assembly"]["usable"]:
            self.selected = bundle
        return {"status": bundle["assembly"]["status"], "usable": bundle["assembly"]["usable"],
                "probes": bundle["probes"], "assembly": bundle["assembly"]}

    async def probe(self, specs, seconds):
        for spec in specs:
            (self.scratch / spec["script"]).write_text(spec["source"])
        return await asyncio.to_thread(run_probes, specs, self.root, self.scratch, seconds)

    async def revise(self, instruction, feedback, seconds):
        self.revision_feedback = copy.deepcopy(feedback)
        # A deterministic test double corrects the source binding, not the scientific expectation.
        self.annotations["quantities"][0]["entity_id"] = self.entity["id"]
        return {**self.receipt(), "annotations_status": "received"}

    async def run_stage(self, name, instruction, seconds):
        if name == "extract":
            return await run_extraction(self, instruction, seconds)
        self.prompt = instruction
        return self.receipt()

    async def collect_graph(self, seconds):
        return self.selected

    async def finish_extraction(self):
        self.finished = True

    async def cleanup(self):
        self.finished = True


@pytest.mark.parametrize("domain,bad_binding", [("numeric", True), ("discrete", True), ("numeric", False)])
def test_grounded_feedback_reaches_repair_without_claiming_probe_success(tmp_path, domain, bad_binding):
    if shutil.which("timeout") is None:
        pytest.skip("GNU timeout required by the existing public-probe runner")
    root, scratch = tmp_path / "task", tmp_path / "scratch"
    root.mkdir()
    scratch.mkdir()
    source = ("def compute(distance, elapsed):\n    return distance * elapsed\n" if domain == "numeric" else
              "def compute(edges, seed):\n    return sorted({n for edge in edges for n in edge})\n")
    definition = ("Rate is displacement divided by positive elapsed time.\n" if domain == "numeric" else
                  "A seed-connected region contains only nodes reachable from the seed along supplied undirected links.\n")
    (root / "model.py").write_text(source)
    (root / "paper.md").write_text(definition)
    driver = LocalDriver(root, scratch, domain, bad_binding)
    record = asyncio.run(run_trial(driver, TrialConfig(total_seconds=30, extraction_seconds=20),
                                  "synthetic", "science", "Inspect the public definition", tmp_path / "trial"))
    assert record["status"] == "completed" and driver.finished
    stage = record["stages"][0]
    assert [c["name"] for c in stage["model_calls"]] == ["extract_draft", "extract_revision"]
    assert stage["usage"]["input_tokens"] == 20 and stage["usage"]["output_tokens"] == 6
    assert stage["usage"]["reasoning_output_tokens"] == 2
    assert stage["selected_model_call"] == "extract_revision"
    feedback = driver.revision_feedback
    assert feedback["public_probe_results"][0]["status"] == "failed"
    assert feedback["public_probe_results"][0]["fingerprint"]
    initial = feedback["draft_assembly"]["assembly"]["code_bindings"][0]
    assert initial["status"] == ("unknown" if bad_binding else "source_matched")
    final = driver.selected
    assert final["assembly"]["code_bindings"][0]["binding_kind"] == "entity"
    assert final["graph"]["claims"][0]["quantity_ids"] == ["q"]
    assert final["graph"]["claims"][0]["scientific_object"] in driver.prompt
    assert "assert compute" in driver.prompt and "Rerun applicable" in driver.prompt
    if bad_binding:
        # Correcting a claim's code correspondence changes its probe interpretation identity.
        assert not final["graph"]["observations"]
        assert "unexecuted for this final interpretation" in driver.prompt
    else:
        assert final["graph"]["observations"]
        assert "failed, exit_code=1 (identity verified)" in driver.prompt
    assert (root / "model.py").read_text() == source


def test_timed_out_draft_with_pending_cleanup_is_fatal(tmp_path):
    class PendingDriver:
        async def prepare(self, seconds):
            return {"status": "ready"}
        async def interpret(self, instruction, seconds):
            try:
                await asyncio.sleep(10)
            finally:
                self._fatal_model_error = True
        async def assemble(self, outcomes, seconds):
            return {"status": "abstained", "usable": False, "probes": []}
        async def revise(self, instruction, feedback, seconds):
            raise AssertionError("must not revise after fatal cleanup")
    result = asyncio.run(run_extraction(PendingDriver(), "synthetic", .1))
    assert result["fatal_model_error"] and result["status"] == "failed"
    assert [c["name"] for c in result["model_calls"]] == ["extract_draft"]
