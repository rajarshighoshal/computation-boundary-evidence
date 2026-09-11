# Current work

## Objective

Build the missing hybrid scientific-object extractor for scientific bug repair across domains.
Code derives objects and computational relationships; LLM interpretation enriches that structure.
Probes support the representation, not replace it. Working window: one–two days (interpreting
the user's “1/2 days”). Full-benchmark execution is the target; samples are development only.
Language-specific structure extraction must feed the shared representation. No repair comparisons now.

## Active work

- Root remains the only writer in main; no extra worktrees. Read-only review findings were addressed
  with regression tests; the implementation is ready for external review.
- Offline retrieval/linking checkpoint COMPLETE: public workflow references reach implementation
  functions, with candidate call links and comparison/statement anchors. Legacy selection unchanged.
  Final verification: 618 tests pass; all three pinned-image helpers finish within the existing cap.
  Receipts/region excerpts: `runs/workflow-retrieval-verified/`, `results/workflow-retrieval-v1.json`.
- Coverage is intentionally partial: Osprey timing/scaling regions and the uncalled gravitational
  counterpart remain gaps. Interface/operation counts are not scientific correctness or repair gains.
- User confirmed: no compiler IR or exhaustive reconstruction; deliver a usable research prototype.
- Combined-context v2 check COMPLETE: same three tasks, one Astra/medium call each, 360s model cap,
  no repairs/verifiers/retries. Method source/prompts/dependencies stayed at `a27cc93`; control-only
  commit `084718b`. Final artifact/token/runtime-setting audits pass; all task containers stopped.
- V2 improves implementation anchoring of substantive scientific explanations, including MACS's
  intersection statement and a SHTOOLS pole assignment. Much scientific content was already in v1;
  this is not new scientific discovery. Osprey mathematical chains remain partly absent, some citation
  ranges are imprecise, and the complete handoff is verbose. Source links remain candidates.
- Prototype checkpoint is ready for a bounded matched repair comparison, not further blanket expansion.
  No repair or additional model-run budget is approved. See `docs/SCIENTIFIC_READING_V2_NOTES.md`.
- This does not establish repair improvement, state-of-the-art quality or full-benchmark coverage.

## Latest checkpoint

Latest offline source hashes and target/guest-check results: `results/workflow-retrieval-v1.json`.
Latest live results: `results/scientific-reading-v2.json`, `results/scientific-reading-v2-token-audit.json`,
and `results/scientific-reading-v1-v2.json`; raw outputs and verification in `runs/scientific-reading-v2/`.
Live check: `runs/scientific-reading-v1/`, `results/scientific-reading-v1.json` and
`results/scientific-reading-v1-token-audit.json`. Public source review copies are inside the run.
Earlier preflight: `6954048`, `runs/scientific-input-preflight/`; multilingual checkpoint `4fd7130`.
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
