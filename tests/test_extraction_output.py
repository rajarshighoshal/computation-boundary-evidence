import asyncio
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

pytest.importorskip("pier")

from scicontext.annotations import assemble_annotations
from scicontext.extraction import run_extraction
from scicontext.pier_agent import REMOTE, SCRATCH, ScientificCodex, revision_feedback


class Environment:
    def __init__(self):
        self.files = {}
        self.commands = []

    async def upload_file(self, source, destination):
        self.files[destination] = source.read_text()

    async def download_file(self, source, destination):
        destination.write_text(self.files[source])

    async def download_dir(self, source, destination):
        pass

    async def exec(self, command, **kwargs):
        self.commands.append(command)
        return SimpleNamespace(return_code=0, stdout="", stderr="")


@pytest.fixture
def driver(tmp_path):
    logs = tmp_path / "logs"
    logs.mkdir()
    temporary = tmp_path / "uploads"
    temporary.mkdir()
    d = SimpleNamespace(workspace=Path(__file__).resolve().parents[1], root=str(tmp_path),
                        logs_dir=logs, task_id="058", extract_environment=Environment(),
                        _temporary=SimpleNamespace(name=str(temporary)), _selected_remote=None)
    for name in ("_put", "checked", "interpret", "_interpret_call", "probe", "collect_graph", "assemble"):
        setattr(d, name, getattr(ScientificCodex, name).__get__(d))
    return d


def test_final_json_is_saved_by_code_and_inline_probe_is_saved_after_assembly(driver):
    async def check():
        root = Path(driver.root)
        document = root / "README.md"
        document.write_text("Speed is distance divided by time.\n")
        packet = {"task_id": "058", "documents": [{"id": "doc_speed", "path": "README.md",
                  "start_line": 1, "end_line": 1,
                  "sha256": hashlib.sha256(document.read_bytes()).hexdigest()}]}
        annotations = {"schema_version": "annotations-1.0", "quantities": [], "claims": [
            {"id": "c_speed", "description": "Speed is distance divided by time.",
             "evidence": ["doc_speed"]}], "probes": [
            {"id": "p_speed", "claim_ids": ["c_speed"], "script": "probes/speed.py",
             "source": "print(2 / 1)\n", "description": "Check a simple speed ratio."}]}

        async def model(stage, prompt, seconds):
            assert stage == "extract_draft"
            assert "do not edit task source or write annotation/probe files" in prompt
            assert "ONLY the compact annotation JSON object" in prompt
            (driver.logs_dir / "extract_draft-final.txt").write_text(json.dumps(annotations))
            return {"status": "completed", "usage": {"input_tokens": 12}}

        driver._run_codex = AsyncMock(side_effect=model)
        result = await driver.interpret("Inspect the speed task", 120)
        assert result["status"] == "completed"
        saved = json.loads(driver.extract_environment.files[SCRATCH + "/extract_draft-annotations.json"])
        assert saved == annotations
        bundle = assemble_annotations(saved, packet, root)
        assert bundle["assembly"]["usable"]

        async def runner(command, seconds):
            assert "run-probes" in command
            assert SCRATCH + "/probes/speed.py" not in driver.extract_environment.files
            assert json.loads(driver.extract_environment.files[SCRATCH + "/probe-round-1-specs.json"])["probes"] == bundle["probes"]
            assert "probe-round-1-results.json" in command
            return {"results": [{"id": "p_speed", "status": "completed"}]}

        driver._helper = AsyncMock(side_effect=runner)
        assert await driver.probe(bundle["probes"], 45) == [{"id": "p_speed", "status": "completed"}]
        assert (driver.logs_dir / "probe-round-1-results.json").is_file()
        driver._run_codex.assert_awaited_once()
    asyncio.run(check())


def test_adapter_keeps_separate_draft_and_revision_probe_receipts(driver):
    async def check():
        driver._helper = AsyncMock(side_effect=[{"results": [{"id": "p", "status": "failed"}]},
                                               {"results": [{"id": "p", "status": "completed"}]}])
        for source in ("print('draft')\n", "print('revision')\n"):
            await driver.probe([{"id": "p", "source": source, "script": "p.py"}], 45)
        first = json.loads(driver.extract_environment.files[SCRATCH + "/probe-round-1-specs.json"])
        second = json.loads(driver.extract_environment.files[SCRATCH + "/probe-round-2-specs.json"])
        assert first["probes"][0]["source"] == "print('draft')\n"
        assert second["probes"][0]["source"] == "print('revision')\n"
        assert json.loads((driver.logs_dir / "probe-round-1-results.json").read_text())["results"][0]["status"] == "failed"
        assert json.loads((driver.logs_dir / "probe-round-2-results.json").read_text())["results"][0]["status"] == "completed"
    asyncio.run(check())


def test_object_mode_uses_scientific_reader_and_object_assembly(driver):
    async def check():
        driver.extraction_mode = "scientific_objects"
        driver.prepare = ScientificCodex.prepare.__get__(driver)
        driver._helper = AsyncMock(return_value={"status": "ready"})
        await driver.prepare(30)
        command = driver._helper.await_args.args[0]
        assert "--objects-output" in command and "--enrichment-input" in command
        async def model(name, prompt, seconds):
            assert "scientific working model" in prompt
            assert "scientific-context-input.json" in prompt
            assert "object-enrichment.schema.json" in prompt
            assert "Do not repair code or design tests" in prompt
            (driver.logs_dir / "extract_draft-final.txt").write_text(json.dumps({
                "schema_version": "object-enrichment-1.0", "annotations": []}))
            return {"status": "completed", "usage": {"input_tokens": 1}}
        driver._run_codex = AsyncMock(side_effect=model)
        await driver.interpret("Scientific task", 120)
        driver._helper = AsyncMock(return_value={"usable": True})
        await driver.assemble(None, 50)
        assert "assemble-objects" in driver._helper.await_args.args[0]
        assert "scientific-context-input.json" in driver._helper.await_args.args[0]
    asyncio.run(check())


def test_analysis_helper_does_not_use_candidate_directory_for_dependency_imports(driver):
    driver.checked = AsyncMock(return_value='{"status":"ready"}')
    result = asyncio.run(ScientificCodex._helper(driver, "python -m scicontext.tool_cli packet", 30))
    assert result["status"] == "ready"
    assert driver.checked.await_args.kwargs["cwd"] == REMOTE


@pytest.mark.parametrize("output", [None, "not JSON", "[]"])
def test_missing_or_malformed_final_output_falls_back_without_retry(driver, output):
    async def check():
        async def model(*args):
            if output is not None:
                (driver.logs_dir / "extract_draft-final.txt").write_text(output)
            return {"status": "completed", "usage": {"input_tokens": 12}}
        driver._run_codex = AsyncMock(side_effect=model)
        driver.prepare = AsyncMock(return_value={"status": "ready"})
        driver.assemble = AsyncMock(return_value={"status": "no_valid_annotations", "usable": False})
        driver.probe = AsyncMock()
        result = await run_extraction(driver, "task", 1)
        assert not result["usable_checkpoint"]
        assert result["pipeline_status"] == "no_valid_annotations"
        assert result["usage"]["input_tokens"] == 12
        receipt = json.loads((driver.logs_dir / "extract_draft-process.json").read_text())
        assert receipt["annotations_status"] == "no_valid_annotations"
        assert SCRATCH + "/extract_draft-annotations.json" not in driver.extract_environment.files
        driver._run_codex.assert_awaited_once()
        driver.probe.assert_not_awaited()
    asyncio.run(check())


@pytest.mark.parametrize("task_id,usable,accepted", [("058", True, True), ("091", True, False), ("058", False, False)])
def test_collect_graph_keeps_task_and_usable_checks_without_git_guard(driver, task_id, usable, accepted):
    bundle = {"graph": {"task_id": task_id}, "assembly": {"usable": usable}}
    driver._selected_remote = "/compiled.json"
    driver.extract_environment.files[driver._selected_remote] = json.dumps(bundle)
    result = asyncio.run(driver.collect_graph(10))
    assert (result is not None) is accepted
    assert driver.extract_environment.commands == []
    assert not (driver.logs_dir / "extraction-source-check.json").exists()


def test_assembly_paths_are_unique_and_invalid_revision_keeps_observed_bundle(driver):
    async def check():
        driver._annotations_remote = SCRATCH + "/extract_draft-annotations.json"
        driver._helper = AsyncMock(side_effect=[{"usable": True}, {"usable": True}, {"usable": False}])
        await driver.assemble(None, 50)
        initial = driver._selected_remote
        observations = [{"id": "p1", "status": "failed", "fingerprint": "a" * 64}]
        await driver.assemble(observations, 50)
        observed = driver._selected_remote
        driver._annotations_remote = SCRATCH + "/extract_revision-annotations.json"
        await driver.assemble(observations, 50)
        assert initial != observed == driver._selected_remote
        assert len(list(driver.logs_dir.glob("assembly-*.json"))) == 3
        commands = [c.args[0] for c in driver._helper.await_args_list]
        assert "assembly-1.json" in commands[0] and "assembly-2.json" in commands[1]
        assert "extract_revision-annotations.json" in commands[2] and "assembly-3.json" in commands[2]
        assert json.loads(driver.extract_environment.files[SCRATCH + "/assembly-2-probe-results.json"])["results"] == observations
    asyncio.run(check())


def test_revision_uses_exact_draft_feedback_and_does_not_replace_annotations_on_timeout(driver, tmp_path):
    async def check():
        (tmp_path / "prompts").mkdir()
        (tmp_path / "prompts/extract_revision.md").write_text("{instruction}\n{feedback}\n{seconds}")
        driver.workspace = tmp_path
        driver.revise = ScientificCodex.revise.__get__(driver)
        draft_text = '{"claims": [], "unresolved": ["unknown meaning"]}'
        (driver.logs_dir / "extract_draft-final.txt").write_text(draft_text)
        driver._annotations_remote = SCRATCH + "/extract_draft-annotations.json"
        async def model(stage, prompt, seconds):
            assert stage == "extract_revision"
            feedback = json.loads(prompt.splitlines()[1])
            assert feedback["draft_annotations_text"] == draft_text
            assert feedback["public_probe_results"] == [{"status": "failed"}]
            (driver.logs_dir / "extract_revision-final.txt").write_text('{"claims": []}')
            return {"status": "timeout", "usage": {"input_tokens": 9}}
        driver._run_codex = AsyncMock(side_effect=model)
        result = await driver.revise("task", {"public_probe_results": [{"status": "failed"}]}, 30)
        assert result["status"] == "timeout"
        assert driver._annotations_remote.endswith("extract_draft-annotations.json")
        assert (driver.logs_dir / "extract_draft-final.txt").read_text() == draft_text
        assert (driver.logs_dir / "revision-feedback.json").is_file()
    asyncio.run(check())


def test_feedback_removes_duplicate_source_but_keeps_binding_diagnostics(tmp_path):
    draft = tmp_path / "draft.txt"
    draft.write_text('{"probes": [{"source": "print(42)"}]}')
    summary = {"probes": [{"id": "p1", "source": "print(42)", "fingerprint": "a" * 64}],
               "assembly": {"rejected_bindings": [{"id": "q1", "reason": "ambiguous"}]}}
    result = revision_feedback({"draft_assembly": summary, "observed_assembly": summary}, draft)
    assert "source" not in result["draft_assembly"]["probes"][0]
    assert result["draft_assembly"]["assembly"] == summary["assembly"]
    assert result["draft_annotations_text"] == draft.read_text()
    assert result["feedback_omissions"]
    assert "source" in summary["probes"][0]  # Raw summary is untouched.
    with pytest.raises(ValueError, match="correction skipped"):
        revision_feedback({"draft_assembly": {"error": "x" * 140000}}, draft)
