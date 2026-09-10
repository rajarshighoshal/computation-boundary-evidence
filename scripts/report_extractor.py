#!/usr/bin/env python3
"""Generate extraction-only verification records from preserved artifacts."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path


def read(path):
    return json.loads(path.read_text())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", type=Path, default=Path("runs/extractor-annotations-v1"))
    parser.add_argument("--json-output", type=Path, default=Path("results/extractor-annotations-v1.json"))
    parser.add_argument("--markdown-output", type=Path, default=Path("docs/EXTRACTOR_VERIFICATION.md"))
    args = parser.parse_args(argv)
    root = args.run_root
    # Round-aware runs use the current report contract; retain this script's
    # historical verification output for old single-round artifacts.
    if any("probe_rounds" in stage for path in (root / "jobs").glob("*/*/run.json")
           for stage in read(path).get("stages", [])):
        from report_task_local_extractor import main as report_current
        return report_current(["--run-root", str(root), "--json-output", str(args.json_output),
                               "--markdown-output", str(args.markdown_output)])
    subprocess.run([sys.executable, str(Path(__file__).with_name("recompute_results.py")),
                    str(root / "jobs"), "--verify", str(root / "summary/summary.json")], check=True)
    schedule = read(root / "schedule.json")
    if schedule["kind"] != "extraction_verification" or schedule["status"] != "completed":
        raise ValueError("Expected a completed extraction-only schedule")
    records = []
    for path in sorted((root / "jobs").glob("*/*/run.json")):
        trial, run = path.parent, read(path)
        if not run.get("extraction_only") or [s["name"] for s in run["stages"]] != ["extract"]:
            raise ValueError("Unexpected repair or missing extraction-only marker")
        if (trial / "verifier/reward.json").exists():
            raise ValueError("Private verification should be disabled")
        stage, bundle = run["stages"][0], read(trial / "graph-bundle.json")
        source = read(trial / "agent/extraction-source-check.json")
        digest = hashlib.sha256(json.dumps(bundle["graph"], sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
        if digest != bundle["graph_sha256"] or digest != run["graph_sha256"]:
            raise ValueError("Graph hash mismatch")
        phases = {p["name"]: p for p in stage["phases"]}
        prepare, interpret = phases["prepare"], phases["interpret"]
        overlap = max(0, min(p["started_offset_seconds"] + p["duration_seconds"] for p in (prepare, interpret))
                      - max(p["started_offset_seconds"] for p in (prepare, interpret)))
        final = (trial / "agent/extract-final.txt").read_text().strip()
        probes = read(trial / "agent/extract-scratch/probe-results.json").get("results", []) if (trial / "agent/extract-scratch/probe-results.json").exists() else []
        for probe in probes:
            artifact = trial / "agent/extract-scratch" / probe["artifact"]
            if read(artifact) != probe:
                raise ValueError("Probe receipt mismatch")
            script = artifact.parent / "script.py"
            if probe["script_sha256"] and hashlib.sha256(script.read_bytes()).hexdigest() != probe["script_sha256"]:
                raise ValueError("Executed probe script changed")
        verified = (run["status"] == "completed" and run["extraction_status"] == "usable_graph"
                    and interpret["status"] == "completed" and not source["source_changed"]
                    and prepare["status"] == "ready" and bundle["validation"]["valid"]
                    and stage["usage"].get("completed_turns") == 1
                    and final == "annotations.json" and run["duration_seconds"] <= run["config"]["extraction_seconds"])
        records.append({"task_id": run["task_id"], "verified": verified,
                        "duration_seconds": run["duration_seconds"], "interpretation_seconds": interpret["duration_seconds"],
                        "phase_overlap_seconds": overlap, "phases": stage["phases"],
                        "claims": len(bundle["graph"]["claims"]), "quantities": len(bundle["graph"]["quantities"]),
                        "source_changed": source["source_changed"], "final_response": final,
                        "usage": stage["usage"], "probe_statuses": [p["status"] for p in probes],
                        "probe_assertion_failures": sum(p["status"] == "failed" and "AssertionError" in p.get("stderr_excerpt", "") for p in probes),
                        "graph_sha256": digest, "trial_path": trial.relative_to(root).as_posix()})
    output = {"kind": "extraction_verification", "implementation_revision": schedule["implementation_revision"],
              "config_sha256": schedule["config_sha256"], "prompt_sha256": schedule["prompt_sha256"],
              "extraction_seconds": schedule["config"]["extraction_seconds"], "records": records,
              "all_verified": bool(records) and all(r["verified"] for r in records)}
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(json.dumps(output, indent=2, sort_keys=True, allow_nan=False) + "\n")
    lines = ["# Bounded extractor verification", "",
             f"Verified extraction-only runs: {sum(r['verified'] for r in records)}/{len(records)}. "
             f"The cap remained {output['extraction_seconds']} seconds per task. No repair sessions or private verifiers ran.", "",
             "| Task | Total seconds | Interpretation seconds | Claims | Source changed | Finished cleanly |",
             "| --- | ---: | ---: | ---: | --- | --- |"]
    for r in records:
        lines.append(f"| {r['task_id']} | {r['duration_seconds']:.2f} | {r['interpretation_seconds']:.2f} | {r['claims']} | {r['source_changed']} | {r['verified']} |")
    probe_count = sum(len(r["probe_statuses"]) for r in records)
    assertion_count = sum(r["probe_assertion_failures"] for r in records)
    lines += ["", "The final model responses were short annotation-file identifiers, not duplicate graphs. Code resolved source evidence, assembled and checked the graphs, and ran declared probes. "
              "Preparation overlapped interpretation-session startup/execution. Multi-probe concurrency is covered by tests; these live checks each selected a single probe.", "",
              f"Executed probes: {probe_count}; assertion failures against the original implementations: {assertion_count}. Numeric output and traces are preserved in the handoff. "
              "These are candidate scientific counterexamples, not an automatic proof that every extracted claim or probe is correct.", "",
              "Completed-turn usage was available for these interpretation sessions. This verifies completion and artifact handling; it does not measure repair success, "
              "nor establish an end-to-end improvement over the earlier pilot.", "",
              f"Evaluated implementation: `{output['implementation_revision']}`. Raw records: `{root}`. "
              "A subsequent small controller fix reserves/bounds shutdown time; that exception path is covered by synthetic deadline tests, not a new model run.", "",
              "[Machine-readable verification](../results/extractor-annotations-v1.json). Quantitative text is generated from checked receipts.", "",
              "```bash", "uv run --no-sync python scripts/report_extractor.py", "```"]
    args.markdown_output.write_text("\n".join(lines) + "\n")
    print(json.dumps({"all_verified": output["all_verified"], "records": len(records), "report": str(args.markdown_output)}))


if __name__ == "__main__":
    main()
