"""Public commands for extraction, reproducible runs, and artifact analysis."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from .controller import TrialConfig
from .io import digest_file, digest_json, read_json, utc_now, write_json


def _workspace() -> Path:
    return Path(__file__).resolve().parents[2]


def pilot(workspace: Path, config_path: Path, output: Path, execute: bool,
          auth_file: Path | None, smoke: bool = False) -> dict:
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
        conditions = ["baseline"] if smoke else (["baseline", "science"] if int(task) % 2 == 0 else ["science", "baseline"])
        for condition in conditions:
            schedule.append({"task_id": task, "condition": condition})
    plan = {"schema_version": "1.0", "kind": "subscription_smoke" if smoke else "development_pilot",
            "config": config, "config_sha256": digest_file(config_path),
            "selection_sha256": receipt["selection_sha256"], "schedule": schedule,
            "output": str(output.resolve()), "execute": execute}
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
    write_json(output / "schedule.json", plan)
    with tempfile.TemporaryDirectory(prefix="scicontext-auth-") as private_dir:
        os.chmod(private_dir, 0o700)
        private_auth = Path(private_dir) / "auth.json"
        shutil.copyfile(auth_file, private_auth)
        private_auth.chmod(0o600)
        for item in schedule:
            task, condition = item["task_id"], item["condition"]
            task_input = output / "inputs" / f"task-{task}-{condition}"
            task_input.mkdir(parents=True)
            shutil.copytree(selected / f"task_{task}", task_input / f"task_{task}")
            write_json(task_input / "selection.json", {"task_ids": [task], "allow_restricted_licenses": False})
            total = 60 if smoke else budget.total_seconds
            extract = 10 if smoke else budget.extraction_seconds
            task_row = next(r for r in receipt["tasks"] if r["task_id"] == task)
            # Pier 0.3.0 prioritizes a named built-in agent over import_path. The
            # release wrapper always supplies --agent, so invoke Pier directly.
            for image in (task_row["environment_image"], task_row["verifier_image"]):
                subprocess.run(["docker", "pull", "--platform", "linux/amd64", image], check=True, stdout=subprocess.DEVNULL)
            command = [str(Path(sys.executable).parent / "pier"), "run",
                       "--path", str(task_input.resolve()), "--env", "docker", "--model", budget.model,
                       "--agent-import-path", "scicontext.pier_agent:ScientificCodex",
                       "--no-force-build", "--no-delete", "--yes", "--n-concurrent", "1", "--n-attempts", "1",
                       "--max-retries", "0", "--agent-timeout-multiplier", str(total / 5400),
                       "--jobs-dir", str((output / "jobs").resolve()), "--job-name", f"task-{task}-{condition}"]
            for key, value in {"condition": condition, "total_seconds": total, "extraction_seconds": extract,
                               "reasoning_effort": budget.reasoning_effort, "codex_version": budget.codex_version,
                               "workspace": str(workspace), "auth_file": str(private_auth), "smoke": smoke}.items():
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
            with log.open("w") as stream:
                result = subprocess.run(command, env=environment, stdout=stream, stderr=subprocess.STDOUT, cwd=workspace)
            write_json(output / f"task-{task}-{condition}-receipt.json", {**item, "return_code": result.returncode, "finished_at": utc_now(), "runner_log_sha256": digest_file(log)})
            # Add final patch and provenance hashes without reading private assertion text.
            job = output / "jobs" / f"task-{task}-{condition}"
            found_records = list(job.rglob("run.json"))
            if not found_records:
                setup_record = {"schema_version": "1.0", **item,
                                "model": budget.model, "reasoning_effort": budget.reasoning_effort,
                                "codex_version": budget.codex_version,
                                "config": {"total_seconds": total, "extraction_seconds": extract},
                                "status": "infrastructure_failure", "stages": [],
                                "started_at": plan["started_at"], "finished_at": utc_now(),
                                "duration_seconds": None, "error": "No agent record; inspect preserved Pier setup/runner artifacts"}
                write_json(job / "setup-failure/run.json", setup_record)
                found_records = [job / "setup-failure/run.json"]
            for run_file in found_records:
                record = read_json(run_file)
                patch = run_file.parent / "artifacts/model.patch"
                record["patch_sha256"] = digest_file(patch) if patch.is_file() else None
                record["selection_sha256"] = receipt["selection_sha256"]
                record["config_sha256"] = plan["config_sha256"]
                record["release_commit"] = config["release_commit"]
                record["benchmark_revision"] = config["release_commit"]
                record["dataset_revision"] = config["dataset_revision"]
                record["runner_version"] = config["pier_version"]
                task_row = next(r for r in receipt["tasks"] if r["task_id"] == task)
                record["verifier_image"] = task_row["verifier_image"]
                write_json(run_file, record)
            if result.returncode or any(read_json(p).get("status") == "infrastructure_failure" for p in found_records):
                plan["status"] = "runner_failure"
                write_json(output / "schedule.json", plan)
                raise RuntimeError(f"Runner failed; retained {log}. Remaining schedule has not been executed.")
    plan["status"] = "completed"
    plan["finished_at"] = utc_now()
    write_json(output / "schedule.json", plan)
    from .results import write_summary
    return write_summary(output / "jobs", output / "summary")


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] in {"index", "cite", "expression", "checkpoint"}:
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
    for name in ("index", "cite", "expression", "checkpoint"):
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
        result = pilot(args.workspace.resolve(), args.config, args.output, args.execute, args.auth_file, args.smoke)
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
