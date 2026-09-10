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
from scicontext.pier_agent import SCRATCH, ScientificCodex


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
    for name in ("_put", "checked", "interpret", "probe", "collect_graph"):
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
            assert stage == "extract"
            assert "do not edit task source or write annotation/probe files" in prompt
            assert "ONLY the compact annotation JSON object" in prompt
            (driver.logs_dir / "extract-final.txt").write_text(json.dumps(annotations))
            return {"status": "completed", "usage": {"input_tokens": 12}}

        driver._run_codex = AsyncMock(side_effect=model)
        result = await driver.interpret("Inspect the speed task", 120)
        assert result["status"] == "completed"
        saved = json.loads(driver.extract_environment.files[SCRATCH + "/annotations.json"])
        assert saved == annotations
        bundle = assemble_annotations(saved, packet, root)
        assert bundle["assembly"]["usable"]

        async def runner(command, seconds):
            assert "run-probes" in command
            assert driver.extract_environment.files[SCRATCH + "/probes/speed.py"] == "print(2 / 1)\n"
            assert json.loads(driver.extract_environment.files[SCRATCH + "/probe-specs.json"])["probes"] == bundle["probes"]
            return {"results": [{"id": "p_speed", "status": "completed"}]}

        driver._helper = AsyncMock(side_effect=runner)
        assert await driver.probe(bundle["probes"], 45) == [{"id": "p_speed", "status": "completed"}]
        driver._run_codex.assert_awaited_once()
    asyncio.run(check())


@pytest.mark.parametrize("output", [None, "not JSON", "[]"])
def test_missing_or_malformed_final_output_falls_back_without_retry(driver, output):
    async def check():
        async def model(*args):
            if output is not None:
                (driver.logs_dir / "extract-final.txt").write_text(output)
            return {"status": "completed", "usage": {"input_tokens": 12}}
        driver._run_codex = AsyncMock(side_effect=model)
        driver.prepare = AsyncMock(return_value={"status": "ready"})
        driver.assemble = AsyncMock(return_value={"status": "no_valid_annotations", "usable": False})
        driver.probe = AsyncMock()
        result = await run_extraction(driver, "task", 1)
        assert not result["usable_checkpoint"]
        assert result["pipeline_status"] == "no_valid_annotations"
        assert result["usage"]["input_tokens"] == 12
        receipt = json.loads((driver.logs_dir / "extract-process.json").read_text())
        assert receipt["annotations_status"] == "no_valid_annotations"
        assert SCRATCH + "/annotations.json" not in driver.extract_environment.files
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
