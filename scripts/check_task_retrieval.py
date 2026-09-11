#!/usr/bin/env python3
"""Offline retrieval regression on original public images; no models or candidate execution."""
import argparse
import json
from pathlib import Path
import subprocess
import shlex
import tarfile
import time

from scicontext.io import digest_file, write_json
from scicontext.packet import build_packet
from scicontext.object_context import enrichment_input
from scicontext.scientific_objects import extract_objects


# Development regression targets from the already-inspected public workflows,
# not rules used by the extractor or an untouched evaluation selection.
TARGETS = {
    "051": ["MakeMagGridDH", "MakeMagGradGridDH", "MakeGravGradGridDH"],
    "025": ["OspreyFit", "osp_fitMEGA", "osp_fitHERMES", "osp_addDiffMMPeaks", "OspreyQuantify", "quantH2O"],
    "016": ["bedGraphTrackI.refine_peaks"],
}
CORE_REGIONS = {
    "016": [("source/MACS3/Signal/BedGraph.py", 702, 706, "candidate_signal_overlap")],
    "025": [("source/libraries/FID-A/fitTools/fitModels/Osprey/osp_addDiffMMPeaks.m", 12, 18, "reference_area_scaling"),
            ("source/quantify/OspreyQuantify.m", 237, 243, "caller_timing_conversion"),
            ("source/quantify/OspreyQuantify.m", 587, 590, "callee_timing_conversion")],
    "051": [("source/src/MakeMagGradGridDH.f95", 632, 700, "tensor_output_construction")],
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-receipt", type=Path, default=Path("data/scientific-reading-v1-release.json"))
    parser.add_argument("--cache", type=Path, default=Path(".cache/public-workspaces"))
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--guest-check", action="store_true", help="Also run the existing packet helper in the pinned guest, without models")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    release = json.loads(args.release_receipt.read_text())
    if not args.prepare_only:
        if args.output is None:
            parser.error("--output is required unless --prepare-only")
        args.output.mkdir(parents=True, exist_ok=False)
    results = []
    for row in release["tasks"]:
        task, image = row["task_id"], row["environment_image"]
        assert row["restricted_license"].lower() == "false"
        destination = args.cache / (task + "-" + image.split("sha256:")[1][:12])
        root = destination / "task"
        receipt = destination / "receipt.json"
        if not receipt.exists():
            destination.mkdir(parents=True, exist_ok=False)
            archive_path = destination / "public.tar"
            with archive_path.open("wb") as stream:
                subprocess.run(["docker", "run", "--rm", "--network", "none", "--platform", "linux/amd64",
                    "--entrypoint", "tar", image, "-C", "/app/task_" + task, "--exclude=.git", "-cf", "-", "."],
                    stdout=stream, check=True)
            root.mkdir()
            with tarfile.open(archive_path) as archive:
                archive.extractall(root, filter="data")
            write_json(receipt, {"task_id": task, "image": image, "archive_sha256": digest_file(archive_path),
                "scope": "Full public task files excluding Git metadata; no candidate execution", "model_calls": 0})
        assert json.loads(receipt.read_text())["image"] == image
        print(task, "public workspace ready", flush=True)
        if args.prepare_only:
            continue
        started = time.monotonic()
        context = args.output / task / "context"
        context.mkdir(parents=True)
        (context / "task_statement.md").write_bytes((Path("data/release/tasks") / ("task_" + task) / "instruction.md").read_bytes())
        packet = build_packet(root, context, multilingual=True)
        graph = extract_objects(root, packet)
        interfaces = [o for o in graph["objects"] if o["kind"] == "code_interface"]
        targets = {}
        for target in TARGETS.get(task, []):
            parts = target.split(".")
            matches = [o for o in interfaces if all("." + p + "@" in o["scope"] for p in parts) and
                       not o["properties"].get("interface", {}).get("declaration_only")]
            targets[target] = [{"object_id": o["id"], "path": o["path"], "scope": o["scope"],
                "body_operations": sum(op["source"]["path"] == o["path"] and
                    (op["source"]["scope"] == o["scope"] or op["source"]["scope"].startswith(o["scope"] + ".")) for op in graph["operations"]),
                "incoming_source_reference_links": sum(l["target"] == o["id"] and l["relation"] == "possible_callee_interface" for l in graph["links"])} for o in matches]
            for match in targets[target]:
                match["operation_excerpts"] = [{"line": op["source"]["start_line"], "kind": op["kind"]}
                    for op in graph["operations"] if op["source"]["path"] == match["path"] and op["source"]["scope"] == match["scope"]]
        write_json(args.output / task / "packet.json", packet)
        write_json(args.output / task / "objects.json", graph)
        write_json(args.output / task / "reader-input.json", enrichment_input(graph, packet))
        regions = []
        for path, start, end, label in CORE_REGIONS.get(task, []):
            operations = [{"id": op["id"], "line": op["source"]["start_line"], "kind": op["kind"]}
                for op in graph["operations"] if op["source"]["path"] == path and start <= op["source"]["start_line"] <= end]
            statements = [o["id"] for o in graph["objects"] if o["kind"] == "source_statement" and
                          o["path"] == path and start <= o["source_span"]["start_line"] <= end]
            regions.append({"label": label, "path": path, "start_line": start, "end_line": end,
                "operations": operations, "source_statement_ids": statements,
                "scope": "Public-source region presence, not correctness or complete dataflow"})
        result = {"task_id": task, "seconds": time.monotonic() - started, "targets": targets,
                  "entries": len(packet["entries"]), "coverage": graph["coverage"],
                  "reader_input_bytes": (args.output / task / "reader-input.json").stat().st_size,
                  "scientific_region_evidence": regions}
        if args.guest_check:
            from scicontext.assets import prepare_helpers
            probe = subprocess.run(["docker", "run", "--rm", "--network", "none", "--platform", "linux/amd64",
                "--entrypoint", "bash", image, "-lc", "python -c 'import sys; print(str(sys.version_info.major)+str(sys.version_info.minor))'"],
                capture_output=True, text=True, check=True)
            python_minor = probe.stdout.strip()
            dependencies = prepare_helpers(Path(".cache"), python_minor).resolve()
            guest = (args.output / task / "guest").resolve()
            guest.mkdir()
            command = ["docker", "run", "--rm", "--network", "none", "--platform", "linux/amd64",
                "-v", str(Path("src").resolve()) + ":/opt/scicontext/src:ro",
                "-v", str(dependencies) + ":/opt/scicontext/deps:ro",
                "-v", str(context.resolve()) + ":/opt/scicontext/context:ro",
                "-v", str(guest) + ":/tmp/scicontext-check", "-w", "/opt/scicontext",
                "-e", "PYTHONPATH=/opt/scicontext/src:/opt/scicontext/deps", "-e", "PYTHONDONTWRITEBYTECODE=1",
                "--entrypoint", "timeout", image, "--kill-after=2s", "27s", "python", "-m", "scicontext.tool_cli", "packet",
                "--root", "/app/task_" + task, "--context-root", "/opt/scicontext/context", "--task-id", task,
                "--output", "/tmp/scicontext-check/packet.json", "--catalog", "/tmp/scicontext-check/catalog.md",
                "--objects-output", "/tmp/scicontext-check/objects.json", "--enrichment-input", "/tmp/scicontext-check/reader-input.json"]
            # Match Pier's login-shell environment (including the task's Python
            # environment), not the image's bare Docker-entrypoint PATH.
            index = command.index("python")
            command[index:] = ["bash", "-lc", shlex.join(command[index:])]
            beginning = time.monotonic()
            completed = subprocess.run(command, capture_output=True, text=True)
            (guest / "stdout.log").write_text(completed.stdout)
            (guest / "stderr.log").write_text(completed.stderr)
            result["guest_check"] = {"command": command, "exit_code": completed.returncode,
                                     "seconds": time.monotonic() - beginning, "python_minor": python_minor,
                                     "helper_cap_seconds": 27, "model_calls": 0}
        results.append(result)
        write_json(args.output / "receipt.json", {"model_calls": 0, "kind": "posthoc_public_workflow_regression",
            "scope": "Interface and partial-body retrieval, not scientific-core coverage or repaired semantic alignment",
            "implementation_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
            "source_hashes": {str(p): digest_file(p) for p in sorted(Path("src/scicontext").glob("*.py"))}, "results": results})
        print(json.dumps({k: result[k] for k in ("task_id", "seconds", "entries", "targets")}), flush=True)


if __name__ == "__main__":
    main()
