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
    def __init__(self, monkeypatch, *, failure=None, interrupt=False, reward=1, finished_peer=False,
                 max_alive=2, delays=None):
        self.started = []
        self.events = []
        self.signals = []
        self.cleanup = []
        self.failure, self.interrupt, self.reward = failure, interrupt, reward
        self.finished_peer = finished_peer
        self.max_alive = max_alive
        self.delays = delays or {}
        self.removed_images = []
        monkeypatch.setattr(cli, "_run_owned_process", self.pull)
        monkeypatch.setattr(cli.subprocess, "Popen", self.start)
        monkeypatch.setattr(cli.os, "killpg", self.kill)
        monkeypatch.setattr(cli, "_cleanup_owned_containers", self.clean_containers)

    def pull(self, command, **kwargs):
        assert command[:2] == ["docker", "pull"]
        return subprocess.CompletedProcess(command, 0)

    def start(self, command, **kwargs):
        if command[0] == "docker":
            if command[1] == "rmi":
                task = command[2].split("-")[1].split("@")[0]
                peers = [p for p in self.started if p.name.startswith(f"task-{task}-")]
                assert all(not p.alive for p in peers), "Do not evict a running partner's images"
                self.removed_images.append((command[2], [p.name for p in peers]))
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
                if self.polls < owner.delays.get(self.name, 2):
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
        assert sum(p.alive for p in self.started) <= self.max_alive
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


def parallel(root, *, execute=True, extraction_only=False, smoke=False, concurrency=2):
    config = read_json(root / "config.json")
    config["concurrency"] = concurrency
    write_json(root / "parallel.json", config)
    return cli.pilot(root, root / "parallel.json", root / "output", execute,
                     root / "synthetic-auth.json", smoke=smoke, extraction_only=extraction_only)


@pytest.mark.parametrize("reward", [0, 1])
def test_parallel_pairs_overlap_and_preserve_declared_order(workspace, monkeypatch, reward):
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
    assert plan["execution_policy"]["admission"] == "rolling"
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
    runners = Runners(monkeypatch, failure=failure, delays={"task-002-science": 8})
    parallel(workspace)
    assert len(runners.started) == len({p.name for p in runners.started}) == 4
    assert runners.signals == []
    assert runners.cleanup == [("002", "baseline")]
    assert runners.events.index(("start", "task-077-science")) < runners.events.index(("finish", "task-002-science"))
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


def test_extraction_only_uses_same_rolling_pool(workspace, monkeypatch):
    runners = Runners(monkeypatch)
    parallel(workspace, extraction_only=True)
    assert [p.name for p in runners.started] == ["task-002-science", "task-077-science"]
    plan = read_json(workspace / "output/schedule.json")
    assert plan["execution_policy"]["admission"] == "rolling"
    assert plan["status"] == "completed"


def test_parallel_smoke_still_admits_one(workspace):
    plan = parallel(workspace, execute=False, smoke=True)
    assert len(plan["schedule"]) == 1
    assert plan["execution_policy"]["concurrency"] == 1


def test_local_dummy_subprocess_starts_next_task_while_slow_peer_runs(workspace, monkeypatch):
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
        name = command[command.index("--job-name") + 1]
        delay = .7 if name == "task-002-science" else .05
        script = (
            "import json, pathlib, sys, time; "
            f"start=time.monotonic(); time.sleep({delay}); "
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
        intervals.append(group)
    assert intervals[0][1][0] < intervals[1][0][0] < intervals[0][1][1]
    # The second task's own two arms need not overlap: one slot is still
    # occupied by the first task's slow arm. Total live runners stays bounded.
    live = 0
    for _, change in sorted((point, change) for group in intervals for span in group
                            for point, change in ((span[0], 1), (span[1], -1))):
        live += change
        assert 0 <= live <= 2
    assert all(process.poll() == 0 for process in processes)


def test_free_slot_refills_and_images_wait_for_both_arms(workspace, monkeypatch):
    runners = Runners(monkeypatch, delays={"task-002-science": 10})
    parallel(workspace)
    events = runners.events
    assert events.index(("finish", "task-002-baseline")) < events.index(("start", "task-077-science"))
    assert events.index(("start", "task-077-baseline")) < events.index(("finish", "task-002-science"))
    assert len(runners.removed_images) == 4
    assert all(len(peers) == 2 for _, peers in runners.removed_images)


def test_eight_slots_refill_before_seven_slow_peers_finish(workspace, monkeypatch):
    from scicontext.io import digest_file
    config = read_json(workspace / "config.json")
    receipt = read_json(workspace / "data/release-receipt.json")
    config["task_ids"] = ["002", "077", "078", "079", "080"]
    for task in config["task_ids"][2:]:
        path = workspace / "selection" / f"task_{task}" / "task.toml"
        path.parent.mkdir()
        path.write_text("# synthetic task\n")
        receipt["file_hashes"][f"task_{task}/task.toml"] = digest_file(path)
        receipt["tasks"].append({"task_id": task, "environment_image": f"env-{task}@sha256:00",
                                 "verifier_image": f"verifier-{task}@sha256:00"})
    write_json(workspace / "config.json", config)
    write_json(workspace / "data/release-receipt.json", receipt)
    delays = {f"task-{task}-{arm}": 20 for task in config["task_ids"][:4] for arm in ("baseline", "science")}
    delays["task-002-baseline"] = 2
    runners = Runners(monkeypatch, max_alive=8, delays=delays)
    clock = [0.0]
    monkeypatch.setattr(cli.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(cli.time, "sleep", lambda seconds: clock.__setitem__(0, clock[0] + seconds))
    parallel(workspace, concurrency=8)
    assert len(runners.started) == len({p.name for p in runners.started}) == 10
    assert runners.events.index(("start", "task-080-baseline")) < runners.events.index(("finish", "task-002-science"))
    assert runners.signals == []


def test_cancel_after_refill_preserves_finished_attempt(workspace, monkeypatch):
    runners = Runners(monkeypatch, delays={"task-002-science": 20})
    def start(command, **kwargs):
        process = runners.start(command, **kwargs)
        if len(runners.started) == 3:
            runners.interrupt = True
        return process
    monkeypatch.setattr(cli.subprocess, "Popen", start)
    with pytest.raises(KeyboardInterrupt):
        parallel(workspace)
    plan = read_json(workspace / "output/schedule.json")
    assert [s["status"] for s in plan["schedule"]] == ["completed", "interrupted", "interrupted", "not_run"]
    assert {pid for pid, _ in runners.signals} == {10001, 10002}
    assert all(not p.auth.exists() for p in runners.started)


@pytest.mark.parametrize("concurrency", [0, 9, True, 2.0, "2", None])
def test_invalid_concurrency_is_rejected(workspace, concurrency):
    config = read_json(workspace / "config.json")
    config["concurrency"] = concurrency
    write_json(workspace / "bad.json", config)
    with pytest.raises(ValueError, match="concurrency 1\\.\\.8"):
        cli.pilot(workspace, workspace / "bad.json", workspace / "output", False, None)
