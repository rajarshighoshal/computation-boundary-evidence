"""Bounded admission and cancellation, with no Docker or model calls."""
import json
import signal
import subprocess
import sys
from pathlib import Path

import pytest

from scicontext import cli
from scicontext.io import read_json, write_json
from test_cli import fake_agent_record, workspace  # shared synthetic workspace fixture


class Runners:
    def __init__(self, monkeypatch, *, failure=None, interrupt=False, reward=1, finished_peer=False):
        self.started = []
        self.events = []
        self.signals = []
        self.cleanup = []
        self.failure, self.interrupt, self.reward = failure, interrupt, reward
        self.finished_peer = finished_peer
        monkeypatch.setattr(cli, "_run_owned_process", self.pull)
        monkeypatch.setattr(cli.subprocess, "Popen", self.start)
        monkeypatch.setattr(cli.os, "killpg", self.kill)
        monkeypatch.setattr(cli, "_cleanup_owned_containers", self.clean_containers)

    def pull(self, command, **kwargs):
        assert command[:2] == ["docker", "pull"]
        return subprocess.CompletedProcess(command, 0)

    def start(self, command, **kwargs):
        if command[0] == "docker":
            class PruneDone:
                args = command
                def poll(self):
                    return 0
                def communicate(self, input=None, timeout=None):
                    return (b"", b"")
                def wait(self, timeout=None):
                    return 0
                def __enter__(self):
                    return self
                def __exit__(self, *args):
                    return False
            return PruneDone()
        assert kwargs["start_new_session"]
        assert command[command.index("--n-concurrent") + 1] == "1"
        assert command[command.index("--n-attempts") + 1] == "1"
        assert command[command.index("--max-retries") + 1] == "0"
        assert "UNRELATED_API_KEY" not in kwargs["env"]
        owner = self
        class Process:
            pid = 10000 + len(owner.started)
            name = command[command.index("--job-name") + 1]
            auth = Path(next(arg.split("=", 1)[1] for arg in command if arg.startswith("auth_file=")))
            alive = True
            polls = 0
            def poll(self):
                assert self.auth.is_file()
                self.polls += 1
                if owner.interrupt:
                    signal.getsignal(signal.SIGTERM)(signal.SIGTERM, None)
                if self.polls < 2:
                    return None
                self.alive = False
                owner.events.append(("finish", self.name))
                state = "infrastructure_failure" if owner.failure == "provider" and self.pid == 10000 else "completed"
                path = fake_agent_record(command, status=state)
                if "--disable-verification" not in command:
                    write_json(path / "verifier/reward.json", {"reward": owner.reward})
                return 3 if owner.failure == "runner" and self.pid == 10000 else 0
            def wait(self, timeout=None):
                assert self.auth.is_file(), "Authentication must outlive all owned processes"
                self.alive = False
                return -15
        process = Process()
        assert process.auth.is_file()
        kwargs["stdout"].write(process.name + " raw runner log\n")
        fake_agent_record(command, status="running")
        self.started.append(process)
        self.events.append(("start", process.name))
        assert sum(p.alive for p in self.started) <= 2
        return process

    def kill(self, pid, sig):
        assert all(p.auth.is_file() for p in self.started)
        assert pid in {p.pid for p in self.started}
        self.signals.append((pid, sig))

    def clean_containers(self, output, item):
        assert all(p.auth.is_file() for p in self.started)
        assert all(not p.alive for p in self.started if p.name == f"task-{item['task_id']}-{item['condition']}")
        self.cleanup.append((item["task_id"], item["condition"]))
        return {"status": "complete", "containers": []}


def parallel(root, *, execute=True, extraction_only=False, smoke=False):
    config = read_json(root / "config.json")
    config["concurrency"] = 2
    write_json(root / "parallel.json", config)
    return cli.pilot(root, root / "parallel.json", root / "output", execute,
                     root / "synthetic-auth.json", smoke=smoke, extraction_only=extraction_only)


@pytest.mark.parametrize("reward", [0, 1])
def test_parallel_pairs_overlap_and_drain_before_next_task(workspace, monkeypatch, reward):
    monkeypatch.setenv("UNRELATED_API_KEY", "not-forwarded")
    runners = Runners(monkeypatch, reward=reward)
    summary = parallel(workspace)
    assert runners.events == [
        ("start", "task-002-baseline"), ("start", "task-002-science"),
        ("finish", "task-002-baseline"), ("finish", "task-002-science"),
        ("start", "task-077-science"), ("start", "task-077-baseline"),
        ("finish", "task-077-science"), ("finish", "task-077-baseline")]
    assert len(summary["trials"]) == 4
    assert runners.signals == runners.cleanup == []
    output = workspace / "output"
    plan = read_json(output / "schedule.json")
    assert plan["status"] == "completed"
    assert plan["execution_policy"]["admission"] == "2_attempt_barrier"
    assert all(t["status"] == "completed" for t in plan["schedule"])
    assert len(list((output / "inputs").glob("task-*/task_*"))) == 4
    for process in runners.started:
        assert not process.auth.exists()
        assert (output / f"{process.name}-runner.log").read_text() == process.name + " raw runner log\n"
        launch = read_json(output / f"{process.name}-launch.json")
        assert "auth_file=<private>" in launch["command"]
        assert str(process.auth) not in json.dumps(launch)
    assert "not-a-credential" not in json.dumps(plan)


@pytest.mark.parametrize("failure", ["runner", "provider"])
def test_infrastructure_failure_preserves_peer_and_continues_queue(workspace, monkeypatch, failure):
    runners = Runners(monkeypatch, failure=failure)
    parallel(workspace)
    assert len(runners.started) == len({p.name for p in runners.started}) == 4
    assert runners.signals == []
    assert runners.cleanup == [("002", "baseline")]
    plan = read_json(workspace / "output/schedule.json")
    assert plan["status"] == "completed_with_failures"
    assert [i["status"] for i in plan["schedule"]] == ["infrastructure_failure", "completed", "completed", "completed"]
    summary = read_json(workspace / "output/summary/summary.json")
    assert len(summary["trials"]) == 4
    assert summary["pairs"][0]["outcome"] == "unknown"
    for process in runners.started:
        assert not process.auth.exists()
        assert (workspace / "output" / f"{process.name}-receipt.json").is_file()


def test_interrupt_stops_both_groups_before_auth_cleanup(workspace, monkeypatch):
    previous = signal.getsignal(signal.SIGTERM)
    runners = Runners(monkeypatch, interrupt=True)
    with pytest.raises(KeyboardInterrupt):
        parallel(workspace)
    assert signal.getsignal(signal.SIGTERM) == previous
    assert runners.signals == [(10000, signal.SIGTERM), (10000, signal.SIGKILL),
                               (10001, signal.SIGTERM), (10001, signal.SIGKILL)]
    plan = read_json(workspace / "output/schedule.json")
    assert plan["status"] == "interrupted"
    assert [i["status"] for i in plan["schedule"]] == ["interrupted", "interrupted", "not_run", "not_run"]
    for record in (workspace / "output/jobs").glob("*/*/run.json"):
        assert read_json(record)["status"] == read_json(record)["orchestration_status"] == "interrupted"
    assert all(not p.auth.exists() for p in runners.started)


def test_finished_peer_keeps_its_completed_receipt(workspace, monkeypatch):
    runners = Runners(monkeypatch, failure="provider", finished_peer=True)
    parallel(workspace)
    plan = read_json(workspace / "output/schedule.json")
    assert [i["status"] for i in plan["schedule"]] == ["infrastructure_failure", "completed", "completed", "completed"]
    assert runners.cleanup == [("002", "baseline")]
    assert runners.signals == []


def test_second_spawn_failure_keeps_first_and_next_pair(workspace, monkeypatch):
    runners = Runners(monkeypatch)
    def start(command, **kwargs):
        if command[0] == "docker":
            return runners.start(command, **kwargs)
        if command[command.index("--job-name") + 1] == "task-002-science":
            # The first is still active while the second spawn fails.
            raise OSError("synthetic second spawn failure")
        return runners.start(command, **kwargs)
    monkeypatch.setattr(cli.subprocess, "Popen", start)
    parallel(workspace)
    plan = read_json(workspace / "output/schedule.json")
    assert [i["status"] for i in plan["schedule"]] == ["completed", "infrastructure_failure", "completed", "completed"]
    assert runners.signals == []
    assert len(runners.started) == 3
    assert len(read_json(workspace / "output/summary/summary.json")["trials"]) == 4


def test_preparation_failure_does_not_block_sibling_or_next_pair(workspace, monkeypatch):
    runners = Runners(monkeypatch)
    original = cli.shutil.copytree
    def copy(source, target, **kwargs):
        if "task-002-baseline" in str(target):
            raise OSError("one local copy failure")
        return original(source, target, **kwargs)
    monkeypatch.setattr(cli.shutil, "copytree", copy)
    parallel(workspace)
    plan = read_json(workspace / "output/schedule.json")
    assert [i["status"] for i in plan["schedule"]] == ["infrastructure_failure", "completed", "completed", "completed"]
    assert len(runners.started) == 3 and runners.signals == []
    assert runners.cleanup == [("002", "baseline")]


def test_extraction_only_groups_two_tasks(workspace, monkeypatch):
    runners = Runners(monkeypatch)
    parallel(workspace, extraction_only=True)
    assert [p.name for p in runners.started] == ["task-002-science", "task-077-science"]
    plan = read_json(workspace / "output/schedule.json")
    assert plan["execution_policy"]["admission"] == "2_attempt_barrier"
    assert plan["status"] == "completed"


def test_parallel_smoke_still_admits_one(workspace):
    plan = parallel(workspace, execute=False, smoke=True)
    assert len(plan["schedule"]) == 1
    assert plan["execution_policy"]["concurrency"] == 1


def test_local_dummy_subprocesses_really_overlap_with_pair_barrier(workspace, monkeypatch):
    real_popen = subprocess.Popen
    processes = []
    def start(command, **kwargs):
        if command[0] == "docker":
            class PruneDone:
                args = command
                def poll(self):
                    return 0
                def communicate(self, input=None, timeout=None):
                    return (b"", b"")
                def wait(self, timeout=None):
                    return 0
                def __enter__(self):
                    return self
                def __exit__(self, *args):
                    return False
            return PruneDone()
        path = fake_agent_record(command)
        script = (
            "import json, pathlib, sys, time; "
            "start=time.monotonic(); time.sleep(0.15); "
            "pathlib.Path(sys.argv[1]).write_text(json.dumps([start,time.monotonic()]))"
        )
        process = real_popen([sys.executable, "-c", script, str(path / "interval.json")], **kwargs)
        processes.append(process)
        return process
    monkeypatch.setattr(cli, "_run_owned_process", lambda command, **kwargs: subprocess.CompletedProcess(command, 0))
    monkeypatch.setattr(cli.subprocess, "Popen", start)
    parallel(workspace)
    intervals = []
    for names in (("task-002-baseline", "task-002-science"), ("task-077-science", "task-077-baseline")):
        group = [json.loads((workspace / "output/jobs" / name / "synthetic-trial/interval.json").read_text()) for name in names]
        assert max(i[0] for i in group) < min(i[1] for i in group)
        intervals.append(group)
    assert min(i[0] for i in intervals[1]) > max(i[1] for i in intervals[0])
    assert all(process.poll() == 0 for process in processes)


@pytest.mark.parametrize("concurrency", [0, 9, True, 2.0, "2", None])
def test_invalid_concurrency_is_rejected(workspace, concurrency):
    config = read_json(workspace / "config.json")
    config["concurrency"] = concurrency
    write_json(workspace / "bad.json", config)
    with pytest.raises(ValueError, match="concurrency 1\\.\\.8"):
        cli.pilot(workspace, workspace / "bad.json", workspace / "output", False, None)
