# Interactive scientific understanding for repair

## Research question
Does a compact, queryable representation of scientific code and its public definitions help a
repair agent form a useful task model and repair software under the same total allowance?

Preparation builds an index, not a scientific explanation. One continuous repair agent queries
scientific evidence, records a short source-linked model, then repairs. The ordinary baseline
has no added planning requirement. This tests the whole intervention, not individual components.

## Method
- Static preparation indexes public files and supplies a tiny task map. No model call, build,
  reproducer run or mandatory whole-repository analysis occurs during preparation.
- The science tool provides find, inspect and record_model. It exposes connected quantities,
  expressions, conditions, interfaces and source definitions; detailed evidence remains expandable.
- Existing Python/native/Cython parsers do syntax work. Targeted Joern analysis runs on demand when
  its frontend is installed; unsupported analysis is explicit. No parser output is scientific truth.
- Initially only science tools are available. A durably recorded, source-linked model unlocks
  ordinary repair tools. Unknowns are allowed; references are checked, not scientific correctness.
- The working model states the scientific object/goal, governing relationships, implementation
  correspondence, expected change and behaviour to preserve. It remains revisable during repair.
- The same conversation and task container continue throughout. All tool use and model building
  count against the same1800-second allowance as baseline.

## Development and evaluation
The frozen split is configs/interactive-science.split.json:30 development tasks and89 locked
evaluation tasks. Known task-specific design cases are included; remaining development slots are
sampled from unrestricted tasks by SHA256 with seed interactive-science-v1-20260914.
Prior pipeline runs, design use and private-diagnostic exposure are separate facts.
The evaluation set is not claimed to have been historically untouched.

First run the original five development tasks001/009/058/091/114 in both arms, one attempt each,
DeepSeek Flash/high,1800seconds, concurrency2. Inspect the scientific models, evidence queries and
repair behaviour before interpreting outcomes. Refine on development data, freeze the method,
then evaluate the locked tasks with required approvals/license opt-ins. No deadline-forced launch.

## Verification and responsibility
Tests and independent code review check source identities, compact paging, correct conditions,
analyzer persistence, tool-name dispatch and gate ordering. The actual pilot establishes whether
models are scientifically correct/useful and used during repair. Official verifier outcomes,
paired differences, all input/cached/output/reasoning tokens, runtime and failures are preserved.

Rajarshi makes scientific decisions. Codex implements; reviewers are read-only. No Claude calls.
Old forced-interpretation and probe-first runs remain historical evidence, not results of this method.
Current progress and blockers are recorded only in WORK_LOG.md.
