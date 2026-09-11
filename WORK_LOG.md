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
- Approved extraction check COMPLETE: full public workspaces 051/SHTOOLS, 025/Osprey, 016/MACS;
  Astra/medium, one call each, all returned under the 360s model cap. No repairs/verifiers/retries.
  Code/config frozen at `2aafb20`; model time separate from 600s extraction wall allowance.
- Final verification passed: outputs/graphs preserved, all session token counters audited, runtime
  model/effort/read-only settings confirmed, selected scientific claims checked against public sources.
  No task containers remain running. Report: `docs/SCIENTIFIC_READING_V1.md` and `_NOTES.md`.
- Main finding: meaningful scientific interpretation, inadequate implementation grounding. Graph
  selection misses the scientific bodies; annotations cite them as prose while anchoring elsewhere.
  Next justified work is task-directed source/operation selection, not new API rules or guardrails.
  No further model attempts or repair comparisons are authorized.
- Offline retrieval/linking checkpoint COMPLETE: public workflow references reach implementation
  functions, with candidate call links and comparison/statement anchors. Legacy selection unchanged.
  Final verification: 618 tests pass; all three pinned-image helpers finish within the existing cap.
  Receipts/region excerpts: `runs/workflow-retrieval-verified/`, `results/workflow-retrieval-v1.json`.
- Coverage is intentionally partial: Osprey timing/scaling regions and the uncalled gravitational
  counterpart remain gaps. Interface/operation counts are not scientific correctness or repair gains.
- User confirmed: no compiler IR or exhaustive reconstruction; deliver a usable research prototype.
- APPROVED NOW: one combined-context extraction call each on 051/025/016, Astra/medium, 360 model
  seconds, no repairs/verifiers/retries. Freeze the source/prompt implementation at `a27cc93`.
  Use a fresh v2 run directory; compare scientific implementation anchoring, public-source support,
  readability and token costs with v1. Driver-only explanations/function-name paraphrases do not
  satisfy the scientific-content criterion. Final check: artifact/token/protocol audit and source review.
- This does not establish repair improvement, state-of-the-art quality or full-benchmark coverage.

## Latest checkpoint

Latest offline source hashes and target/guest-check results: `results/workflow-retrieval-v1.json`.
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
