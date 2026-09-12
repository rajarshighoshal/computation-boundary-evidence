# Offline loci evaluation v1 (2026-09-12)

Execution-derived constraint structure on the five development tasks. Config and fix-touched sets predeclared in configs/loci-eval-v1.json; script scripts/eval_loci.py; receipts results/loci-eval-v1.json and runs/loci-eval-v1/.

## Per-task results (strengthened)

| Task | Instances | Violated loci | Hit | Hit level | Precision | Workflow flip |
|---|---|---|---|---|---|---|
| 009 DESC | 299 | 6 | yes | function+file | 0.50 | yes: workflow_completed under the verified patch; script-level distinctness and build_vacmet_inputs collapse loci disappear |
| 058 OpenMC | 14 (C++ core) | 1 | yes | file | 1.00 | yes: report -> post_fix_success |
| 091 pymatgen | 20,562 | 2 | no | - | 0.0 | yes: report pre_fix_expected_failure -> post_fix_success |
| 114 PyPSA | 6,257 | 3 | no | - | 0.0 | n/a: no passing patch (best 13/15) |
| 001 autochem | 912,877 | 7 | no | - | 0.0 | n/a: no passing patch (best 1/3) |

## What the evidence shows

- 009 is the full worked example: R1 sensitivity at build_projection_wall / build_external_region_payload / build_vacmet_inputs, R4 collapse between projection and scaled modes; the workflow flips and the collapse structure changes under the verified patch. The wall builder's local insensitivity persisting post-fix is by-design (the fix acts downstream) - the documented intended-vs-actual limit.
- 058 hits via the R6 completion locus carrying static candidates at lattice.cpp lines 274/276/279 - exactly the RectLattice::distance comparisons the verified patch rescales (FP_PRECISION -> FP_PRECISION * pitch). Static evidence was obtained by direct inspection of the preserved source (labeled); the in-pipeline native frontend (tree-sitter grammars in the helper deps) is a known gap.
- 091/058 flip at workflow level; 091 has no function-level localization (single-call workflow).
- 114/001: the scripts embed the violated constraints in their report observations even under nominal status - transition_across_label_boundary 1.5 (continuity violated) and signature_agreement false (invariance violated) are now recorded as script-declared constraint loci with the measured values. No function-level localization (the violating quantities are computed inside opaque third-party libraries).

## Stop-rule decision

Predeclared gate: at least 2 of {009, 001, 091} with function/file-level hits. Outcome: 1 of 3 (009). Per the stop rule, NO repair comparison was launched; the offline evaluation is the deliverable. Localization hits: 009 (function+file) and 058 (file, static evidence). Strengthening directions that remain: pipeline-wire the native frontends, parse 114's observation into provenance over the solver boundary, and bind 001's presentation comparison to producer instances.

## Method status

The extractor core is implemented and verified: trace_runtime (sys.monitoring / setprofile, structure fingerprints, report + stdout capture), proc_observer (universal tier), relations (R1-R7 + R6s/R6p observation constraints + scientific-pair precision filter), dynamic_binding (quantity graph + dependence signatures), the trace/packet/merge-dynamic helper chain wired into the science arm's prepare phase, and the predeclared eval. Suite: 469 tests.
