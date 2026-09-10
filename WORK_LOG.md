# Current work

## Objective

Build the missing hybrid scientific-object extractor for scientific bug repair across domains.
Code derives objects and computational relationships; LLM interpretation enriches that structure.
Probes support the representation, not replace it. Working window: one–two days (interpreting
the user's “1/2 days”). Full-benchmark execution is the target; samples are development only.
Language-specific structure extraction must feed the shared representation. No benchmark runs now.

## Active work

- Core merged as `ef3e62c`; all extra worktrees removed, commits retained. Unique old source checks
  preserved in `runs/archived-semantic-bindings-source-checks`. Root is the only writer.
- Anchored enrichment, source/interface context and the one-call scientific-reading path are
  implemented; local/full tests and offline fixtures pass. Custom code remains annotatable even
  without recognised APIs. Pint replaces the unit table; PyCG fit check did not produce a graph.
- Finish the clean review checkpoint, then other-language structure frontends and a separately
  approved live scientific-quality check. Public plasma-source extraction runs without model calls;
  its API recognition is absent but source-only objects remain available for interpretation.
  No API-rule expansion or new benchmark calls yet.
- Final check: inspect generated representations, run local tests, and state unsupported cases.
  This does not establish repair improvement or authorize another experiment.

## Latest checkpoint

`ef3e62c`: code-first core integrated and focused tests passed. Prior comparison at `82e2a35`
is complete and negative; results and limitations in
`docs/PROBE_FIRST_PAIRS_V1.md` and `_NOTES.md`. Historical attempts remain unchanged.
Project rules/log have now been compacted; archive links below preserve older context.

## Carry forward

- No benchmark runs active. Preserve user-owned PDFs, `.serena/` and `workspace/`.
- Docker memory remains temporarily increased; restore `MemoryMiB=4096` only when no longer needed.
  Original setting/receipt: `results/docker-memory-change.json`.
- All previously used tasks are development-exposed. Task001 has additional posthoc hidden-assertion
  exposure; disclose it before any future attempt. Do not feed private outcomes into extraction.

History only when needed: `docs/archive/WORK_LOG_2026-09-11.md`. This file is current state, not a diary.
