# Current work

## Objective

Build the missing hybrid scientific-object extractor for scientific bug repair across domains.
Code derives objects and computational relationships; LLM interpretation enriches that structure.
Probes support the representation, not replace it. Working window: one–two days (interpreting
the user's “1/2 days”). Full-benchmark execution is the target; samples are development only.
Language-specific structure extraction must feed the shared representation. No repair comparisons now.

## Active work

- Local multilingual milestone verified: scientific passages, interfaces and computations reach the
  same representation; native scope/write/omission regressions tested. No API-rule expansion.
- Root remains the only writer in main; no extra worktrees. Read-only review findings were addressed
  with regression tests; the implementation is ready for external review.
- Approved now: extraction-only checks on full public workspaces for 051/SHTOOLS, 025/Osprey,
  016/MACS; Astra/medium, one attempt each, six minutes per model call. No repairs or verifiers.
- Active: verify the existing extraction-only command and workspace preparation, then launch the
  approved calls in parallel where feasible. Final verification: preserve inputs/outputs and stage
  token usage; inspect scientific meanings against public evidence and report failures honestly.
- Launch configuration: `configs/scientific-reading-v1.json`; three pinned unrestricted environments
  downloaded, separate release receipt prepared. Explicit model cap 360s; full extraction wall budget
  600s includes preparation/handoff/cleanup. Existing runner concurrency 2; 599 local tests pass.
- Component preflight complete: purpose/convention evidence exists, but selected-file artifacts are
  not task-complete (MACS omits refinement; Osprey omits the other report problem). See METHOD.md.
- Fixed Python interface/docstring reservation and native per-function allocation; MATLAB outputs
  now use function-exit binding instead of whole-body return excerpts. Legacy selection unchanged.
- Review target: scientific meanings must connect to code objects/interfaces, not merely rename
  APIs. Current offline annotations are fixtures, not demonstrated LLM scientific understanding.
- Final local check passed: inspect generated representations, full local tests and helper-wheel
  availability. Native Cython real-source quality and guest runtime imports remain unverified.
  This does not establish repair improvement or authorize another experiment.

## Latest checkpoint

Current preflight: `runs/scientific-input-preflight/pytest.xml` (598 tests), with pinned selected-file
artifacts and implementation hashes in that directory's `receipt.json`. Earlier committed multilingual
checkpoint: `4fd7130`, `runs/multilingual-object-checkpoint-reviewed/receipt.json`.
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
