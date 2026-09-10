# Current work

## Objective

Build the missing hybrid scientific-object extractor for scientific bug repair across domains.
Code derives objects and computational relationships; LLM interpretation enriches that structure.
Probes support the representation, not replace it. No benchmark runs or harness changes now.

## Active work

- In progress: code-driven extractor, `scientific_objects_core` worker in isolated
  `.cache/worktrees/scientific-objects-core`; owns `scientific_objects.py` and its tests.
- Next: root integrates contextual enrichment and a small offline cross-domain demonstration.
- Final check: inspect generated representations, run local tests, and state unsupported cases.
  This does not establish repair improvement or authorize another experiment.

## Latest checkpoint

`82e2a35`: prior method's bounded comparison is complete and negative; results and limitations in
`docs/PROBE_FIRST_PAIRS_V1.md` and `_NOTES.md`. Historical attempts remain unchanged.
Project rules/log have now been compacted; archive links below preserve older context.

## Carry forward

- No benchmark runs active. Preserve user-owned PDFs, `.serena/` and `workspace/`.
- Docker memory remains temporarily increased; restore `MemoryMiB=4096` only when no longer needed.
  Original setting/receipt: `results/docker-memory-change.json`.
- All previously used tasks are development-exposed. Task001 has additional posthoc hidden-assertion
  exposure; disclose it before any future attempt. Do not feed private outcomes into extraction.

History only when needed: `docs/archive/WORK_LOG_2026-09-11.md`. This file is current state, not a diary.
