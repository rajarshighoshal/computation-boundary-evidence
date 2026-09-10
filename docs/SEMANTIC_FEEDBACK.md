# Scientific extraction with one feedback revision

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

Code-owned preparation overlaps the draft interpretation. Code then assembles the draft, runs
accepted public probes and can save an observed draft checkpoint. One short revision receives the
draft, binding diagnostics and actual probe receipts before final assembly. There is no open-ended
refinement loop. Model access to task source remains native read-only; code-owned probes run using
the existing bounded subprocess executor in the disposable task environment.

The existing extraction and total-agent allowances are unchanged. The pipeline reserves revision
and final-assembly time before starting the draft; unused earlier time can flow forward. The outer
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
