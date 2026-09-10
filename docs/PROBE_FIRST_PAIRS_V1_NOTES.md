# Bounded repair comparison: interpretation

The frozen comparison in `configs/probe-first-pairs-v1.json` completed with no method changes,
retries or task replacements. Geometry and storage were known development cases selected before
this comparison's outcomes, not an untouched or representative evaluation set. Each task's
baseline and treatment ran concurrently; the next task waited for the preceding pair to finish.

[Official outcomes, timings and stage-by-stage costs](PROBE_FIRST_PAIRS_V1.md) are generated from
`results/probe-first-pairs-v1.json`, independently reconstructed from raw trial receipts. The
separate session-counter audit is `results/probe-first-pairs-v1-token-audit.json`.

The result is negative for this configuration: baseline succeeds on geometry, while treatment
does not; neither solves storage completely. There is no observed repair benefit in this bounded
comparison. The sample does not support a general effect estimate or a causal claim about graphs.

## Geometry: an executable probe can test the wrong requirement

The baseline subtracts the cube header's shared grid origin from atomic coordinates. Its tests
explicitly preserve coordinates outside the cell rather than wrapping them. The treatment instead
adds `to_unit_cell=True`; it never reads the cube origin. Its new tests concentrate on zero-origin
periodic-image canonicalization.

The supplied scientific probe is not vacuous: it exercises the real reader and public workflow,
distinguishes translated periodic images from an interior control, and checks that lattice,
species and grid samples are preserved. The treatment reruns its logic after repair, with changed
execution setup but retained cases and assertions, and the recorded checks pass. Nevertheless,
official verification rejects the treatment patch.

The failure concerns requirement selection and application. The extracted claim is explicitly
inferred and restricted to zero-origin periodic inputs. Public documentation permits unwrapped
periodic sites, and the reproduction documentation limits the smoke example's specification
coverage. A failed periodic-image check does not establish that wrapping is the missing cube
reader behavior. The repair both leaves origin handling unresolved and applies wrapping more
broadly than the claim's stated scope.

The patch and visible trajectory closely follow the supplied hypothesis. This supports a
hypothesis-consistent failure interpretation, not proof that guidance caused the failure or that
the graph itself was responsible. The exact private assertions were not needed or inspected for
this analysis; aggregate official outcomes do not reveal every private requirement.

Key evidence under `runs/probe-first-pairs-v1`:

- `jobs/task-091-baseline/task_091__x5zweVn/artifacts/model.patch`
- `jobs/task-091-science/task_091__kHGMADp/agent/extract_draft-final.txt`
- `jobs/task-091-science/task_091__kHGMADp/agent/probe-round-1-results.json`
- `jobs/task-091-science/task_091__kHGMADp/agent/repair.jsonl`
- `jobs/task-091-science/task_091__kHGMADp/artifacts/model.patch`

## Storage: a valid narrow witness does not establish complete repair

The energy-continuity claim is supported by public storage equations and component definitions.
The probe executes real optimization and exposes an artificial boundary reset when cyclic
operation and explicit initial-state resetting are disabled. It does not test simultaneous
cyclic/reset precedence, nonunit snapshot weights, inactive assets or StorageUnit behavior.

Both repairs address the observed flag interaction and Store scenario-axis alignment. They differ
on global cycling combined with an initial-per-period flag: the baseline selects period resetting,
whereas treatment retains global cycling. Both require the main cyclic flag before per-period
cycling takes precedence. This interpretation should be compared carefully with the task's public
precedence wording; self-authored tests do not independently settle it.

Treatment tests go beyond the supplied probe to actual optimization across boundary-flag and
scenario configurations. Baseline tests primarily inspect constructed equations, alongside solved
discharge cases. Treatment also adjusts active-asset selection and a contradictory power-sign
docstring. Their passing local checks do not establish complete correctness: official verification
rejects both patches. Equal pass counts are not proof of identical failed assertions.

The treatment's auxiliary-probe rerun is corroborated: its copied source hash matches the extracted
probe, and saved execution produces the expected continuous histories. This is useful verification
of the narrow repair behavior, not evidence that the remaining requirements were handled.

Key evidence under the raw run root:

- `jobs/task-114-baseline/task_114__vpokiQx/artifacts/model.patch`
- `jobs/task-114-science/task_114__Tf6mqHJ/agent/extract_draft-final.txt`
- `jobs/task-114-science/task_114__Tf6mqHJ/agent/probe-round-1-results.json`
- `jobs/task-114-science/task_114__Tf6mqHJ/agent/repair.jsonl`
- `jobs/task-114-science/task_114__Tf6mqHJ/artifacts/model.patch`

## Accounting and interpretation limits

Completed calls' input, cached-input, output and reasoning counters match independent saved-session
audits. Cached input and reasoning are already included in their respective parent totals. Storage
treatment uses more total tokens than baseline; the generated report gives the exact comparison.

Geometry's optional revision timed out. Unlike the preceding extraction-only check, this call
recorded a completed-turn usage event matching a saved cumulative counter, but its overall timeout
status still prevents certifying full-call cost under the frozen accounting rule. Those observed
values remain in raw receipts; the full extraction/treatment total stays unknown, not zero. The
observed draft and its probe survived, and repair completed normally. Storage's optional revision
was unattempted because feedback exceeded the existing size cap.

The same method, prompts, model effort, image pins and allowances were used throughout this
comparison. The Docker allocation was shared, not a per-trial memory reservation. No peak-memory
or matched serial-speedup claim is supported. The generated report excludes development-assistant
and posthoc-review tokens; it measures benchmark-agent calls, not a monetary API bill.

All final schedule/run receipts are terminal and Docker was idle after completion. Earlier runs
remain separate, and no further comparison or method revision was launched.

The actionable research finding is that source traceability, a scientifically plausible relation,
and a discriminating executable check are insufficient by themselves: the relation must also be
the right requirement for the task, and its applicability must survive the repair handoff.
