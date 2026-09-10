# Random-five comparison: qualitative observations

Posthoc, AI-assisted artifact review, separate from the programmatically generated quantitative
report. These observations were not supplied to evaluated agents and did not change the frozen
method, prompts, selection or budgets. They are candidate interpretations for Rajarshi to review,
not causal-effect claims.

## Task 091: coordinate-origin semantics

Both patches repair `VolumetricData.from_cube` by reading the cube grid origin and subtracting it
from atomic positions. Science subtracts in Bohr before conversion; baseline converts origin and
coordinates before subtraction. Both preserve lattice and scalar-field calculations. Neither
introduces an obvious unrelated production change; both add regression tests around translated
origins and volumetric-file behavior.

The science repair received the generated handoff and probe observations. Its translation tests
reuse a supplied probe origin, supporting guidance uptake, although its trajectory does not
explicitly attribute the diagnosis to the graph. It independently inspected the lattice calculation
before modifying coordinates. Baseline reached the same diagnosis from its own exploration.

The strongest treatment evidence here is the executed translation probe, not corroborated symbolic
implementation structure. The initial packet omitted the relevant `io/common.py`; source-size limits
also affected origin evidence. The final graph contains stale prose saying the probe was unexecuted
alongside the actual execution observation. Preserve and report this inconsistency; do not revise
the extractor mid-comparison to repair an outcome-observed limitation.

Evidence:

- `runs/random-five-v1/jobs/task-091-science/task_091__Pf5SuUn/artifacts/model.patch`
- `runs/random-five-v1/jobs/task-091-baseline/task_091__LrKVPML/artifacts/model.patch`
- Science `graph-bundle.json`, `agent/repair.jsonl`, and
  `agent/extract-scratch/probe-results/p_origin_translation/receipt.json` in its trial directory.
- Baseline `agent/repair.jsonl` in its trial directory.

Verifier outcomes, timings and coverage counts belong in the generated results report. Successful
guidance uptake alone does not establish incremental repair benefit.

## Task 058: handoff rejection during execution

The interpretation and code-owned assembly completed with a usable checkpoint. The source-change
receipt nevertheless lists a Git CRLF-to-LF warning for the vendored Catch2 PowerShell helper as
its sole `changed` entry, with no untracked files. The guard treats any returned diff text as a
source modification, so it rejected the graph and the trial continued the configured ordinary-repair
fallback with remaining time. This is evidence of a warning/filename parsing defect, not evidence
that extraction exceeded its deadline. The frozen comparison retains the rejected handoff and
its time cost. Do not silently repair the guard or rerun this arm after seeing the failure.

Evidence under `runs/random-five-v1/jobs/task-058-science/task_058__euvFCm3/`:

- `agent/extraction-source-check.json`
- `agent/extraction-phases.json` and `agent/assembly-initial.json`
- `run.json` records the `no_valid_graph` handoff status.

The original assembled candidate is not the same thing as a delivered scientific handoff. Keep
these separate when counting extraction coverage and interpreting treatment uptake.

Posthoc inspection of `agent/repair-sessions` confirms that fallback repair received only the
original task and remaining allowance, without scientific context. Both patches repair
`RectLattice::distance`: retain ray-to-face distances, select the minimum, and identify simultaneous
crossings using exact equality or relative distance tolerance instead of absolute coordinate
residuals. Both preserve negative distances and exclude the no-crossing sentinel. Baseline uses
explicit direction/finite-distance checks; fallback uses its distance-array minimum and sentinel
comparison. Both add focused C++ and offline transport tests and scientific rationale. Neither
shows obvious unrelated production changes. The fallback has broader geometric regression tests,
but this cannot establish an effect of graph guidance that it never received.

Baseline evidence: `runs/random-five-v1/jobs/task-058-baseline/task_058__XPkaL4J/artifacts/model.patch`.
Fallback evidence: `artifacts/model.patch` and `agent/repair-sessions` under its trial directory above.

## Task 009: relevant context, unresolved scientific definition

The medium-effort treatment receives source-linked distinctions between projection-wall
construction and VACMET interpolation, the discarded projection-gain input, and the need for
wall coordinates and derivatives to describe the same surface. It leaves the exact projection
formula, normalization and gain meaning unresolved. The snapshot's volume-related convention is
not presented as a normalized physical volume.

The corroborated interpolation expression lacks a corresponding scientific relation and operand
semantic anchors, so the mechanical component cannot resolve the central scientific construction.
No extraction probe was proposed. The absence-of-execution wording is therefore consistent here.

The repair engages with the missing definition, asks for clarification without receiving an answer,
then documents an implementation choice: normalize the physical radial tangent, project its
displacement into the meridional plane, and analytically differentiate that construction. Its
regression tests check internal geometric/derivative consistency and preserved behavior. A radial
tangent is not necessarily a surface normal; the displacement scaling and sign restrictions are
choices rather than definitions established by the supplied context. Thus verifier success alone
does not settle equivalence to a historical scientific formulation.

Evidence under `runs/random-five-medium-v1/jobs/task-009-science/task_009__hedEtB2/`:

- `agent/extract-scratch/annotations.json` and `graph-bundle.json`
- `agent/repair.jsonl` and `agent/repair-sessions`
- `artifacts/model.patch`

The completed baseline chooses a different construction: it displaces in the full physical radial
direction, converts back to cylindrical coordinates, and extends the downstream wall interface to
carry explicit toroidal phase and derivatives. Treatment keeps the original phase and projects the
displacement into its meridional plane. Both patches explicitly distinguish a radial tangent from
a general surface normal and add consistency tests. Their verified success therefore does not
establish that the benchmark uniquely identifies the missing scientific construction. Baseline's
larger interface change and treatment's narrower preserved interface are descriptive differences,
not a demonstrated causal effect of the handoff.

Baseline evidence:
`runs/random-five-medium-v1/jobs/task-009-baseline/task_009__NTZLvQJ/artifacts/model.patch`.

## Remaining checks: subscription quota, not a repair result

The medium continuation stopped when task 114's baseline received an explicit subscription
usage-limit error before any repair was completed. Its unknown outcome is not a verifier failure.
The remaining arms and task 001 were not launched. No API fallback or additional retry was used;
benchmark containers were cleaned up.

Exact provider error is preserved in
`runs/random-five-medium-v1/jobs/task-114-baseline/task_114__aZ4unEJ/agent/codex.txt`.
`schedule.json` and the generated medium report retain the failed launch and unrun work. Resume
only after model access is available or the user approves another route, using fresh output paths
and keeping the existing quota-failed receipt. Do not rerun the already-completed task 009 pair.
