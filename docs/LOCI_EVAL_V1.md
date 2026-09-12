# Offline loci evaluation v1 (2026-09-12)

Execution-derived constraint structure on the five development tasks. Config and fix-touched sets predeclared in configs/loci-eval-v1.json; script scripts/eval_loci.py; receipts results/loci-eval-v1.json and runs/loci-eval-v1/.

## Per-task results

| Task | Instances | Violated loci | Hit | Hit level | Precision | Workflow flip |
|---|---|---|---|---|---|---|
| 009 DESC | 299 | 6 | yes | function+file | 0.50 | yes: workflow_completed under the verified patch; script-level distinctness and build_vacmet_inputs collapse loci disappear |
| 091 pymatgen | 20,562 | 2 | no | - | 0.0 | yes: report pre_fix_expected_failure -> post_fix_success |
| 058 OpenMC | 14 (C++ core) | 0 | no | - | - | yes: report -> post_fix_success (process level; compiled core behind a subprocess) |
| 114 PyPSA | 6,257 | 2 | no | - | 0.0 | n/a: no passing patch (best 13/15) |
| 001 autochem | 912,877 | 6 | no | - | 0.0 | n/a: no passing patch (best 1/3) |

## What the evidence shows

- Task 009 is a full worked example: R1 sensitivity loci at build_projection_wall / build_external_region_payload / build_vacmet_inputs (projection_gain has no effect on the wall arrays; the fix routes the gain downstream), R4 collapse between projection and scaled modes; the workflow flips under the verified patch. The wall-builder's local insensitivity persisting post-fix is by-design (the fix acts downstream) — a documented semantic limit, exactly the "intended vs actual" distinction the representation is built for.
- 091/058 flip only at workflow level: the reproduce report encodes the constraint (pre_fix -> post_fix), but the relation layer produces no function-level localization for them (single-call workflow for 091; compiled core for 058).
- 114/001 have no passing patch; their reproduce scripts report workflow_completed while embedding the failing observation values, so the script-status constraint layer does not fire. Localization misses are reported as-is.

## Stop-rule decision

Predeclared gate: at least 2 of {009, 001, 091} with function/file-level hits. Outcome: 1 of 3 (009). Per the stop rule, NO repair comparison was launched. The offline evaluation is the deliverable; a repair comparison would require strengthening localization on at least one more task first (known directions: observation-value parsing for 114's boundary jump and 001's signature presentations; R9 static candidates for 058's lattice.cpp).

## Method status

The extractor core is implemented and verified: trace_runtime (sys.monitoring / setprofile, structure fingerprints, script reports), proc_observer (universal tier), relations (R1-R7 with scientific-pair precision filter), dynamic_binding (quantity graph + dependence signatures), the trace/packet/merge-dynamic helper chain wired into the science arm's prepare phase, and the predeclared eval. Suite: 469 tests. Suite gates, receipts, and the predeclared eval protocol are preserved for the report.
