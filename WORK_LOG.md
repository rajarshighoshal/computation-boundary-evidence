# Current work

## Objective

Build the missing hybrid scientific-object extractor for scientific bug repair across domains.
Code derives objects and computational relationships; LLM interpretation enriches that structure.
Probes support the representation, not replace it. Working window: one–two days (interpreting
the user's “1/2 days”). Full-benchmark execution is the target; samples are development only.
Language-specific structure extraction must feed the shared representation. No benchmark runs now.

## Active work

- Local multilingual milestone verified: scientific passages, interfaces and computations reach the
  same representation; native scope/write/omission regressions tested. No API-rule expansion.
- Root remains the only writer in main; no extra worktrees. Read-only review findings were addressed
  with regression tests; the implementation is ready for external review.
- Next: a separately approved live scientific-quality check (exact tasks/attempts/budget), not another
  parser expansion. No new model, Docker or benchmark runs were made in this continuation.
- Review target: scientific meanings must connect to code objects/interfaces, not merely rename
  APIs. Current offline annotations are fixtures, not demonstrated LLM scientific understanding.
- Final local check passed: inspect generated representations, full local tests and helper-wheel
  availability. Native Cython real-source quality and guest runtime imports remain unverified.
  This does not establish repair improvement or authorize another experiment.

## Latest checkpoint

Current multilingual checkpoint: `runs/multilingual-object-checkpoint-reviewed/pytest.xml` (595 tests),
`runs/multilingual-public-source-reviewed/receipt.json` (pinned selected files; implementation hashes).
Native C/C++/Fortran/MATLAB/Cython feed shared objects; unsupported syntax is explicit. The MACS
file is Python syntax at its pinned revision, not evidence of a real `.pyx` source check. Earlier
failed source checks remain preserved. Helper-wheel receipts: `.cache/multilingual-fit/assets/`;
Python 3.10 needs rpds-py 0.30.0, while 3.11–3.13 retain the existing pin.
Earlier Python/LLM integration: `27705a3`; offline fixtures `runs/scientific-object-demo-v2` are
hand-authored interpretations. PyCG fit failures: `runs/tool-fit-pycg/RECEIPT.md`.
Prior negative comparison remains unchanged in `docs/PROBE_FIRST_PAIRS_V1.md` and `_NOTES.md`.

## Carry forward

- No benchmark runs active. Preserve user-owned PDFs, `.serena/` and `workspace/`.
- Docker memory remains temporarily increased; restore `MemoryMiB=4096` only when no longer needed.
  Original setting/receipt: `results/docker-memory-change.json`.
- All previously used tasks are development-exposed. Task001 has additional posthoc hidden-assertion
  exposure; disclose it before any future attempt. Do not feed private outcomes into extraction.

History only when needed: `docs/archive/WORK_LOG_2026-09-11.md`. This file is current state, not a diary.
