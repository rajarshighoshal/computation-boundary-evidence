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
