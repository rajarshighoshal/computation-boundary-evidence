# Probe-first scientific extraction with optional feedback

Implementation approved by Rajarshi after the task001 diagnosis. This document describes the
mechanism; local tests do not establish better scientific understanding or repair outcomes.
The evaluated earlier method and its results remain unchanged and separately versioned.

## What reaches repair

The extractor now identifies scientific objects through source-derived entity IDs for parameters,
assignments, returned objects and selected container updates. These bindings identify code carriers;
they are separate from mathematical expression matching. Ambiguous locations stay unresolved, with
bounded inspected candidate IDs in diagnostics. An apparent container-method name does not prove
its runtime semantics. Scientific units, scales and shapes still need independent evidence.

Claims can carry `scientific_object`, `applicability`, `alternative_interpretation`,
`discriminating_observation` and selected `consumer_ids`, alongside the existing evidence and
explicit/inferred/unresolved status. These fields preserve the proposed interpretation, not a
formal proof of it. The prompt asks for public evidence capable of distinguishing meanings instead
of treating invariant outputs alone as sufficient.

## Bounded sequence

Code-owned preparation overlaps the draft interpretation. The first deliverable is one supported
scientific claim and a small executable check of the actual repository computation, with its
applicability and expected relationship grounded in public evidence. A diagnostic comparison may
leave the scientific expectation unresolved; if no useful probe is possible, the prompt requires
a specific evidence-backed explanation in `unresolved`. No oracle is invented to force coverage.
Code then assembles the draft, runs accepted probes and saves an observed draft checkpoint.
One optional revision receives the draft, binding diagnostics and actual probe receipts when
correction is indicated and time remains. New or changed probes are executed after revised assembly;
unchanged attempted probes are not automatically retried. There is no open-ended
refinement loop. Model access to task source remains native read-only; code-owned probes run using
the existing bounded subprocess executor in the disposable task environment.

The existing extraction and total-agent allowances are unchanged. The arbitrary 45-percent draft
allocation and mandatory correction pass are removed. `extraction_reserve()` leaves only code-owned
assembly/probe time after the first call, not a quota for a second model call. Initial assembly can
use all remaining work time; probe execution leaves room for observed assembly. Revision is skipped
when there is too little time for both the optional call and subsequent code work. Prompt deadlines
are earlier soft milestones within the actual CLI allowance, not additional process cutoffs. The outer
collection/shutdown reserve remains outside the work allowance. A valid draft survives an invalid
or ordinarily timed-out revision. Provider/execution failures are not treated as invitations for
another model call. Upstream execution, cancellation cleanup and artifact collection have bounded
waits; unfinished upstream I/O marks the trial fatal and prevents another model call even if a
draft exists. That fatal state survives outer phase/stage cancellation. This is not an exhaustive
detached-process supervision guarantee. See `WORK_LOG.md` for final verification status.

Probe identity includes its inline source and the accepted claim/quantity/evidence interpretation.
The runner records that identity and the script hash. Revised probes or revised meanings cannot
inherit an old execution result; unmatched final probes are explicitly unexecuted. Legacy receipts
remain readable without being upgraded to identity-verified results. A failed probe can expose the
original bug; neither an assertion failure nor exit zero establishes the truth of a scientific rule.

Repair receives selected probe source, corresponding execution status and uncertainties. If the
handoff size limit prevents source delivery, the omission is explicit. Repair is instructed to
recheck applicable probes within its allowance and may challenge inferred requirements with public
evidence. No additional final judge or unbudgeted repair pass is introduced.

## Artifacts and cost accounting

Top-level trial stages remain `extract` and `repair`. New extraction records contain ordered
`model_calls` for `extract_draft` and, when attempted, `extract_revision`. Each has distinct JSONL,
final/exit/process receipts and saved sessions. `selected_model_call` identifies the annotations
actually chosen for handoff. Draft and later assembly bundles are separate files.
Each probe call has separate `probe-round-N-specs.json`/`probe-round-N-results.json` files, and
each script/output/receipt lives in a unique directory under `extract-scratch/probe-results`.
Inline scripts with the same logical filename cannot overwrite another probe. `probe_rounds`
preserves every attempted interpretation; `probe_delivery` distinguishes retained probes with
actual execution receipts from unexecuted or absent probes. A citation-only valid graph is labelled
untested guidance, not an executed scientific check.

Extraction totals include every attempted call once. Input includes cached input, output includes
reasoning; neither subset is added again. Missing or incomplete attempted-call costs stay unknown.
Reports show leaf calls and their extraction aggregate without adding both into trial totals.
Legacy records without `model_calls` retain their original single-call interpretation. The separate
session audit corroborates each call before summing it.

## Verification boundary

Synthetic integration cases use the real index, assembler, public-probe executor and controller,
with deterministic model test doubles. They cover numerical and discrete-object interpretations,
failed probes on intentionally buggy public code, correction of unresolved bindings, stale-result
rejection, selected handoff content and combined usage. Unit tests cover source ambiguity, legacy
contracts, slow assembly, cancellation, fallback, native read-only call routing and log isolation.

This verifies implementation behavior—not whether a live LLM discovers useful scientific rules.
A separately approved, predeclared [extractor-only development check](SEMANTIC_FEEDBACK_CHECK_V1.md)
has now completed with mixed outcomes. [Its quality review](SEMANTIC_FEEDBACK_CHECK_V1_NOTES.md)
records useful geometry distinctions without probes and a storage draft timeout. It does not
establish improved repair performance or complete scientific understanding.
That check motivated the probe-first corrections above. Their local verification is recorded in
`results/probe-first-verification.json`. The subsequent approved
[probe-first live check](PROBE_FIRST_CHECK_V1.md) produced and executed scoped scientific probes
on both development tasks. [Its scientific review](PROBE_FIRST_CHECK_V1_NOTES.md) distinguishes
useful counterexamples from incomplete alignment and optional-correction failures. Repair benefit
and broader coverage were not established by that extraction-only check. The later
[bounded paired repair comparison](PROBE_FIRST_PAIRS_V1.md) found no improvement on these known
development tasks. [Its interpretation](PROBE_FIRST_PAIRS_V1_NOTES.md) identifies requirement
selection and scope transfer as concrete failures despite executed auxiliary probes.
Task001 is diagnostic-exposed; its hidden assertion and constructed diagnostic case are not included
in the new prompts or integration examples. No larger experiment is authorized by implementation.

The [recorded local verification](SEMANTIC_FEEDBACK_VERIFICATION.md) also preserves the initially
failed original-source coverage check and its fix. New entity entries share the existing cap across
referenced regions; adding parameters must not silently crowd out later relevant computations.

## Optional parallel execution

Config `concurrency` accepts one or two simultaneous trials. With two, full comparisons run a task's
baseline and treatment together and wait for both before moving to the next task. Extraction-only
checks group two selected tasks. Standard single-trial Pier processes, separate input copies and
receipts remain; provider/infrastructure failure cancels the active sibling and stops future
admission. Scientific test failure alone does not cancel the other arm. Shared asset-cache builders
use a process lock, and authentication stays alive until owned runners finish.

Concurrency counts trials, not containers. The Docker allocation is shared; per-task memory limits
do not reserve that memory. Local overlap/cancellation/cache tests pass, but actual scientific
container memory pressure and wall-clock speedup still need observation in the next approved check.
