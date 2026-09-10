#!/usr/bin/env python3
"""Replay a public, posthoc axis-locality counterexample without agents or hidden tests."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path


def serial(value):
    if isinstance(value, dict):
        return {str(k): serial(v) for k, v in value.items()}
    if isinstance(value, (set, frozenset)):
        return [serial(v) for v in sorted(value)]
    if isinstance(value, (list, tuple)):
        return [serial(v) for v in value]
    return value


def observe(callback):
    try:
        return {"status": "ok", "value": serial(callback())}
    except Exception as error:
        return {"status": "error", "error": f"{type(error).__name__}: {error}"}


def container_probe(patch):
    if patch:
        subprocess.run(["git", "apply", patch], check=True)
    sys.path.insert(0, "/app/task_001/source")
    from automol import graph

    result = []
    # This is an independently constructed public probe, NOT the hidden fixture.
    # Start with CH3-C#C-OH in the library's pi-free graph representation. Add H
    # transversely at the internal carbon, preserving the same atom inventory.
    for addition in (False, True):
        edges = [(0, 1, 1), (1, 2, 1), (2, 3, 1)]
        if addition:
            edges.append((1, 4, 0.1))
        gra = graph.from_data(dict(enumerate("CCCOH")),
            [frozenset(e[:2]) for e in edges],
            atm_imp_hyd_dct=dict(enumerate([3, 0, 0, 1, 0])),
            bnd_ord_dct={frozenset(e[:2]): e[2] for e in edges})
        gra = graph.explicit(gra)
        for reverse in (False, True):
            current = graph.ts.reverse(gra) if reverse else gra
            snapshot = {}

            def trace(frame, event, arg):
                if frame.f_code is not graph.rotational_symmetry_number.__code__:
                    return None
                if event == "return":
                    for key in ("key1", "key2", "axis_keys", "lin_keys_lst", "ngb_keys_dct", "imp_hyd_dct"):
                        if key in frame.f_locals:
                            snapshot[key] = serial(frame.f_locals[key])
                return trace

            sys.settrace(trace)
            try:
                symmetry = observe(lambda: graph.rotational_symmetry_number(current, 2, 3))
            finally:
                sys.settrace(None)
            result.append({"transverse_h_addition": addition, "reaction_reversed": reverse,
                "query_axis": [2, 3], "symbols": serial(graph.atom_symbols(current)),
                "linear_atoms": observe(lambda: graph.linear_atom_keys(current)),
                "extended_linear_paths": observe(lambda: graph.linear_segments_atom_keys(current, extend=True)),
                "rotational_segments": observe(lambda: graph.rotational_segment_keys(current)),
                "symmetry": symmetry, "symmetry_locals_at_return": snapshot})
    print(json.dumps({"cases": result}, sort_keys=True))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def host_probe(output):
    root = Path(__file__).resolve().parents[1]
    output.mkdir(parents=True, exist_ok=False)
    summary = json.loads((root / "results/task-local-five-v2.json").read_text())
    rows = {row["condition"]: row for row in summary["trials"] if row["task_id"] == "001"}
    image = rows["baseline"]["provenance"]["environment_image"]
    records = []
    for condition in ("original", "baseline", "science"):
        name = "scicontext-diagnose-001-" + condition + "-" + uuid.uuid4().hex[:8]
        command = ["docker", "run", "--rm", "--name", name, "--network", "none",
                   "--platform", "linux/amd64", "--memory", "8g", "--cpus", "2",
                   "--workdir", "/app/task_001", "--volume", f"{Path(__file__).resolve()}:/diagnose.py:ro"]
        patch = None
        if condition != "original":
            patch = root / "runs/task-local-five-v2/jobs" / rows[condition]["trial_path"] / "artifacts/model.patch"
            if digest(patch) != rows[condition]["patch_sha256"]:
                raise ValueError("Saved patch hash mismatch")
            command += ["--volume", f"{patch}:/candidate.patch:ro"]
        command += ["--entrypoint", "timeout", image, "--kill-after=5s", "90s",
                    "python", "/diagnose.py", "--in-container"]
        if patch:
            command += ["--patch", "/candidate.patch"]
        (output / f"{condition}-command.json").write_text(json.dumps(command, indent=2) + "\n")
        try:
            process = subprocess.run(command, capture_output=True, text=True, timeout=120)
        except subprocess.TimeoutExpired:
            subprocess.run(["docker", "rm", "-f", name], capture_output=True, text=True, timeout=20)
            raise
        (output / f"{condition}-stdout.json").write_text(process.stdout)
        (output / f"{condition}-stderr.txt").write_text(process.stderr)
        if process.returncode:
            raise RuntimeError(f"{condition} probe failed with exit {process.returncode}; see preserved output")
        records.append({"condition": condition, "patch_sha256": digest(patch) if patch else None,
                        **json.loads(process.stdout)})
    trial = root / "runs/task-local-five-v2/jobs" / rows["science"]["trial_path"]
    junit = trial / "verifier/junit.xml"
    failures = [{"name": case.get("name"), "message": case.find("failure").get("message")}
                for case in ET.parse(junit).iter("testcase") if case.find("failure") is not None]
    result = {"kind": "posthoc_public_counterexample_not_benchmark_attempt", "image": image,
              "probe_sha256": digest(Path(__file__)), "records": records,
              "posthoc_hidden_diagnostic_exposure": {"task_id": "001", "junit_sha256": digest(junit),
                  "source": str(junit.relative_to(root)), "failures": failures},
              "limits": "Constructed public case, not reconstruction of the hidden fixture; no hidden tests or model calls executed. Docker allocation differs from the original comparison; no timing comparison."}
    (output / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    for row in records:
        print(row["condition"], [(c["transverse_h_addition"], c["reaction_reversed"], c["symmetry"])
                                 for c in row["cases"]])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--in-container", action="store_true")
    parser.add_argument("--patch")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.in_container:
        container_probe(args.patch)
    elif args.output:
        host_probe(args.output)
    else:
        parser.error("Provide --output for a fresh diagnostic output directory")


if __name__ == "__main__":
    main()
