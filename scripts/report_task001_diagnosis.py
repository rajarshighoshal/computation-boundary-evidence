#!/usr/bin/env python3
"""Generate the task001 posthoc diagnosis from preserved, no-model replay receipts."""
import collections
import hashlib
import json
import re
from pathlib import Path

from report_comparison import table


ROOT = Path(__file__).resolve().parents[1]


def main():
    run = ROOT / "runs/task001-diagnosis-v1"
    data = json.loads((run / "result.json").read_text())
    probe = ROOT / "scripts/diagnose_task001.py"
    if hashlib.sha256(probe.read_bytes()).hexdigest() != data["probe_sha256"]:
        raise ValueError("Probe script differs from the executed version")
    trial = ROOT / "runs/task-local-five-v2/jobs/task-001-science/task_001__nJayhq5"
    bundle = json.loads((trial / "graph-bundle.json").read_text())
    annotations = json.loads((trial / "agent/extract-scratch/annotations.json").read_text())
    failure, = data["posthoc_hidden_diagnostic_exposure"]["failures"]
    match = re.search(r"AssertionError: assert (\d+) == (\d+)", failure["message"])
    if not match:
        raise ValueError("Expected numeric assertion absent from saved diagnostic")
    observed, expected = map(int, match.groups())
    compact = {**data, "posthoc_hidden_diagnostic_exposure": {
        **{k: v for k, v in data["posthoc_hidden_diagnostic_exposure"].items() if k != "failures"},
        "test_name": failure["name"], "observed": observed, "expected": expected,
        "timing": "Inspected only after the completed comparison; historical pre-run metadata is unchanged."}}
    compact["extraction"] = {
        "retained_claims": len(bundle["graph"]["claims"]),
        "claim_quantity_links": sum(len(c["quantity_ids"]) for c in bundle["graph"]["claims"]),
        "alignment_statuses": dict(collections.Counter(a["status"] for a in bundle["analysis"]["alignments"])),
        "declared_probes": len(annotations.get("probes", []))}
    (ROOT / "results/task001-failure-diagnosis.json").write_text(json.dumps(compact, sort_keys=True, indent=2) + "\n")
    lines = ["# Task 001: posthoc failure diagnosis", "",
        "Diagnosis only: no method changes, new benchmark-agent attempts, or hidden-test execution. "
        "The saved hidden-test failure was inspected after the comparison; task001 remains development-exposed. "
        "This new exposure must not be backdated into historical run metadata.", "",
        "## Observed failure", "",
        f"Saved hidden test `{failure['name']}` expected rotational symmetry factor **{expected}**, "
        f"but treatment returned **{observed}**. The saved result is an assertion failure, not a timeout or out-of-memory error.", "",
        "The earlier public rotor-multiplicity difference did not establish this cause. The following "
        "separate counterexample tests a specific endpoint-selection mechanism; it does not reconstruct the hidden fixture.", "",
        "## Bounded public replay", "",
        "The probe constructs a pi-free CH3–C–C–OH chain with an extra H atom, either isolated or "
        "forming a bond to the internal carbon. It checks the far C–O axis in each reaction orientation. "
        "Original code and both hash-checked submitted patches run in separate disposable containers from "
        "the pinned environment image, without network, credentials or model calls.", ""]
    cases = {(r["condition"], c["transverse_h_addition"], c["reaction_reversed"]): c
             for r in data["records"] for c in r["cases"]}
    rows = []
    for added in (False, True):
        for reverse in (False, True):
            values = [cases[(arm, added, reverse)]["symmetry"] for arm in ("original", "baseline", "science")]
            rows.append(("transverse H addition" if added else "uninterrupted-line control",
                         "reverse" if reverse else "forward",
                         *(v.get("value", v.get("error")) for v in values)))
    table(lines, ["Case", "Orientation", "Original", "Baseline", "Context-assisted"], rows)
    table(lines, ["Patch", "Queried endpoints", "Endpoints actually used", "Rotational segments"],
        [(arm, cases[(arm, True, False)]["query_axis"],
          [cases[(arm, True, False)]["symmetry_locals_at_return"][k] for k in ("key1", "key2")],
          cases[(arm, True, False)]["rotational_segments"]["value"]) for arm in ("baseline", "science")])
    lines += ["Both patches retain the same extended linear path. The decisive difference in this probe "
        "is rotational-axis segmentation and endpoint selection: treatment substitutes a remote methyl cap, "
        "whereas baseline uses a nearer boundary at the transverse reference. The tracer observes function "
        "locals without modifying them. Original-code exception-unwind snapshots are failure-state locals, "
        "not successful returns.", "",
        "Baseline's value follows its local-axis rule; this graph-based probe is not an independent physical "
        "symmetry oracle. It corroborates the candidate mechanism, not the exact hidden fixture's execution. "
        "The original code crashes on the added-branch case: treatment removes the crash but still propagates "
        "the remote cap's symmetry. Thus this is incomplete semantic repair, not evidence that extraction "
        "necessarily introduced a previously absent bug.", "",
        "## Why the added context did not prevent it", ""]
    ex = compact["extraction"]
    table(lines, ["Extraction artifact", "Observed value"], list(ex.items()))
    lines += ["The handoff correctly emphasized exact presentation invariance, nonredundant collective axes, "
        "linearity in either reagent limit and reaction-orientation invariance. It explicitly left branching cap/neighbor geometry unresolved and "
        "distinguished signature length from a rotational symmetry factor. It did not supply an executable "
        "axis-locality condition capable of catching the observed endpoint substitution.", "",
        "The mechanical limits have concrete causes: source locators point to a function signature, append "
        "statements outside the expression index, an ambiguous assignment/return span, and an augmented "
        "assignment excluded by the resolver. The claims are prose with operation `other`; the one "
        "source-matched expression is an unsupported observation dictionary. A valid delivered graph "
        "therefore did not amount to validated scientific constraints.", "",
        "The repair received the handoff; its subsequent choices are consistent with several hints, "
        "but it also made independent design choices. "
        "This paired attempt cannot establish that context caused the bad choice. A matched ablation "
        "would be needed to attribute it to the handoff or a particular claim; none was run.", "",
        "## Research implication and limits", "",
        "Representation invariance is necessary here but insufficient: the same semantically inappropriate "
        "answer can remain stable under relabeling or reversal. The immediate gap is executable validation "
        "of scientific scope and downstream consumers, not a larger extraction timeout. Any next intervention "
        "must recover such constraints from public evidence rather than paste the revealed hidden assertion "
        "into a prompt. No fix or broader experiment was implemented during this diagnosis.", "",
        "Docker memory was raised after the original comparison; this replay is about functional behavior, "
        "not timing. The exact hidden graph's ordered caps were not retrieved, so that last fixture-specific "
        "attribution remains unverified.", "",
        "## Reproduction and evidence", "",
        "```bash", 
        ".venv/bin/python scripts/diagnose_task001.py --output runs/task001-diagnosis-reproduction",
        ".venv/bin/python scripts/report_task001_diagnosis.py", "```", "",
        "The report command reads the preserved original diagnostic directory; the replay requires a fresh "
        "output directory and does not invoke an agent.", "",
        "- Compact evidence: `results/task001-failure-diagnosis.json`.",
        "- Raw diagnostic stdout/stderr/commands: `runs/task001-diagnosis-v1/`.",
        "- Treatment patch: `runs/task-local-five-v2/jobs/task-001-science/task_001__nJayhq5/artifacts/model.patch`, symmetry hunk and neighbor pairing.",
        "- Baseline patch: `runs/task-local-five-v2/jobs/task-001-baseline/task_001__GGfH99H/artifacts/model.patch`, axis segmentation and symmetry lookup.",
        "- Treatment `graph-bundle.json`, `agent/extract-scratch/annotations.json`, `agent/repair.jsonl` and saved repair session.",
        "- Saved hidden failure: treatment `verifier/junit.xml` and `verifier/test-stdout.txt`; no hidden source fixture was retrieved.",
        "- Resolver behavior: `src/scicontext/annotations.py`, the `binding` method.", ""]
    target = ROOT / "docs/TASK001_FAILURE_DIAGNOSIS.md"
    target.write_text("\n".join(lines))
    print(f"Generated {target.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
