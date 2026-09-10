"""Public commands for extraction, reproducible runs, and artifact analysis."""
from __future__ import annotations

import argparse
import json
import os
import re
import signal
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import asdict, replace
from pathlib import Path

from .controller import TrialConfig
from .io import digest_file, digest_json, read_json, utc_now, write_json


def _workspace() -> Path:
    return Path(__file__).resolve().parents[2]


def _implementation_provenance(workspace: Path) -> dict:
    revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=workspace, check=True,
                              capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"], cwd=workspace,
                           check=True, capture_output=True, text=True).stdout.strip()
    lock = workspace / "uv.lock"
    return {"implementation_revision": revision, "implementation_dirty": bool(dirty),
            "uv_lock_sha256": digest_file(lock) if lock.is_file() else None,
            "prompt_sha256": {path.relative_to(workspace).as_posix(): digest_file(path)
                              for path in sorted((workspace / "prompts").glob("*.md"))}}


def _run_owned_process(command: list[str], *, check: bool = False, **kwargs) -> subprocess.CompletedProcess:
    """Own a separate process group and stop it before unwinding private auth.

    Only the process group created by this call is signalled; Docker services and
    unrelated Pier runs are never discovered or killed by name.
    """
    process = subprocess.Popen(command, start_new_session=True, **kwargs)
    try:
        code = process.wait()
    except BaseException:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass
        finally:
            # Descendants may outlive their leader, including ones ignoring TERM.
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait(timeout=5)
        raise
    result = subprocess.CompletedProcess(command, code)
    if check:
        result.check_returncode()
    return result


def _interrupt_schedule(signum, frame):
    raise KeyboardInterrupt(f"Received signal {signum}")


_CONTAINER_INSPECT_FORMAT = (
    '{"id":{{json .Id}},"running":{{json .State.Running}},'
    '"project":{{json (index .Config.Labels "com.docker.compose.project")}},'
    '"working_dir":{{json (index .Config.Labels "com.docker.compose.project.working_dir")}},'
    '"config_files":{{json (index .Config.Labels "com.docker.compose.project.config_files")}}}'
)


def _cleanup_owned_containers(output: Path, item: dict) -> dict:
    """Stop, never remove, containers proved to belong to this interrupted job.

    Pier 0.3.0's exact trial names and Compose path labels jointly establish
    ownership. A project-name match alone never authorizes stopping a container.
    Only running containers are queried; successful jobs do not call this helper.
    """
    job = (output / "jobs" / f"task-{item['task_id']}-{item['condition']}").resolve()
    task = (output / "inputs" / f"task-{item['task_id']}-{item['condition']}" / f"task_{item['task_id']}").resolve()
    result = {"started_at": utc_now(), "status": "complete", "containers": [], "errors": [], "warnings": []}
    deadline = time.monotonic() + 45
    owned: dict[str, dict] = {}

    def docker(*arguments):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("Owned-container cleanup exceeded its 45-second allowance")
        return subprocess.run(["docker", *arguments], check=True, capture_output=True, text=True,
                              timeout=min(10, remaining)).stdout

    def inspect(identity):
        return json.loads(docker("inspect", "--format", _CONTAINER_INSPECT_FORMAT, identity))

    try:
        for path in sorted(job.glob("*/config.json")):
            trial = path.parent
            config = read_json(path)
            name = config.get("trial_name")
            task_config = config.get("task") if isinstance(config.get("task"), dict) else {}
            if (path.is_symlink() or trial.is_symlink() or trial.parent.resolve() != job
                    or name != trial.name or not isinstance(name, str)
                    or not re.fullmatch(rf"task_{re.escape(item['task_id'])}__[A-Za-z0-9]+", name)
                    or Path(config.get("trials_dir", "")).resolve() != job
                    or Path(task_config.get("path", "")).resolve() != task):
                result["errors"].append(f"Unproven trial ownership: {path.relative_to(output.resolve())}")
                continue
            # These session IDs and contexts are fixed by the pinned Pier runner
            # and this adapter; do not scan or stop matching name prefixes.
            projects = [(name.lower(), task / "environment", trial / "docker-compose-mounts.json")]
            if item["condition"] == "science":
                projects.append((name.lower() + "-extract", task / "environment", trial / "extraction_environment/docker-compose-mounts.json"))
            projects.append((name.lower() + "__verifier__trial", task / "tests", trial / "docker-compose-mounts.json"))
            for project, working_dir, mounts_file in projects:
                identities = docker("ps", "--quiet", "--no-trunc", "--filter", f"label=com.docker.compose.project={project}").split()
                for identity in dict.fromkeys(identities):
                    if not re.fullmatch(r"[a-f0-9]{64}", identity):
                        result["errors"].append(f"Invalid container identity returned for exact project {project}")
                        continue
                    metadata = inspect(identity)
                    raw_paths = metadata.get("config_files")
                    config_paths = {Path(value).resolve() for value in raw_paths.split(",")} if isinstance(raw_paths, str) else set()
                    valid = (metadata.get("id") == identity and metadata.get("project") == project
                             and isinstance(metadata.get("working_dir"), str)
                             and Path(metadata["working_dir"]).resolve() == working_dir.resolve()
                             and mounts_file.is_file() and not mounts_file.is_symlink()
                             and mounts_file.resolve().is_relative_to(trial.resolve())
                             and mounts_file.resolve() in config_paths)
                    entry = {"id": identity, "project": project, "ownership_verified": valid,
                             "initially_running": metadata.get("running"), "stopped": False}
                    result["containers"].append(entry)
                    if not valid:
                        result["errors"].append(f"Refused container {identity}: Compose project/path ownership differs")
                    elif metadata.get("running") is True:
                        owned[identity] = entry
                    elif metadata.get("running") is False:
                        entry["stopped"] = True
                    else:
                        result["errors"].append(f"Unknown running state for {identity}")
    except (OSError, ValueError, TypeError, subprocess.SubprocessError) as error:
        result["errors"].append(f"{type(error).__name__}: {error}")
    try:
        # Discovery of another role can fail after a main container was proved
        # owned. Still stop every already-proven container before reporting it.
        if owned:
            try:
                docker("stop", "--time", "5", *owned)
            except (subprocess.SubprocessError, OSError) as error:
                result["warnings"].append(f"Docker stop reported {type(error).__name__}; inspecting exact owned IDs")
            remaining = []
            for identity, entry in owned.items():
                state = inspect(identity).get("running")
                if state is False:
                    entry["stopped"] = True
                elif state is True:
                    remaining.append(identity)
                else:
                    result["errors"].append(f"Unknown final running state for {identity}")
            if remaining:
                docker("kill", "--signal", "KILL", *remaining)
                for identity in remaining:
                    owned[identity]["stopped"] = inspect(identity).get("running") is False
    except (OSError, ValueError, TypeError, subprocess.SubprocessError) as error:
        result["errors"].append(f"{type(error).__name__}: {error}")
    finally:
        if result["errors"] or any(not entry["stopped"] for entry in result["containers"]):
            result["status"] = "incomplete"
        result["finished_at"] = utc_now()
        write_json(output / f"task-{item['task_id']}-{item['condition']}-container-cleanup.json", result)
    return result


def _reconcile_trial(output: Path, item: dict, budget: TrialConfig, task_row: dict,
                     config: dict, plan: dict, return_code: int | None,
                     *, forced_status: str | None = None, error: str | None = None) -> str:
    """Preserve an attempted trial even when setup failed before agent.run()."""
    job = output / "jobs" / f"task-{item['task_id']}-{item['condition']}"
    # Pier places each trial directly under its job. Scratch files may themselves
    # be named run.json and must never be interpreted or rewritten as receipts.
    records = sorted(job.glob("*/run.json"))
    status = forced_status or ("infrastructure_failure" if return_code or not records else "completed")
    if not records:
        path = job / "setup-failure/run.json"
        record = {"schema_version": "1.0", "task_id": item["task_id"], "condition": item["condition"],
                  "model": budget.model, "reasoning_effort": budget.reasoning_effort,
                  "codex_version": budget.codex_version, "config": asdict(budget),
                  "status": status, "stages": [], "started_at": item["started_at"],
                  "finished_at": utc_now(), "duration_seconds": None,
                  "error": error or "No agent record; inspect preserved Pier setup/runner artifacts"}
        write_json(path, record)
        records = [path]
    for path in records:
        record = read_json(path)
        if record.get("status") == "infrastructure_failure":
            status = forced_status or "infrastructure_failure"
        if record.get("status") == "running":
            record["status"] = forced_status or "infrastructure_failure"
            record["finished_at"] = utc_now()
            status = forced_status or "infrastructure_failure"
        expected_image = task_row["environment_image"]
        if record.get("environment_image") not in (None, expected_image):
            raise ValueError("Executed environment image differs from the pinned task selection")
        patch = path.parent / "artifacts/model.patch"
        record.update({"patch_sha256": digest_file(patch) if patch.is_file() else None,
                       "selection_sha256": plan["selection_sha256"], "config_sha256": plan["config_sha256"],
                       "release_commit": config["release_commit"], "benchmark_revision": config["release_commit"],
                       "dataset_revision": config["dataset_revision"], "runner_version": config["pier_version"],
                       "environment_image": expected_image, "verifier_image": task_row["verifier_image"],
                       "experiment_kind": plan["kind"], "orchestration_status": status,
                       **{key: plan[key] for key in ("implementation_revision", "implementation_dirty", "uv_lock_sha256", "prompt_sha256")}})
        write_json(path, record)
    log = output / f"task-{item['task_id']}-{item['condition']}-runner.log"
    write_json(output / f"task-{item['task_id']}-{item['condition']}-receipt.json", {
        "task_id": item["task_id"], "condition": item["condition"], "status": status,
        "phase": item["phase"], "started_at": item["started_at"], "finished_at": utc_now(),
        "return_code": return_code, "error": error,
        "runner_log_sha256": digest_file(log) if log.is_file() else None,
    })
    return status


def pilot(workspace: Path, config_path: Path, output: Path, execute: bool,
          auth_file: Path | None, smoke: bool = False, extraction_only: bool = False) -> dict:
    if smoke and extraction_only:
        raise ValueError("Choose subscription smoke or extraction-only verification, not both")
    config = read_json(config_path)
    budget = TrialConfig(config["model"], config["reasoning_effort"], config["codex_version"],
                         config["total_seconds"], config["extraction_seconds"])
    if config.get("attempts") != 1 or config.get("concurrency") != 1:
        raise ValueError("Pilot supports exactly one attempt and serial execution")
    if config.get("allow_restricted_licenses"):
        raise ValueError("Development pilot does not opt into restricted licenses")
    if not set(config["task_ids"]) <= {"002", "077"}:
        raise ValueError("Pilot is limited to the approved development tasks 002 and 077")
    receipt = read_json(workspace / "data/release-receipt.json")
    if receipt["release_commit"] != config["release_commit"] or receipt["dataset_revision"] != config["dataset_revision"]:
        raise ValueError("Configuration and restored release revisions differ")
    selected = Path(receipt["selection_path"])
    for rel, expected_hash in receipt["file_hashes"].items():
        if not (selected / rel).is_file() or digest_file(selected / rel) != expected_hash:
            raise ValueError(f"Materialized release changed: {rel}")
    tasks = ["002"] if smoke else config["task_ids"]
    schedule = []
    for task in tasks:
        conditions = ["baseline"] if smoke else ["science"] if extraction_only else (["baseline", "science"] if int(task) % 2 == 0 else ["science", "baseline"])
        for condition in conditions:
            schedule.append({"task_id": task, "condition": condition, "status": "pending", "phase": "not_started"})
    plan = {"schema_version": "1.0", "kind": "extraction_verification" if extraction_only else "subscription_smoke" if smoke else "development_pilot",
            "config": config, "config_sha256": digest_file(config_path),
            "selection_sha256": receipt["selection_sha256"], "schedule": schedule,
            "output": str(output.resolve()), "execute": execute}
    plan.update(_implementation_provenance(workspace))
    if not execute:
        return plan
    if output.exists():
        raise FileExistsError("Run directory already exists; choose a fresh name to preserve attempts")
    if auth_file is None:
        auth_file = Path.home() / ".codex/auth.json"
    if not auth_file.is_file():
        raise ValueError("Saved ChatGPT auth cache not found; provide a private --auth-file or use device login")
    # Inspect only the auth mode, never serialize credential values into public receipts.
    auth_mode = read_json(auth_file)
    if auth_mode.get("auth_mode") == "apikey" or auth_mode.get("OPENAI_API_KEY"):
        raise ValueError("API-key auth is not the approved route; require ChatGPT subscription auth")
    if not auth_mode.get("tokens"):
        raise ValueError("Expected a saved ChatGPT token cache")
    del auth_mode
    output.mkdir(parents=True)
    plan["started_at"] = utc_now()
    plan["status"] = "running"
    write_json(output / "schedule.json", plan)
    actual_budget = replace(budget, total_seconds=60, extraction_seconds=10) if smoke else budget
    current = None
    task_row = None
    return_code = None
    summary = None
    private_session = None
    prior_sigterm = None
    try:
        if threading.current_thread() is threading.main_thread():
            prior_sigterm = signal.signal(signal.SIGTERM, _interrupt_schedule)
        private_session = tempfile.TemporaryDirectory(prefix="scicontext-auth-")
        private_dir = private_session.name
        os.chmod(private_dir, 0o700)
        private_auth = Path(private_dir) / "auth.json"
        shutil.copyfile(auth_file, private_auth)
        private_auth.chmod(0o600)
        for item in schedule:
            current = item
            item.update({"status": "running", "phase": "preparing", "started_at": utc_now()})
            write_json(output / "schedule.json", plan)
            return_code = None
            task, condition = item["task_id"], item["condition"]
            task_row = None
            task_row = next(r for r in receipt["tasks"] if r["task_id"] == task)
            task_input = output / "inputs" / f"task-{task}-{condition}"
            task_input.mkdir(parents=True)
            shutil.copytree(selected / f"task_{task}", task_input / f"task_{task}")
            write_json(task_input / "selection.json", {"task_ids": [task], "allow_restricted_licenses": False})
            total, extract = actual_budget.total_seconds, actual_budget.extraction_seconds
            # Pier 0.3.0 prioritizes a named built-in agent over import_path. The
            # release wrapper always supplies --agent, so invoke Pier directly.
            item["phase"] = "pulling_images"
            write_json(output / "schedule.json", plan)
            images = [task_row["environment_image"]] if extraction_only else [task_row["environment_image"], task_row["verifier_image"]]
            for image in images:
                _run_owned_process(["docker", "pull", "--platform", "linux/amd64", image], check=True, stdout=subprocess.DEVNULL)
            command = [str(Path(sys.executable).parent / "pier"), "run",
                       "--path", str(task_input.resolve()), "--env", "docker", "--model", budget.model,
                       "--agent-import-path", "scicontext.pier_agent:ScientificCodex",
                       "--no-force-build", "--no-delete", "--yes", "--n-concurrent", "1", "--n-attempts", "1",
                       "--max-retries", "0", "--agent-timeout-multiplier", str(total / 5400),
                       "--jobs-dir", str((output / "jobs").resolve()), "--job-name", f"task-{task}-{condition}"]
            if extraction_only:
                command += ["--disable-verification"]
            for key, value in {"condition": condition, "total_seconds": total, "extraction_seconds": extract,
                               "reasoning_effort": budget.reasoning_effort, "codex_version": budget.codex_version,
                               "workspace": str(workspace), "auth_file": str(private_auth), "smoke": smoke,
                               "extraction_only": extraction_only}.items():
                command += ["--agent-kwarg", f"{key}={str(value).lower() if isinstance(value, bool) else value}"]
            log = output / f"task-{task}-{condition}-runner.log"
            write_json(output / f"task-{task}-{condition}-launch.json", {
                **item, "command": ["auth_file=<private>" if arg.startswith("auth_file=") else arg for arg in command],
                "images": {k: task_row[k] for k in ("environment_image", "verifier_image")},
                "task_selection_sha256": digest_file(task_input / "selection.json"),
            })
            print(f"Running {task}/{condition}; receipt: {log}", flush=True)
            environment = os.environ.copy()
            # Never forward unrelated provider credentials to benchmark tooling.
            for name in list(environment):
                if any(token in name.upper() for token in ("API_KEY", "AUTH_TOKEN", "BEARER", "SECRET")):
                    environment.pop(name, None)
            environment["PYTHONPATH"] = str(workspace / "src")
            item["phase"] = "pier"
            write_json(output / "schedule.json", plan)
            with log.open("w") as stream:
                result = _run_owned_process(command, env=environment, stdout=stream, stderr=subprocess.STDOUT, cwd=workspace)
            return_code = result.returncode
            item["status"] = _reconcile_trial(output, item, actual_budget, task_row, config, plan, return_code)
            item["finished_at"] = utc_now()
            write_json(output / "schedule.json", plan)
            if item["status"] != "completed":
                raise RuntimeError(f"Runner failed; retained {log}. Remaining schedule has not been executed.")
            item["phase"] = "finished"
            current = None
        plan["status"] = "completed"
    except BaseException as error:
        interrupted = isinstance(error, (KeyboardInterrupt, SystemExit))
        plan["status"] = "interrupted" if interrupted else "runner_failure"
        plan["error"] = f"{type(error).__name__}: {error}"
        if current is not None and task_row is not None:
            # The owned Pier process has already stopped. Docker daemon children
            # may survive that process group; resolve and stop only this job's
            # proven containers before the private auth directory is removed.
            plan["container_cleanup"] = _cleanup_owned_containers(output, current)
            status = "interrupted" if interrupted else "infrastructure_failure"
            current["status"] = status
            current["finished_at"] = utc_now()
            code = error.returncode if isinstance(error, subprocess.CalledProcessError) else return_code
            try:
                _reconcile_trial(output, current, actual_budget, task_row, config, plan, code,
                                 forced_status=status, error=plan["error"])
            except Exception as accounting_error:
                plan["accounting_error"] = f"{type(accounting_error).__name__}: {accounting_error}"
        raise
    finally:
        if prior_sigterm is not None:
            signal.signal(signal.SIGTERM, prior_sigterm)
        if private_session is not None:
            private_session.cleanup()
        for item in schedule:
            if item["status"] == "pending":
                item.update({"status": "not_run", "reason": "schedule_stopped_before_launch"})
        plan["finished_at"] = utc_now()
        write_json(output / "schedule.json", plan)
        if (output / "jobs").is_dir():
            from .results import write_summary
            try:
                summary = write_summary(output / "jobs", output / "summary")
            except Exception as error:
                plan["summary_error"] = f"{type(error).__name__}: {error}"
                write_json(output / "schedule.json", plan)
        if plan["status"] == "completed" and summary is None:
            raise RuntimeError("Schedule completed, but summary generation failed; inspect schedule.json")
    return summary


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] in {"index", "cite", "expression", "checkpoint", "packet", "assemble", "run-probes"}:
        from .tool_cli import main as helper_main
        return helper_main(argv)
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="command", required=True)
    schema = subs.add_parser("schema", help="Export strict extraction output schema")
    schema.add_argument("--output", type=Path)
    prepare = subs.add_parser("prepare", help="Restore pinned release and development selection")
    prepare.add_argument("--workspace", type=Path, default=_workspace())
    prepare.add_argument("--task-id", default="002,077")
    analyze = subs.add_parser("analyze", help="Validate and analyze a graph against its public sources")
    analyze.add_argument("--root", type=Path, required=True)
    analyze.add_argument("--graph", type=Path, required=True)
    analyze.add_argument("--output", type=Path, required=True)
    summaries = subs.add_parser("summarize", help="Generate paired results from raw artifacts")
    summaries.add_argument("root", type=Path)
    summaries.add_argument("--output", type=Path, required=True)
    run = subs.add_parser("pilot", help="Print schedule; --execute runs the approved development pilot")
    run.add_argument("--workspace", type=Path, default=_workspace())
    run.add_argument("--config", type=Path, default=_workspace() / "configs/pilot.json")
    run.add_argument("--output", type=Path, required=True)
    run.add_argument("--auth-file", type=Path)
    run.add_argument("--execute", action="store_true")
    run.add_argument("--smoke", action="store_true")
    run.add_argument("--extract-only", action="store_true", help="Verify only extraction on configured development tasks; no repair or private verifier")
    for name in ("index", "cite", "expression", "checkpoint", "packet", "assemble", "run-probes"):
        subs.add_parser(name, help="Offline extraction helper; use command --help")
    args = parser.parse_args(argv)
    if args.command == "schema":
        from .graph import graph_schema
        result = graph_schema()
        if args.output:
            write_json(args.output, result)
    elif args.command == "prepare":
        from .release import prepare as prepare_release
        result = prepare_release(args.workspace, args.task_id.split(","))
    elif args.command == "analyze":
        from .tool_cli import checkpoint
        result = checkpoint(args.graph, args.root, args.output)
    elif args.command == "summarize":
        from .results import write_summary
        result = write_summary(args.root, args.output)
    else:
        result = pilot(args.workspace.resolve(), args.config, args.output, args.execute, args.auth_file, args.smoke, args.extract_only)
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
