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
              "uv_lock_sha256": "b" * 64, "prompt_sha256": {"prompts/enrich_objects.md": "c" * 64}}


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
    (root / "src/scicontext").mkdir(parents=True)
    (root / "src/scicontext/__init__.py").write_text("# synthetic method source\n")
    (root / "prompts").mkdir()
    prompts = {"enrich_objects.md": "enrich", "repair.md": "repair"}
    for name, text in prompts.items():
        (root / "prompts" / name).write_text(text)
    provenance = {"implementation_revision": "a" * 40, "implementation_dirty": False,
                  "uv_lock_sha256": "b" * 64,
                  "prompt_sha256": {f"prompts/{name}": digest_file(root / "prompts" / name)
                                    for name in prompts}}
    monkeypatch.setattr(cli, "_implementation_provenance", lambda _: dict(provenance))
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
    if status == "completed" and "--disable-verification" not in command:
        write_json(path / "verifier/reward.json", {"reward": 1,
                   "private": {"passed": 2, "collected": 2, "return_code": 0}})
    return path


def test_extract_only_has_no_repair_or_private_verifier(workspace, monkeypatch):
    calls = []
    def execute(command, **kwargs):
        calls.append(command)
        if command[0] != "docker":
            assert "--disable-verification" in command
            assert "condition=science" in command
            assert "extraction_only=true" in command
            fake_agent_record(command)
        return subprocess.CompletedProcess(command, 0)
    monkeypatch.setattr(cli, "_run_owned_process", execute)
    cli.pilot(workspace, workspace / "config.json", workspace / "output", True,
              workspace / "synthetic-auth.json", extraction_only=True)
    assert len(calls) == 4
    assert all("verifier-" not in " ".join(c) for c in calls)
    schedule = read_json(workspace / "output/schedule.json")
    assert schedule["kind"] == "extraction_verification"
    assert [i["condition"] for i in schedule["schedule"]] == ["science", "science"]


def test_deepseek_backoff_extends_only_outer_agent_timeout_for_both_arms(workspace, monkeypatch):
    from scicontext.deepseek_agent import API_RETRY_DELAYS, MAX_LOOP_ITERATIONS
    config = read_json(workspace / "config.json")
    config.update(agent="deepseek", model="deepseek-flash", extractor="interactive_science")
    write_json(workspace / "config.json", config)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "synthetic-not-a-credential")
    calls = []

    def execute(command, **kwargs):
        if command[0] != "docker":
            calls.append(command)
            fake_agent_record(command)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(cli, "_run_owned_process", execute)
    run_pilot(workspace)
    assert len(calls) == 4
    expected = 1800 + MAX_LOOP_ITERATIONS * sum(API_RETRY_DELAYS) + 20
    for command in calls:
        multiplier = float(command[command.index("--agent-timeout-multiplier") + 1])
        assert multiplier * 5400 == pytest.approx(expected)
        assert "total_seconds=1800" in command
        assert "--timeout-multiplier" not in command
        assert "--verifier-timeout-multiplier" not in command
    policy = read_json(workspace / "output/schedule.json")["execution_policy"]
    assert policy["agent_work_budget_seconds"] == 1800
    assert policy["provider_retries"]["charge_backoff_to_work_budget"] is False


def test_glm_reuses_same_agent_with_selected_private_opencode_key(workspace, monkeypatch):
    credential = workspace / "opencode-auth.json"
    write_json(credential, {"zai-coding-plan": {"type": "api", "key": "synthetic-plan-key"},
                            "zai": {"type": "api", "key": "must-not-use-general-key"}})
    config = read_json(workspace / "config.json")
    config.update(agent="glm", model="glm-5.3-flash", reasoning_effort="low",
                  extractor="interactive_science", opencode_auth_file=str(credential))
    write_json(workspace / "config.json", config)
    calls = []

    def execute(command, **kwargs):
        if command[0] != "docker":
            calls.append(command)
            assert "scicontext.deepseek_agent:DeepSeekAgent" in command
            assert "api_provider=zai-coding-plan" in command
            assert "reasoning_effort=low" in command
            key_path = Path(next(arg.split("=", 1)[1] for arg in command if arg.startswith("deepseek_key_file=")))
            assert read_json(key_path) == {"api_key": "synthetic-plan-key"}
            assert key_path.stat().st_mode & 0o777 == 0o600
            assert all("synthetic-plan-key" not in arg for arg in command)
            fake_agent_record(command)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(cli, "_run_owned_process", execute)
    run_pilot(workspace)
    assert len(calls) == 4
    assert not any("opencode" in command[0] for command in calls)
    for path in (workspace / "output").rglob("*.json"):
        assert "synthetic-plan-key" not in path.read_text()


def test_explicit_receipt_and_condition_order_support_new_cohort(workspace):
    config = read_json(workspace / "config.json")
    receipt = read_json(workspace / "data/release-receipt.json")
    receipt["tasks"].append({"task_id": "091", "environment_image": "env", "verifier_image": "verifier", "restricted_license": "False"})
    write_json(workspace / "data/other-receipt.json", receipt)
    config.update(task_ids=["091"], release_receipt="data/other-receipt.json",
                  study_kind="random_five_comparison", condition_order={"091": ["baseline", "science"]})
    write_json(workspace / "other-config.json", config)
    plan = cli.pilot(workspace, workspace / "other-config.json", workspace / "new-output", False, None)
    assert plan["kind"] == "random_five_comparison"
    assert [(x["task_id"], x["condition"]) for x in plan["schedule"]] == [("091", "baseline"), ("091", "science")]


def test_bounded_cohort_refuses_duplicate_or_unmaterialized_tasks(workspace):
    config = read_json(workspace / "config.json")
    for ids in (["002", "002"], ["001", "002", "003", "004", "005", "006"], ["091"]):
        config["task_ids"] = ids
        write_json(workspace / "bad-config.json", config)
        with pytest.raises(ValueError):
            cli.pilot(workspace, workspace / "bad-config.json", workspace / "new-output", False, None)


def test_pull_failure_retains_each_attempt_and_continues(workspace, monkeypatch):
    calls = []
    def fail(command, **kwargs):
        calls.append(command)
        raise subprocess.CalledProcessError(3, command)
    monkeypatch.setattr(cli, "_run_owned_process", fail)
    run_pilot(workspace)
    output = workspace / "output"
    schedule = read_json(output / "schedule.json")
    assert schedule["status"] == "completed_with_failures"
    assert [item["status"] for item in schedule["schedule"]] == ["infrastructure_failure"] * 4
    assert schedule["schedule"][0]["phase"] == "pulling_images"
    assert schedule["finished_at"] and len(calls) == 4
    row = read_json(output / "jobs/task-002-baseline/setup-failure/run.json")
    assert row["config"] == asdict(TrialConfig())
    assert row["environment_image"] == "env-002@sha256:00"
    provenance = cli._implementation_provenance(workspace)
    assert all(row[key] == provenance[key] for key in PROVENANCE)
    summary = read_json(output / "summary/summary.json")
    assert len(summary["trials"]) == 4
    assert summary["trials"][0]["exact_private_success"] is None
    assert read_json(output / "task-002-baseline-receipt.json")["return_code"] == 3


def test_launch_does_not_prune_unrelated_docker_resources(workspace, monkeypatch):
    original_run = subprocess.run
    def checked_run(command, **kwargs):
        assert not (command[:1] == ["docker"] and "prune" in command)
        return original_run(command, **kwargs)
    monkeypatch.setattr(subprocess, "run", checked_run)
    def fail_pull(command, **kwargs):
        raise subprocess.CalledProcessError(3, command)
    monkeypatch.setattr(cli, "_run_owned_process", fail_pull)
    run_pilot(workspace)


def test_success_and_setup_failure_still_make_comparable_unknown_pair(workspace, monkeypatch):
    pier_calls = []
    def execute(command, **kwargs):
        if command[0] != "docker":
            pier_calls.append(command)
            if len(pier_calls) == 1:
                fake_agent_record(command)
        return subprocess.CompletedProcess(command, 0)
    monkeypatch.setattr(cli, "_run_owned_process", execute)
    run_pilot(workspace)
    output = workspace / "output"
    summary = read_json(output / "summary/summary.json")
    assert len(summary["trials"]) == 4
    assert summary["pairs"][0]["outcome"] == "unknown"
    schedule = read_json(output / "schedule.json")
    assert "summary_error" not in schedule
    assert [item["status"] for item in schedule["schedule"]] == ["completed", "infrastructure_failure", "infrastructure_failure", "infrastructure_failure"]
    assert len(pier_calls) == 4
    left, right = summary["trials"][:2]
    assert left["config"] == right["config"]
    assert left["provenance"] == right["provenance"]


@pytest.mark.parametrize("termination_signal", [False, True])
def test_interrupt_stops_only_owned_group_before_private_auth_cleanup(workspace, monkeypatch, termination_signal):
    signals, auth_paths, waits = [], [], []
    container_cleanup_seen = []
    previous_handler = signal.getsignal(signal.SIGTERM)
    original_cleanup = cli._cleanup_owned_containers
    def cleanup_containers(output, item):
        assert auth_paths[-1].is_file()
        assert len(waits) == 3 and waits[0] is None and 0 <= waits[1] <= 5 and waits[2] == 5
        container_cleanup_seen.append(True)
        return original_cleanup(output, item)
    class SyntheticProcess:
        pid = 314159
        def __init__(self, command, **kwargs):
            self.is_prune = command[0] == "docker" and command[1:2] in (["network"], ["container"])
            if self.is_prune:
                self.is_pier = False
                self.first = False
                return
            assert kwargs["start_new_session"] is True
            self.is_pier = command[0] != "docker"
            self.first = True
            if self.is_pier:
                auth_paths.append(Path(next(arg.split("=", 1)[1] for arg in command if arg.startswith("auth_file="))))
                assert auth_paths[-1].is_file()
        def communicate(self, input=None, timeout=None):
            return (b"", b"")

        def kill(self):
            pass

        def poll(self):
            return 0

        args: list = []

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

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
    monkeypatch.setattr(cli, "_cleanup_owned_containers", cleanup_containers)
    with pytest.raises(KeyboardInterrupt):
        run_pilot(workspace)
    assert signals == [(314159, signal.SIGTERM), (314159, signal.SIGKILL)]
    assert len(waits) == 3 and waits[0] is None and 0 <= waits[1] <= 5 and waits[2] == 5
    assert not auth_paths[-1].exists()
    assert container_cleanup_seen == [True]
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
    calls = {"count": 0}
    real_copytree = cli.shutil.copytree

    def fail(*args, **kwargs):
        # The frozen-source snapshot (2 copytree calls) must succeed; the task
        # materialization copy fails.
        calls["count"] += 1
        if calls["count"] > 2:
            raise OSError("synthetic copy failure")
        return real_copytree(*args, **kwargs)
    monkeypatch.setattr(cli.shutil, "copytree", fail)
    monkeypatch.setattr(cli, "_run_owned_process", lambda *a, **k: pytest.fail("No process should launch"))
    run_pilot(workspace)
    schedule = read_json(workspace / "output/schedule.json")
    assert schedule["status"] == "completed_with_failures"
    assert schedule["schedule"][0]["phase"] == "preparing"
    assert len(read_json(workspace / "output/summary/summary.json")["trials"]) == 4


def test_successful_smoke_preserves_actual_budget_and_provenance(workspace, monkeypatch):
    def execute(command, **kwargs):
        if command[0] != "docker":
            fake_agent_record(command)
        return subprocess.CompletedProcess(command, 0)
    monkeypatch.setattr(cli, "_run_owned_process", execute)
    monkeypatch.setattr(cli, "_cleanup_owned_containers", lambda *a: pytest.fail("Completed schedules must not stop retained containers"))
    summary = run_pilot(workspace, smoke=True)
    row = summary["trials"][0]
    assert row["config"]["total_seconds"] == 60
    assert row["config"]["extraction_seconds"] == 10
    schedule = read_json(workspace / "output/schedule.json")
    assert schedule["status"] == "completed"
    assert schedule["schedule"][0]["status"] == "completed"
    assert schedule["schedule"][0]["phase"] == "finished"
    provenance = cli._implementation_provenance(workspace)
    assert all(schedule[key] == provenance[key] for key in PROVENANCE)
    assert schedule["frozen_source"]["dir"].endswith("/frozen-source")
    assert "prompts/enrich_objects.md" in schedule["frozen_source"]["file_hashes"]


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
    (tmp_path / "prompts/enrich_objects.md").write_text("enrich")
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
    assert set(result["prompt_sha256"]) == {"prompts/enrich_objects.md", "prompts/repair.md"}
    assert "--untracked-files=no" in calls[-1]


class SyntheticDocker:
    """Docker metadata only; never invokes the daemon or exposes environment."""
    def __init__(self, records):
        self.records = records
        self.listings = {}
        for identity, record in records.items():
            self.listings.setdefault(record["project"], []).append(identity)
        self.calls = []
        self.stop_failure = False
        self.ignore_kill = False
        self.fail_query = None

    def __call__(self, command, **kwargs):
        self.calls.append(command)
        assert command[0] == "docker"
        assert 0 < kwargs["timeout"] <= 10
        operation = command[1]
        if operation == "ps":
            assert command[2:5] == ["--quiet", "--no-trunc", "--filter"]
            project = command[-1].split("=", 2)[-1]
            if project == self.fail_query:
                raise subprocess.CalledProcessError(1, command)
            output = "\n".join(identity for identity in self.listings.get(project, []) if self.records[identity]["running"])
        elif operation == "inspect":
            assert ".Config.Env" not in command[3]
            output = json.dumps(self.records[command[-1]])
        elif operation in {"stop", "kill"}:
            assert command[2:4] == (["--time", "5"] if operation == "stop" else ["--signal", "KILL"])
            if operation == "stop" and self.stop_failure:
                raise subprocess.CalledProcessError(1, command)
            for identity in command[4:]:
                assert identity in self.records and len(identity) == 64
                if operation == "stop" or not self.ignore_kill:
                    self.records[identity]["running"] = False
            output = "\n".join(command[4:])
        else:
            pytest.fail(f"Unscoped/unexpected Docker operation: {operation}")
        return subprocess.CompletedProcess(command, 0, stdout=output)


def container_fixture(workspace, *, all_roles=False):
    output = workspace / "output"
    condition = "science" if all_roles else "baseline"
    item = {"task_id": "002", "condition": condition}
    job = output / "jobs" / f"task-002-{condition}"
    trial = job / "task_002__AbC123"
    task = output / "inputs" / f"task-002-{condition}" / "task_002"
    write_json(trial / "config.json", {"trial_name": trial.name, "trials_dir": str(job), "task": {"path": str(task)}})
    write_json(trial / "docker-compose-mounts.json", {"services": {}})
    write_json(trial / "extraction_environment/docker-compose-mounts.json", {"services": {}})
    project = trial.name.lower()
    records = {"a" * 64: {"id": "a" * 64, "running": True, "project": project,
               "working_dir": str(task / "environment"), "config_files": str(trial / "docker-compose-mounts.json")}}
    if all_roles:
        records["b" * 64] = {**records["a" * 64], "id": "b" * 64}
        records["c" * 64] = {**records["a" * 64], "id": "c" * 64, "project": project + "-extract",
                              "config_files": str(trial / "extraction_environment/docker-compose-mounts.json")}
        records["d" * 64] = {**records["a" * 64], "id": "d" * 64, "project": project + "__verifier__trial",
                              "working_dir": str(task / "tests")}
    return output, item, trial, SyntheticDocker(records)


def test_container_cleanup_stops_exact_proven_roles_but_no_prefix_neighbors(workspace, monkeypatch):
    output, item, trial, docker = container_fixture(workspace, all_roles=True)
    unrelated = "e" * 64
    docker.records[unrelated] = {"id": unrelated, "running": True, "project": trial.name.lower() + "-unrelated"}
    docker.listings[docker.records[unrelated]["project"]] = [unrelated]
    monkeypatch.setattr(cli.subprocess, "run", docker)
    result = cli._cleanup_owned_containers(output, item)
    assert result["status"] == "complete"
    assert all(entry["ownership_verified"] and entry["stopped"] for entry in result["containers"])
    assert len(result["containers"]) == 4
    assert docker.records[unrelated]["running"] is True
    stop = next(command for command in docker.calls if command[1] == "stop")
    assert set(stop[4:]) == {char * 64 for char in "abcd"}
    assert all(command[1] not in {"rm", "compose"} for command in docker.calls)
    assert (trial / "config.json").exists()
    assert read_json(output / "task-002-science-container-cleanup.json")["status"] == "complete"


@pytest.mark.parametrize("field,value", [
    ("project", "other-project"),
    ("working_dir", "/unrelated/environment"),
    ("config_files", "/unrelated/docker-compose-mounts.json"),
    ("config_files", None),
])
def test_container_cleanup_refuses_mismatching_ownership(workspace, monkeypatch, field, value):
    output, item, trial, docker = container_fixture(workspace)
    docker.records["a" * 64][field] = value
    monkeypatch.setattr(cli.subprocess, "run", docker)
    result = cli._cleanup_owned_containers(output, item)
    assert result["status"] == "incomplete" and result["errors"]
    assert docker.records["a" * 64]["running"] is True
    assert not any(command[1] in {"stop", "kill"} for command in docker.calls)


def test_container_cleanup_refuses_foreign_task_receipt_before_querying(workspace, monkeypatch):
    output, item, trial, docker = container_fixture(workspace)
    config = read_json(trial / "config.json")
    config["task"]["path"] = str(workspace / "another-job")
    write_json(trial / "config.json", config)
    monkeypatch.setattr(cli.subprocess, "run", docker)
    assert cli._cleanup_owned_containers(output, item)["status"] == "incomplete"
    assert docker.calls == []


def test_container_cleanup_refuses_symlinked_mounts_receipt(workspace, monkeypatch):
    output, item, trial, docker = container_fixture(workspace)
    elsewhere = workspace / "other-job/mounts.json"
    write_json(elsewhere, {"services": {}})
    mount = trial / "docker-compose-mounts.json"
    mount.unlink()
    mount.symlink_to(elsewhere)
    monkeypatch.setattr(cli.subprocess, "run", docker)
    assert cli._cleanup_owned_containers(output, item)["status"] == "incomplete"
    assert not any(command[1] in {"stop", "kill"} for command in docker.calls)


def test_container_cleanup_kill_fallback_requires_verified_ids(workspace, monkeypatch):
    output, item, trial, docker = container_fixture(workspace)
    docker.stop_failure = True
    monkeypatch.setattr(cli.subprocess, "run", docker)
    result = cli._cleanup_owned_containers(output, item)
    assert result["status"] == "complete" and result["warnings"]
    kill = next(command for command in docker.calls if command[1] == "kill")
    assert kill[4:] == ["a" * 64]
    assert result["containers"][0]["stopped"] is True


def test_container_cleanup_never_claims_unstopped_container_complete(workspace, monkeypatch):
    output, item, trial, docker = container_fixture(workspace)
    docker.stop_failure = docker.ignore_kill = True
    monkeypatch.setattr(cli.subprocess, "run", docker)
    result = cli._cleanup_owned_containers(output, item)
    assert result["status"] == "incomplete"
    assert result["containers"][0]["stopped"] is False


def test_discovery_failure_still_stops_already_proven_owned_container(workspace, monkeypatch):
    output, item, trial, docker = container_fixture(workspace)
    docker.fail_query = trial.name.lower() + "__verifier__trial"
    monkeypatch.setattr(cli.subprocess, "run", docker)
    result = cli._cleanup_owned_containers(output, item)
    assert result["status"] == "incomplete" and result["errors"]
    assert result["containers"][0]["stopped"] is True


def test_container_cleanup_deadline_is_explicit_and_bounded(workspace, monkeypatch):
    output, item, trial, docker = container_fixture(workspace)
    clock = iter([0.0, 46.0])
    monkeypatch.setattr(cli.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(cli.subprocess, "run", docker)
    result = cli._cleanup_owned_containers(output, item)
    assert result["status"] == "incomplete"
    assert "45-second allowance" in result["errors"][0]
    assert docker.calls == []


def test_head_revision_reads_git_and_tolerates_plain_directories(tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()
    assert cli._head_revision(plain) is None
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "-c", "user.email=t@example.com", "-c", "user.name=t",
                    "commit", "-q", "--allow-empty", "-m", "init"], cwd=repo, check=True)
    revision = cli._head_revision(repo)
    assert revision is not None and len(revision) == 40
