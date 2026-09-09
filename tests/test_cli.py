"""Orchestration failures use synthetic processes and never access credentials."""

from __future__ import annotations

import json
import signal
import subprocess
from dataclasses import asdict
from pathlib import Path

import pytest

from scicontext import cli
from scicontext.controller import TrialConfig
from scicontext.io import digest_file, read_json, write_json


PROVENANCE = {"implementation_revision": "a" * 40, "implementation_dirty": False,
              "uv_lock_sha256": "b" * 64, "prompt_sha256": {"prompts/extract.md": "c" * 64}}


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    root = tmp_path / "workspace"
    root.mkdir()
    config = {"model": "gpt-6-astra", "reasoning_effort": "high", "codex_version": "0.153.4",
              "total_seconds": 1800, "extraction_seconds": 360, "pier_version": "0.3.0",
              "task_ids": ["002", "077"], "conditions": ["baseline", "science"],
              "attempts": 1, "concurrency": 1, "allow_restricted_licenses": False,
              "release_commit": "release", "dataset_revision": "dataset"}
    write_json(root / "config.json", config)
    selected = root / "selection"
    hashes = {}
    for task in config["task_ids"]:
        path = selected / f"task_{task}/task.toml"
        path.parent.mkdir(parents=True)
        path.write_text("# synthetic task\n")
        hashes[path.relative_to(selected).as_posix()] = digest_file(path)
    receipt = {"release_commit": "release", "dataset_revision": "dataset",
               "selection_sha256": "d" * 64, "selection_path": str(selected), "file_hashes": hashes,
               "tasks": [{"task_id": task, "environment_image": f"env-{task}@sha256:00",
                          "verifier_image": f"verifier-{task}@sha256:00"} for task in config["task_ids"]]}
    write_json(root / "data/release-receipt.json", receipt)
    write_json(root / "synthetic-auth.json", {"tokens": {"synthetic": "not-a-credential"}})
    monkeypatch.setattr(cli, "_implementation_provenance", lambda _: dict(PROVENANCE))
    return root


def run_pilot(root, *, smoke=False):
    return cli.pilot(root, root / "config.json", root / "output", True, root / "synthetic-auth.json", smoke)


def fake_agent_record(command, *, status="completed"):
    kwargs = dict(arg.split("=", 1) for arg in command if "=" in arg)
    name = command[command.index("--job-name") + 1]
    task = name.split("-")[1]
    path = Path(command[command.index("--jobs-dir") + 1]) / name / "synthetic-trial"
    config = TrialConfig(total_seconds=float(kwargs["total_seconds"]), extraction_seconds=float(kwargs["extraction_seconds"]))
    write_json(path / "run.json", {
        "schema_version": "1.0", "task_id": task, "condition": kwargs["condition"],
        "model": config.model, "reasoning_effort": config.reasoning_effort,
        "codex_version": config.codex_version, "config": asdict(config),
        "status": status, "stages": [], "environment_image": f"env-{task}@sha256:00",
    })
    if status == "completed":
        write_json(path / "verifier/reward.json", {"reward": 1,
                   "private": {"passed": 2, "collected": 2, "return_code": 0}})
    return path


def test_pull_failure_retains_attempt_and_unstarted_schedule(workspace, monkeypatch):
    calls = []
    def fail(command, **kwargs):
        calls.append(command)
        raise subprocess.CalledProcessError(3, command)
    monkeypatch.setattr(cli, "_run_owned_process", fail)
    with pytest.raises(subprocess.CalledProcessError):
        run_pilot(workspace)
    output = workspace / "output"
    schedule = read_json(output / "schedule.json")
    assert schedule["status"] == "runner_failure"
    assert [item["status"] for item in schedule["schedule"]] == ["infrastructure_failure", "not_run", "not_run", "not_run"]
    assert schedule["schedule"][0]["phase"] == "pulling_images"
    assert schedule["finished_at"] and len(calls) == 1
    row = read_json(output / "jobs/task-002-baseline/setup-failure/run.json")
    assert row["config"] == asdict(TrialConfig())
    assert row["environment_image"] == "env-002@sha256:00"
    assert all(row[key] == value for key, value in PROVENANCE.items())
    summary = read_json(output / "summary/summary.json")
    assert len(summary["trials"]) == 1
    assert summary["trials"][0]["exact_private_success"] is None
    assert read_json(output / "task-002-baseline-receipt.json")["return_code"] == 3


def test_success_and_setup_failure_still_make_comparable_unknown_pair(workspace, monkeypatch):
    pier_calls = []
    def execute(command, **kwargs):
        if command[0] != "docker":
            pier_calls.append(command)
            if len(pier_calls) == 1:
                fake_agent_record(command)
        return subprocess.CompletedProcess(command, 0)
    monkeypatch.setattr(cli, "_run_owned_process", execute)
    with pytest.raises(RuntimeError, match="Runner failed"):
        run_pilot(workspace)
    output = workspace / "output"
    summary = read_json(output / "summary/summary.json")
    assert len(summary["trials"]) == 2
    assert summary["pairs"][0]["outcome"] == "unknown"
    schedule = read_json(output / "schedule.json")
    assert "summary_error" not in schedule
    assert [item["status"] for item in schedule["schedule"]] == ["completed", "infrastructure_failure", "not_run", "not_run"]
    assert len(pier_calls) == 2
    left, right = summary["trials"]
    assert left["config"] == right["config"]
    assert left["provenance"] == right["provenance"]


@pytest.mark.parametrize("termination_signal", [False, True])
def test_interrupt_stops_only_owned_group_before_private_auth_cleanup(workspace, monkeypatch, termination_signal):
    signals, auth_paths, waits = [], [], []
    previous_handler = signal.getsignal(signal.SIGTERM)
    class SyntheticProcess:
        pid = 314159
        def __init__(self, command, **kwargs):
            assert kwargs["start_new_session"] is True
            self.is_pier = command[0] != "docker"
            self.first = True
            if self.is_pier:
                auth_paths.append(Path(next(arg.split("=", 1)[1] for arg in command if arg.startswith("auth_file="))))
                assert auth_paths[-1].is_file()
        def wait(self, timeout=None):
            if not self.is_pier:
                return 0
            waits.append(timeout)
            assert auth_paths[-1].is_file(), "Auth must remain available until owned runner has stopped"
            if self.first:
                self.first = False
                if termination_signal:
                    signal.getsignal(signal.SIGTERM)(signal.SIGTERM, None)
                raise KeyboardInterrupt()
            return -15
    def kill(pid, sig):
        assert auth_paths[-1].is_file()
        signals.append((pid, sig))
    monkeypatch.setattr(cli.subprocess, "Popen", SyntheticProcess)
    monkeypatch.setattr(cli.os, "killpg", kill)
    with pytest.raises(KeyboardInterrupt):
        run_pilot(workspace)
    assert signals == [(314159, signal.SIGTERM), (314159, signal.SIGKILL)]
    assert waits == [None, 5, 5]
    assert not auth_paths[-1].exists()
    assert signal.getsignal(signal.SIGTERM) == previous_handler
    output = workspace / "output"
    schedule = read_json(output / "schedule.json")
    assert schedule["status"] == "interrupted"
    assert [item["status"] for item in schedule["schedule"]] == ["interrupted", "not_run", "not_run", "not_run"]
    assert read_json(output / "summary/summary.json")["trials"][0]["status"] == "interrupted"
    assert "not-a-credential" not in json.dumps(schedule)
    launch = read_json(output / "task-002-baseline-launch.json")
    assert "auth_file=<private>" in launch["command"]
    assert str(auth_paths[-1]) not in json.dumps(launch)


def test_interrupt_finalizes_running_agent_record(workspace, monkeypatch):
    def execute(command, **kwargs):
        if command[0] == "docker":
            return subprocess.CompletedProcess(command, 0)
        fake_agent_record(command, status="running")
        raise KeyboardInterrupt()
    monkeypatch.setattr(cli, "_run_owned_process", execute)
    with pytest.raises(KeyboardInterrupt):
        run_pilot(workspace)
    output = workspace / "output"
    records = list((output / "jobs").rglob("run.json"))
    assert len(records) == 1
    record = read_json(records[0])
    assert record["status"] == record["orchestration_status"] == "interrupted"
    assert record["finished_at"]


def test_preparation_error_is_preserved_without_launch(workspace, monkeypatch):
    def fail(*args, **kwargs):
        raise OSError("synthetic copy failure")
    monkeypatch.setattr(cli.shutil, "copytree", fail)
    monkeypatch.setattr(cli, "_run_owned_process", lambda *a, **k: pytest.fail("No process should launch"))
    with pytest.raises(OSError, match="copy failure"):
        run_pilot(workspace)
    schedule = read_json(workspace / "output/schedule.json")
    assert schedule["status"] == "runner_failure"
    assert schedule["schedule"][0]["phase"] == "preparing"
    assert len(read_json(workspace / "output/summary/summary.json")["trials"]) == 1


def test_successful_smoke_preserves_actual_budget_and_provenance(workspace, monkeypatch):
    def execute(command, **kwargs):
        if command[0] != "docker":
            fake_agent_record(command)
        return subprocess.CompletedProcess(command, 0)
    monkeypatch.setattr(cli, "_run_owned_process", execute)
    summary = run_pilot(workspace, smoke=True)
    row = summary["trials"][0]
    assert row["config"]["total_seconds"] == 60
    assert row["config"]["extraction_seconds"] == 10
    schedule = read_json(workspace / "output/schedule.json")
    assert schedule["status"] == "completed"
    assert schedule["schedule"][0]["status"] == "completed"
    assert schedule["schedule"][0]["phase"] == "finished"
    assert all(schedule[key] == value for key, value in PROVENANCE.items())


def test_reconciliation_never_rewrites_scientific_scratch_named_run_json(workspace):
    output = workspace / "output"
    command = ["pier", "--jobs-dir", str(output / "jobs"), "--job-name", "task-002-baseline",
               "condition=baseline", "total_seconds=1800", "extraction_seconds=360"]
    directory = fake_agent_record(command)
    scratch = directory / "agent/extract-scratch/run.json"
    write_json(scratch, {"scientific_measurement": 42})
    item = {"task_id": "002", "condition": "baseline", "started_at": "synthetic", "phase": "pier"}
    config = read_json(workspace / "config.json")
    task_row = read_json(workspace / "data/release-receipt.json")["tasks"][0]
    plan = {"selection_sha256": "d" * 64, "config_sha256": "e" * 64, "kind": "development_pilot", **PROVENANCE}
    assert cli._reconcile_trial(output, item, TrialConfig(), task_row, config, plan, 0) == "completed"
    assert read_json(scratch) == {"scientific_measurement": 42}


def test_provenance_is_shared_prompt_bundle_not_stage_input(tmp_path, monkeypatch):
    (tmp_path / "prompts").mkdir()
    (tmp_path / "prompts/extract.md").write_text("extract")
    (tmp_path / "prompts/repair.md").write_text("repair")
    (tmp_path / "uv.lock").write_text("lock")
    calls = []
    def git(command, **kwargs):
        calls.append(command)
        value = "abc123\n" if command[1] == "rev-parse" else " M src/scicontext/cli.py\n"
        return subprocess.CompletedProcess(command, 0, stdout=value)
    monkeypatch.setattr(cli.subprocess, "run", git)
    result = cli._implementation_provenance(tmp_path)
    assert result["implementation_revision"] == "abc123"
    assert result["implementation_dirty"] is True
    assert result["uv_lock_sha256"] == digest_file(tmp_path / "uv.lock")
    assert set(result["prompt_sha256"]) == {"prompts/extract.md", "prompts/repair.md"}
    assert "--untracked-files=no" in calls[-1]
