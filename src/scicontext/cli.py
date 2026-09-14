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
from .io import digest_file, read_json, utc_now, write_json


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


def _snapshot_frozen_source(workspace: Path, output: Path) -> dict:
    """Copy the method source and prompts into the run directory so every
    attempt uploads identical bytes regardless of later workspace changes."""
    destination = output / "frozen-source"
    shutil.copytree(workspace / "src/scicontext", destination / "scicontext")
    shutil.copytree(workspace / "prompts", destination / "prompts")
    file_hashes = {path.relative_to(destination).as_posix(): digest_file(path)
                   for path in sorted(destination.rglob("*")) if path.is_file()}
    # The snapshot must match the provenance recorded in the schedule.
    live_prompts = _implementation_provenance(workspace)["prompt_sha256"]
    for rel, expected in live_prompts.items():
        if file_hashes.get(rel) != expected:
            raise ValueError(f"Frozen prompt drift after snapshot: {rel}")
    return {"dir": str(destination.resolve()), "file_hashes": file_hashes}


def _run_owned_process(command: list[str], *, check: bool = False, **kwargs) -> subprocess.CompletedProcess:
    """Own a separate process group and stop it before unwinding private auth.

    Only the process group created by this call is signalled; Docker services and
    unrelated Pier runs are never discovered or killed by name.
    """
    process = subprocess.Popen(command, start_new_session=True, **kwargs)
    try:
        code = process.wait()
    except BaseException:
        _stop_owned_process(process)
        raise
    result = subprocess.CompletedProcess(command, code)
    if check:
        result.check_returncode()
    return result


def _stop_owned_process(process) -> None:
    _stop_owned_processes([process])


def _stop_owned_processes(processes) -> None:
    # Signal every owned group immediately; forty workers must not each wait
    # for the previous worker's grace period before receiving cancellation.
    errors = []
    for process in processes:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        except Exception as error:
            errors.append(f"TERM {process.pid}: {error}")
    deadline = time.monotonic() + 5
    for process in processes:
        try:
            process.wait(timeout=max(0, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            pass
        except Exception as error:
            errors.append(f"wait {process.pid}: {error}")
    for process in processes:
        # Descendants can outlive their leader.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        except Exception as error:
            errors.append(f"KILL {process.pid}: {error}")
    for process in processes:
        try:
            process.wait(timeout=5)
        except Exception as error:
            errors.append(f"reap {process.pid}: {error}")
    if errors:
        raise RuntimeError("; ".join(errors))


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
                       "development_exposed": item["task_id"] in config.get("development_task_ids", ["002", "077"]),
                       **({"exposure_policy": "explicit_split_v1",
                           "prior_private_test_exposure": item["task_id"] in config.get("extra_private_diagnostic_exposure_task_ids", []),
                           "evaluation_partition": config["study_partition"]} if config.get("study_split") else {}),
                       **{key: plan[key] for key in ("implementation_revision", "implementation_dirty", "uv_lock_sha256", "prompt_sha256")}})
        if "execution_policy" in plan:
            record["execution_policy"] = plan["execution_policy"]
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
    if config.get("extractor", "scientific_objects") not in {"scientific_objects", "interactive_science"}:
        raise ValueError("Unknown extraction method")
    budget = TrialConfig(config["model"], config["reasoning_effort"], config["codex_version"],
                         config["total_seconds"], config["extraction_seconds"],
                         config.get("flexible_budget", False))
    concurrency = config.get("concurrency")
    if config.get("attempts") != 1 or type(concurrency) is not int or not (1 <= concurrency <= 40):
        raise ValueError("Pilot supports exactly one attempt and concurrency 1..40")
    restricted_optin = bool(os.environ.get("SCICONSORT_RESTRICTED_OPTIN"))
    if config.get("allow_restricted_licenses") and not restricted_optin:
        raise ValueError("Restricted-license tasks require the owner's explicit "
                         "SCICONSORT_RESTRICTED_OPTIN in the environment")
    ids = config["task_ids"]
    max_tasks = 119 if config.get("full_benchmark") else 5
    if not isinstance(ids, list) or not 1 <= len(ids) <= max_tasks or len(set(ids)) != len(ids):
        raise ValueError(f"A comparison requires one to {max_tasks} unique task IDs "
                         "(>5 needs full_benchmark: true)")
    receipt_path = Path(config.get("release_receipt", "data/release-receipt.json"))
    receipt = read_json(receipt_path if receipt_path.is_absolute() else workspace / receipt_path)
    available = {r["task_id"]: r for r in receipt["tasks"]}
    if any(t not in available for t in ids):
        raise ValueError("Configured tasks are not in the explicit release receipt")
    restricted_ids = [t for t in ids
                      if str(available[t].get("restricted_license", "false")).lower() != "false"]
    if restricted_ids and not (config.get("allow_restricted_licenses") and restricted_optin):
        raise ValueError("Restricted-license tasks are not enabled for this comparison")
    if config.get("sampling_manifest"):
        manifest_path = Path(config["sampling_manifest"])
        manifest_path = manifest_path if manifest_path.is_absolute() else workspace / manifest_path
        draw = read_json(manifest_path)
        if digest_file(manifest_path) != config["sampling_manifest_sha256"] or draw["task_ids"] != ids or draw["condition_order"] != config["condition_order"]:
            raise ValueError("Frozen sampling manifest differs from the comparison config")
    if config.get("study_split"):
        split_path = workspace / config["study_split"]
        split = read_json(split_path)
        partition = config.get("study_partition")
        field = {"development": "development_task_ids", "locked_evaluation": "locked_evaluation_task_ids"}.get(partition)
        if (not field or digest_file(split_path) != config.get("study_split_sha256")
                or not set(ids) <= set(split[field])
                or config.get("development_task_ids") != split["development_task_ids"]
                or config.get("extra_private_diagnostic_exposure_task_ids", []) != split["extra_private_diagnostic_exposure_task_ids"]):
            raise ValueError("Configuration differs from the frozen study split")
    if receipt["release_commit"] != config["release_commit"] or receipt["dataset_revision"] != config["dataset_revision"]:
        raise ValueError("Configuration and restored release revisions differ")
    selected = Path(receipt["selection_path"])
    for rel, expected_hash in receipt["file_hashes"].items():
        if not (selected / rel).is_file() or digest_file(selected / rel) != expected_hash:
            raise ValueError(f"Materialized release changed: {rel}")
    tasks = ["002"] if smoke else config["task_ids"]
    schedule = []
    for task in tasks:
        conditions = ["baseline"] if smoke else ["science"] if extraction_only else config.get("condition_order", {}).get(task, (["baseline", "science"] if int(task) % 2 == 0 else ["science", "baseline"]))
        if not smoke and not extraction_only and sorted(conditions) != ["baseline", "science"]:
            raise ValueError("Each comparison task needs exactly one attempt in each condition")
        for condition in conditions:
            schedule.append({"task_id": task, "condition": condition, "status": "pending", "phase": "not_started"})
    plan = {"schema_version": "1.0", "kind": "extraction_verification" if extraction_only else "subscription_smoke" if smoke else config.get("study_kind", "development_pilot"),
            "config": config, "config_sha256": digest_file(config_path),
            "selection_sha256": receipt["selection_sha256"],
            "restricted_license_optin": bool(restricted_ids) and config.get("allow_restricted_licenses", False),
            "restricted_license_task_count": len(restricted_ids),
            "schedule": schedule,
            "output": str(output.resolve()), "execute": execute}
    plan.update(_implementation_provenance(workspace))
    plan["execution_policy"] = {
        "concurrency": 1 if smoke else concurrency,
        "admission": "serial" if smoke or concurrency == 1 else "rolling",
        "pier_concurrency_per_process": 1,
        "shared_resources": concurrency >= 2 and not smoke,
        "attempt_failure": "record_and_continue_without_retry",
        "launch_spacing_seconds": 0,
    }
    if not execute:
        return plan
    if output.exists():
        raise FileExistsError("Run directory already exists; choose a fresh name to preserve attempts")
    agent = config.get("agent", "codex")
    if agent not in {"codex", "deepseek"}:
        raise ValueError("Unknown experiment agent; use codex or deepseek")
    deepseek_key = None
    if agent == "codex":
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
    else:
        deepseek_key = os.environ.get("DEEPSEEK_API_KEY")
        if not deepseek_key:
            raise ValueError("DEEPSEEK_API_KEY is not set for the deepseek agent route")
    output.mkdir(parents=True)
    # Per-attempt teardown owns its containers and networks. Do not prune
    # unrelated stopped containers or networks when starting a study.
    frozen_source = _snapshot_frozen_source(workspace, output)
    plan["frozen_source"] = frozen_source
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
    active = []
    try:
        if threading.current_thread() is threading.main_thread():
            prior_sigterm = signal.signal(signal.SIGTERM, _interrupt_schedule)
        private_session = tempfile.TemporaryDirectory(prefix="scicontext-auth-")
        private_dir = private_session.name
        os.chmod(private_dir, 0o700)
        private_auth = None
        private_deepseek_key = None
        if agent == "codex":
            private_auth = Path(private_dir) / "auth.json"
            shutil.copyfile(auth_file, private_auth)
            private_auth.chmod(0o600)
        else:
            private_deepseek_key = Path(private_dir) / "deepseek-key.json"
            write_json(private_deepseek_key, {"api_key": deepseek_key})
            private_deepseek_key.chmod(0o600)
        pulled_images = set()
        def prepare_attempt(item):
            nonlocal current, task_row, return_code
            current = item
            item.update({"status": "running", "phase": "preparing", "started_at": utc_now()})
            if (workspace / ".git").is_dir():
                revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=workspace, check=True,
                                          capture_output=True, text=True).stdout.strip()
                if revision != plan["implementation_revision"]:
                    raise RuntimeError("Implementation moved during the run; attempts are frozen to "
                                       f"{plan['implementation_revision'][:12]} but HEAD is {revision[:12]}")
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
                if image in pulled_images:
                    continue
                # Registry pulls burst-fail under concurrency (429/network);
                # retry with backoff instead of failing the attempt.
                for attempt in range(3):
                    pull = _run_owned_process(["docker", "pull", "--platform", "linux/amd64", image],
                                              stdout=subprocess.DEVNULL)
                    if pull.returncode == 0:
                        pulled_images.add(image)
                        break
                    if attempt < 2:
                        time.sleep(30 * (attempt + 1))
                else:
                    raise subprocess.CalledProcessError(pull.returncode, pull.args)
            command = [str(Path(sys.executable).parent / "pier"), "run",
                       "--path", str(task_input.resolve()), "--env", "docker", "--model", budget.model,
                       "--agent-import-path",
                       "scicontext.pier_agent:ScientificCodex" if agent == "codex" else "scicontext.deepseek_agent:DeepSeekAgent",
                       "--no-force-build", "--yes", "--n-concurrent", "1", "--n-attempts", "1",
                       "--max-retries", "0", "--agent-timeout-multiplier", str(total / 5400),
                       "--jobs-dir", str((output / "jobs").resolve()), "--job-name", f"task-{task}-{condition}"]
            if extraction_only:
                command += ["--disable-verification"]
            kwargs = {"condition": condition, "total_seconds": total, "extraction_seconds": extract,
                      "reasoning_effort": budget.reasoning_effort, "codex_version": budget.codex_version,
                      "flexible_budget": budget.flexible_budget,
                      "workspace": str(workspace), "smoke": smoke,
                      "extraction_only": extraction_only,
                      "frozen_source_dir": frozen_source["dir"],
                      "extractor": config.get("extractor", "scientific_objects")}
            if agent == "codex":
                kwargs["auth_file"] = str(private_auth)
            else:
                kwargs["deepseek_key_file"] = str(private_deepseek_key)
            for key, value in kwargs.items():
                command += ["--agent-kwarg", f"{key}={str(value).lower() if isinstance(value, bool) else value}"]
            if config.get("extraction_model_seconds") is not None:
                command += ["--agent-kwarg", f"extraction_model_seconds={config['extraction_model_seconds']}"]
            log = output / f"task-{task}-{condition}-runner.log"
            write_json(output / f"task-{task}-{condition}-launch.json", {
                **item, "command": ["auth_file=<private>" if arg.startswith("auth_file=")
                                    else "deepseek_key_file=<private>" if arg.startswith("deepseek_key_file=")
                                    else arg for arg in command],
                "images": {k: task_row[k] for k in ("environment_image", "verifier_image")},
                "task_selection_sha256": digest_file(task_input / "selection.json"),
            })
            print(f"Running {task}/{condition}; receipt: {log}", flush=True)
            environment = os.environ.copy()
            # Never forward unrelated provider credentials to benchmark tooling.
            for name in list(environment):
                if any(token in name.upper() for token in ("API_KEY", "AUTH_TOKEN", "BEARER", "SECRET")):
                    environment.pop(name, None)
            environment["PYTHONPATH"] = frozen_source["dir"]
            item["phase"] = "pier"
            write_json(output / "schedule.json", plan)
            return command, environment, log

        def remove_finished_images(item):
            # A task's images are shared by its arms. A fast arm must not evict
            # them while its partner is still running or waiting for admission.
            siblings = [s for s in schedule if s["task_id"] == item["task_id"]]
            if (smoke or not config.get("cleanup_images", True) or item.get("images_removed") or any(
                    s["status"] not in ("completed", "infrastructure_failure", "cancelled") for s in siblings)):
                return
            row = available[item["task_id"]]
            for image in {row["environment_image"], row["verifier_image"]}:
                subprocess.run(["docker", "rmi", image], capture_output=True, check=False)
                pulled_images.discard(image)
            for sibling in siblings:
                sibling["images_removed"] = True
            write_json(output / "schedule.json", plan)

        def finish_attempt(state, code, error=None):
            nonlocal current, task_row, return_code
            item = current = state["item"]
            task_row = state["task_row"]
            return_code = state["return_code"] = code
            if state.get("stream") is not None:
                state["stream"].close()
            item["status"] = _reconcile_trial(
                output, item, actual_budget, task_row, config, plan, code,
                **({"forced_status": "infrastructure_failure", "error": f"{type(error).__name__}: {error}"}
                   if error is not None else {}))
            item["finished_at"] = utc_now()
            write_json(output / "schedule.json", plan)
            if item["status"] != "completed":
                cleanup = _cleanup_owned_containers(output, item)
                plan.setdefault("container_cleanups", {})[f"task-{item['task_id']}-{item['condition']}"] = cleanup
                if cleanup["status"] != "complete":
                    raise RuntimeError("Failed attempt's containers could not be stopped; inspect cleanup receipt")
                print(f"Recorded {item['task_id']}/{item['condition']}: {item['status']}; continuing without retry.", flush=True)
            else:
                item["phase"] = "finished"
            state["finalized"] = True
            current = None
            write_json(output / "schedule.json", plan)
            remove_finished_images(item)

        def harvest_finished():
            nonlocal current
            for state in list(active):
                process = state.get("process")
                if process is None or state.get("finalized"):
                    continue
                current = state["item"]
                code = process.poll()
                if code is not None:
                    finish_attempt(state, code)
            active[:] = [state for state in active if not state.get("finalized")]

        width = plan["execution_policy"]["concurrency"]
        next_attempt = 0
        while active or next_attempt < len(schedule):
            # Refill available slots in declared order, without a task/batch
            # barrier. Start each prepared runner before preparing the next.
            while next_attempt < len(schedule) and len(active) < width:
                # With a wide pool, process completions while admitting further
                # work, not only after all forty preparations have finished.
                if len(active) >= 2:
                    harvest_finished()
                item = schedule[next_attempt]
                next_attempt += 1
                state = {"item": item, "task_row": available[item["task_id"]], "return_code": None}
                active.append(state)
                try:
                    command, environment, log = prepare_attempt(item)
                    state.update(command=command, environment=environment, log=log)
                except Exception as error:
                    finish_attempt(state, error.returncode if isinstance(error, subprocess.CalledProcessError) else None, error)
                if state.get("finalized"):
                    active.remove(state)
                    continue
                if width == 1:
                    try:
                        with state["log"].open("w") as stream:
                            result = _run_owned_process(state["command"], env=state["environment"], stdout=stream,
                                                        stderr=subprocess.STDOUT, cwd=workspace)
                    except Exception as error:
                        finish_attempt(state, error.returncode if isinstance(error, subprocess.CalledProcessError) else None, error)
                    else:
                        finish_attempt(state, result.returncode)
                else:
                    current = state["item"]
                    try:
                        state["stream"] = state["log"].open("w")
                        state["process"] = subprocess.Popen(
                            state["command"], start_new_session=True, env=state["environment"],
                            stdout=state["stream"], stderr=subprocess.STDOUT, cwd=workspace)
                    except Exception as error:
                        finish_attempt(state, None, error)
                if state.get("finalized"):
                    active.remove(state)
            harvest_finished()
            if active and (len(active) == width or next_attempt == len(schedule)):
                time.sleep(0.05)
        plan["status"] = "completed" if all(item["status"] == "completed" for item in schedule) else "completed_with_failures"
    except BaseException as error:
        interrupted = isinstance(error, (KeyboardInterrupt, SystemExit))
        plan["status"] = "interrupted" if interrupted else "runner_failure"
        plan["error"] = f"{type(error).__name__}: {error}"
        # A sibling may have exited between polls. Preserve an already finished
        # attempt instead of reclassifying its result as cancellation.
        if not interrupted:
            for state in active:
                if state.get("finalized") or state["item"] is current or state.get("process") is None:
                    continue
                code = state["process"].poll()
                if code is not None:
                    state["return_code"] = code
                    state["stream"].close()
                    try:
                        item = state["item"]
                        item["status"] = _reconcile_trial(output, item, actual_budget, state["task_row"], config, plan, code)
                        item["finished_at"] = utc_now()
                        if item["status"] == "completed":
                            item["phase"] = "finished"
                            state["finalized"] = True
                        else:
                            state["observed_failure"] = True
                    except Exception as accounting_error:
                        state["observed_failure"] = True
                        plan["accounting_error"] = f"{type(accounting_error).__name__}: {accounting_error}"
        # Stop every owned sibling before container cleanup, reconciliation, or
        # auth removal. A cancelled peer is interrupted, never a repair failure.
        try:
            _stop_owned_processes([state["process"] for state in active
                if not state.get("finalized") and state.get("process") is not None])
        except Exception as cleanup_error:
            plan.setdefault("process_cleanup_errors", []).append(f"{type(cleanup_error).__name__}: {cleanup_error}")
        for state in active:
            if state.get("finalized"):
                continue
            if state.get("stream") is not None:
                state["stream"].close()
        for state in active:
            if state.get("finalized"):
                continue
            item, row = state["item"], state["task_row"]
            # The owned Pier process has already stopped. Docker daemon children
            # may survive that process group; resolve and stop only this job's
            # proven containers before the private auth directory is removed.
            try:
                cleanup = _cleanup_owned_containers(output, item)
            except Exception as cleanup_error:
                cleanup = {"status": "incomplete", "errors": [f"{type(cleanup_error).__name__}: {cleanup_error}"]}
            if width == 1:
                plan["container_cleanup"] = cleanup
            else:
                plan.setdefault("container_cleanups", {})[f"task-{item['task_id']}-{item['condition']}"] = cleanup
            status = "interrupted" if interrupted or (item is not current and not state.get("observed_failure")) else "infrastructure_failure"
            item["status"] = status
            item["finished_at"] = utc_now()
            code = (error.returncode if isinstance(error, subprocess.CalledProcessError) else return_code) if item is current else state["return_code"]
            try:
                _reconcile_trial(output, item, actual_budget, row, config, plan, code,
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
        if plan["status"] in {"completed", "completed_with_failures"} and summary is None:
            raise RuntimeError("Schedule completed, but summary generation failed; inspect schedule.json")
    return summary


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] in {"packet", "assemble-objects"}:
        from .tool_cli import main as helper_main
        return helper_main(argv)
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="command", required=True)
    prepare = subs.add_parser("prepare", help="Restore pinned release and development selection")
    prepare.add_argument("--workspace", type=Path, default=_workspace())
    prepare.add_argument("--task-id", default="002,077")
    prepare.add_argument("--receipt", type=Path, help="Save a separate selection receipt, preserving the development selection")
    summaries = subs.add_parser("summarize", help="Generate paired results from raw artifacts")
    summaries.add_argument("root", type=Path)
    summaries.add_argument("--output", type=Path, required=True)
    objects = subs.add_parser("scientific-objects", help="Extract a code-owned scientific object graph without model calls")
    objects.add_argument("--root", type=Path, required=True)
    objects.add_argument("paths", nargs="*", help="Optional public source paths; otherwise use task-local packet selection")
    objects.add_argument("--interpretations", type=Path, help="Contextual annotations referencing extracted object IDs")
    objects.add_argument("--context-root", type=Path)
    objects.add_argument("--output", type=Path, required=True)
    objects.add_argument("--markdown", type=Path)
    objects.add_argument("--llm-input", type=Path, help="Save the scientific context payload for interpretation")
    run = subs.add_parser("pilot", help="Print schedule; --execute runs the approved development pilot")
    run.add_argument("--workspace", type=Path, default=_workspace())
    run.add_argument("--config", type=Path, default=_workspace() / "configs/interactive-five.json")
    run.add_argument("--output", type=Path, required=True)
    run.add_argument("--auth-file", type=Path)
    run.add_argument("--execute", action="store_true")
    run.add_argument("--smoke", action="store_true")
    run.add_argument("--extract-only", "--prepare-only", action="store_true", help="Verify only source preparation; no model, repair or private verifier")
    for name in ("packet", "assemble-objects"):
        subs.add_parser(name, help="Offline extraction helper; use command --help")
    args = parser.parse_args(argv)
    if args.command == "prepare":
        from .release import prepare as prepare_release
        result = prepare_release(args.workspace, args.task_id.split(","), receipt_path=args.receipt)
    elif args.command == "summarize":
        from .results import write_summary
        result = write_summary(args.root, args.output)
    elif args.command == "scientific-objects":
        from .scientific_objects import extract_objects
        from .object_context import enrich_objects, enrichment_input, render_objects
        from .packet import build_packet
        packet = build_packet(args.root, args.context_root, multilingual=True, source_paths=args.paths or None)
        result = extract_objects(args.root, packet)
        from .scientific_model import reading_input
        context = enrichment_input(result, packet)
        if args.llm_input:
            write_json(args.llm_input, reading_input(context))
        if args.interpretations:
            result = enrich_objects(result, read_json(args.interpretations), reading_input(context))
        write_json(args.output, result)
        if args.markdown:
            args.markdown.parent.mkdir(parents=True, exist_ok=True)
            args.markdown.write_text(render_objects(result))
    else:
        result = pilot(args.workspace.resolve(), args.config, args.output, args.execute, args.auth_file, args.smoke, args.extract_only)
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
