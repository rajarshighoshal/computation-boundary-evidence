# Probe-first live check: scientific interpretation

The approved extraction-only check completed on the previously inspected geometry-reader and
storage development tasks. The frozen configuration is `configs/probe-first-check-v1.json` and
the evaluated commit is `1511cf7`. Neither the method nor the resource allocation changed during
execution. No repair, hidden verifier, retry or expanded evaluation ran.

Both first passes produced an evidence-linked claim and an inline probe which code actually
executed against the original repository. Both final handoffs retain the observed draft, including
the exact probe source and matching execution identity. The probes failed scientific assertions,
not imports, solver setup or their execution deadline. These failures are useful counterexamples
to the stated requirements, not repaired-task successes.

Exact outcomes, phase timing and token counts are generated from receipts in
[the main report](PROBE_FIRST_CHECK_V1.md), [runtime report](PROBE_FIRST_CHECK_V1_RUNTIME.md), and
`results/probe-first-check-v1-token-audit.json`. Raw results are under `runs/probe-first-check-v1`.

## Geometry reader

The expected relationship is deliberately an **inferred public-workflow requirement**: for a
fully periodic, zero-origin crystal, independently translating sites by integer lattice vectors
should preserve their basic-cell representatives. The public workflow requires in-cell fractional
coordinates; repository documentation supplies periodic reduction semantics and also states that
ordinary Structure construction can retain unwrapped positions.

The probe uses the real cube writer, reader and workflow. Known interior coordinates are its
reference, not output copied from the buggy reader. A skew-cell interior control succeeds; equivalent
periodic images remain unwrapped and fail the position/workflow condition. Species, lattice and
grid samples remain unchanged. The known-coordinate comparison distinguishes the requirement from
merely clipping coordinates to satisfy a bounds predicate. The helium warning is incidental.

This does not resolve the bundled input's nonzero-origin convention or establish a universal cube
format rule. Using the repository writer limits the covered input convention. The source entity
links are useful, but structural alignment remains unknown. A particular repair is not validated.

Sources and execution:

- `jobs/task-091-science/task_091__pr5DyGM/agent/extract_draft-final.txt`
- `jobs/task-091-science/task_091__pr5DyGM/agent/probe-round-1-results.json`
- `jobs/task-091-science/task_091__pr5DyGM/graph-bundle.json`

Paths above are relative to the raw run root. Source quotes, hashes and locations are retained in
the compiled graph. Independent review checked the original public workflow, periodic-site
semantics and cube writer/reader, then corroborated the executed script and final fingerprint.

## Storage boundary

The public energy-balance documentation and component definitions support the expected distinction:
noncyclic storage carries energy across chronology labels unless explicit resetting is enabled.
Changing the scope flag for cyclic behavior should not itself reset an otherwise noncyclic history.

The probe calls the actual Network.optimize API and HiGHS on an isolated Store/Load experiment.
Load fixes actual dispatch through balance, and unequal storage-duration weights exercise energy
accounting. The continuous control and explicit-reset control yield their respective expected
histories. Enabling cyclic scope while cyclic operation and resetting are disabled unexpectedly
produces the reset history. The solver completes normally before the scientific assertion fails.

All cases execute and print results before assertions begin. The first failed trajectory stops
later assertions, so do not describe every control as a completed assertion test; the saved numerical
outputs support their comparison.

The symbolic correspondence is weaker than the executable evidence: the proposed energy equation is
linked to the Boolean `per_period` expression rather than the energy-balance expression, and the
duration binding is unresolved. The reported unknown alignment must remain unknown.

Coverage excludes losses, inactive assets, StorageUnit, and the task's explicitly requested cyclic
precedence when both boundary conditions are enabled. A demand-only cyclic experiment may be
infeasible without replenishment; these cases require distinct valid constructions. This witness
does not establish complete task understanding or repair sufficiency.

Sources and execution, relative to the raw run root:

- `jobs/task-114-science/task_114__E5AXDXf/agent/extract_draft-final.txt`
- `jobs/task-114-science/task_114__E5AXDXf/agent/probe-round-1-results.json`
- `jobs/task-114-science/task_114__E5AXDXf/graph-bundle.json`

Independent review checked the public documentation excerpts, actual output, control construction,
and mechanical alignment limitations.

## Optional correction and cost limitations

Neither first interpretation nor probe execution timed out. Geometry's optional revision did time
out without a final annotation artifact; the observed draft remained selected. Storage's optional
revision was not attempted because the generated feedback exceeded the existing size cap. No
automatic retries were performed. The correction step did not improve either final handoff here.

The completed first-call token counts match their saved cumulative session counters. Geometry's
whole-extraction cost remains unknown because its attempted revision has no completed-turn usage;
the last observed partial counter is reported separately, never substituted as full cost. Storage's
skipped revision incurs no model-call entry. Cached input and reasoning are subsets, not additions.

Final schedule/run receipts establish completion; launch records describe the launch and may retain
their original in-progress status. Docker was idle after completion. No resource sampling was
performed during this check, so no peak-memory or parallel-speedup claim is supported.

## Research conclusion

The automatic first pass can now supply executable scientific evidence on these development cases,
rather than only describing a potential check. This is a feasibility result, not an estimate of
benchmark coverage, a causal comparison with earlier prompts, or evidence of improved repair.

The useful artifact is the scoped scientific expectation plus its real counterexample and controls.
The current structural graph and optional correction remain incomplete. A subsequent paired repair
comparison must keep these limitations and all costs visible; no larger comparison was launched by
this check.
