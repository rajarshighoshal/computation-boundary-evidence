# Proposed revision: scientific meaning with grounded, testable conditions

Status: proposal only, following the task001 diagnosis. Not approved or implemented.
`WORK_LOG.md` is the canonical status ledger; the currently approved method remains unchanged.

## Target

Recover a small amount of task-specific scientific meaning that can constrain repair: what the
scientific object is, what code represents it, which conditions make an operation meaningful,
and what observable behavior would contradict that interpretation. This is not a claim of full
scientific understanding or a guarantee that every task supplies enough information.

## What is already present

`prompts/extract.md` already requests meaning, assumptions, evidence, source references and optional
probes. `annotations.py` assembles these, and `extraction.py` runs probes after interpretation ends.
Therefore simply asking for those fields again is not the proposed improvement. Task001 showed
unresolved bindings, prose-only claims and no executed extraction probe. Its model never received
compiler diagnostics before finalizing the annotations.

## Minimal substantive changes

### Bind scientific objects, not just arithmetic expressions

The LLM should identify the scientific object and distinguish it from convenient implementation
structures. For example, a physical rotational axis is not interchangeable with any connected
path in a molecular graph. This is an illustration, not a hidden-test-derived rule to insert into
the extractor prompt.

Code should offer validated source identifiers for function inputs, outputs and relevant container
updates, with unambiguous candidate locations for the LLM to select. Keep entity bindings separate
from expression bindings: identifying the variable that carries a graph does not prove a mathematical
equation about that graph. Repair the observed locator/index mismatches without accepting ambiguous
references as verified. Retain the existing arithmetic analysis where it actually applies.

### Represent applicability and a discriminating observation

For each retained item, ask for: scientific object/meaning; code carrier and affected consumers;
public evidence; applicability conditions; a plausible conflicting interpretation; and a small
observation or probe that could distinguish them. Use mathematical expressions for mathematical
claims and executable predicates for discrete/structural claims. Do not build a universal semantic
language or treat a successful probe as a proof of the science.

The expected relation must come from public scientific evidence, a documented API contract or a
justified reference/limiting case—not simply copying the current buggy output. Preserve explicit,
inferred and unresolved status. If a probe only shows that interpretations differ, it does not
establish which is correct. Public-source silence must remain an unresolved question.

An invariance check alone can preserve an inappropriate answer. A useful check should also address
the scientific scope of the particular claim, including a contrasting case when the evidence
supports one. The task001 posthoc probe and hidden assertion must not become task-specific extractor
instructions or be passed to a future evaluated agent.

### Close one bounded feedback loop inside extraction

Proposed sequence: draft annotations → existing code-owned assembly/public probe → one short model
revision using rejected bindings and observed probe results → final assembly/handoff. The revision
can correct locators, narrow applicability, retract unsupported interpretations or preserve unknowns.
Do not require an intended requirement to pass on the original buggy code: a supported failed probe
can be exactly the repair target.

Give repair the selected public probe source alongside the supported interpretation and observed
results, so it can recheck its patch within the repair allowance. Repair may challenge an inferred
rule with public evidence; an erroneous extracted rule must not become an unquestionable instruction.

Reuse `tool_cli.py` assembly diagnostics and `pier_agent.py` assembly/probe execution. A second
interpretation call needs distinct raw artifacts and combined token accounting; calling today's
`interpret` twice unchanged would overwrite its logs. Keep model source access read-only. Code-owned
probes remain ordinary bounded executions in the disposable task environment, not a new source-write
permission scheme for the model.

All calls, probes, revision and final assembly stay inside the existing extraction cap and total
agent allowance. Reserve time for revision/final assembly before starting the draft; do not append
them after today's phases have consumed the allowance. Retain the last valid draft if revision
cannot finish. Changed probes cannot inherit results from old scripts or different claim bindings.

## Falsifiable development check before another repair comparison

Propose extractor-only checks on already exposed examples spanning both discrete and numerical
science; choose the exact tasks and a single revised configuration before running. Rajarshi reviews
whether the output contains relevant scientific content rather than generic software advice.

Record whether the intended code entities actually bind; whether applicability is supported;
whether a probe executes and meaningfully distinguishes interpretations or exposes a supported bug;
and which claims remain uncertain. Do not use graph validity, citations alone or probe exit zero as
the success criterion. Fixing source bindings is necessary but does not by itself supply missing
scientific knowledge.

If this still produces only paraphrases, unsupported expected values or irrelevant tests, stop and
reconsider the extraction approach before spending on a larger comparison. If it produces useful
scientific constraints, propose a fresh paired repair comparison with matched model/resources/budget
and all extraction/revision costs included. No expanded experiment is authorized by this proposal.

## Boundaries

This tests the whole extraction-and-repair procedure, not a causal contribution of the graph alone.
Task001 is diagnostic-exposed and cannot serve as an untouched evaluation case. The benchmark runner,
Docker isolation and standard repair execution need no redesign for this revision. Implementation
and any live model checks require Rajarshi's subsequent approval.
