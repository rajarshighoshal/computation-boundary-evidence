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
- Next: other-language structure frontends for the shared representation and a separately approved
  live scientific-quality check after review. No API-rule expansion or benchmark calls yet.
- Review target: scientific meanings must connect to code objects/interfaces, not merely rename
  APIs. Current offline annotations are fixtures, not demonstrated LLM scientific understanding.
- Final check: inspect generated representations, run local tests, and state unsupported cases.
  This does not establish repair improvement or authorize another experiment.

## Latest checkpoint

`27705a3`: anchored scientific reading is integrated with the existing runner; Pint and custom-code
anchors included. Full tests passed from this commit (`runs/scientific-object-checkpoint-v1/pytest.xml`).
Offline examples: `runs/scientific-object-demo-v2`; real public-source extraction:
`runs/scientific-object-public-source-v1`. PyCG fit failures: `runs/tool-fit-pycg/RECEIPT.md`.
Prior negative comparison remains unchanged in `docs/PROBE_FIRST_PAIRS_V1.md` and `_NOTES.md`.

## Carry forward

- No benchmark runs active. Preserve user-owned PDFs, `.serena/` and `workspace/`.
- Docker memory remains temporarily increased; restore `MemoryMiB=4096` only when no longer needed.
  Original setting/receipt: `results/docker-memory-change.json`.
- All previously used tasks are development-exposed. Task001 has additional posthoc hidden-assertion
  exposure; disclose it before any future attempt. Do not feed private outcomes into extraction.

History only when needed: `docs/archive/WORK_LOG_2026-09-11.md`. This file is current state, not a diary.
