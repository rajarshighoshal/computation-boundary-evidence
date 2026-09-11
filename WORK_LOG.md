# Current work

## Objective

Build the missing hybrid scientific-object extractor for scientific bug repair across domains.
Code derives objects and computational relationships; LLM interpretation enriches that structure.
Probes support the representation, not replace it. Working window: one–two days (interpreting
the user's “1/2 days”). Full-benchmark execution is the target; samples are development only.
Language-specific structure extraction must feed the shared representation.

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
- APPROVED NOW (supersedes Astra): fresh baseline versus context-assisted repair on the original five
  tasks 091/058/009/114/001 using GPT-5.6 Luna/xhigh, one attempt per arm, 1800s total; treatment's
  360s model extraction cap and 600s extraction wall allowance are inside that total. Official verification.
  Existing maximum concurrency 2: both arms together, then next task; no method changes or retries.
  Task001's prior private-test diagnostic exposure was disclosed; all five are development cases.
- Original five-task run STOPPED at an infrastructure error; no containers remain running.
  091 completed: baseline passed, science failed private checks (both public passed). 058 science
  extraction completed, but repair never launched: host `docker` spawn raised E2BIG on the 7.7MB
  handoff. The runner interrupted 058 baseline; 009/114/001 were not started. No retries performed.
- APPROVED FIX + FRESH COMPARISON: durable full graph in the repair workspace, concise scientific
  guidance/file pointers rather than a graph dump, standard stdin prompt input. Isolate failed attempts
  so siblings and remaining queued tasks continue; no silent retries. Same original five/tasks/budgets.
- Transport/handoff + attempt-local scheduling VERIFIED: all 630 tests pass, including byte-exact
  oversized stdin and sibling/queue continuation after failure. Actual OpenMC graph replay in its pinned
  offline image preserves all objects/annotations with matching host/guest hashes; receipt:
  `results/file-handoff-check-v1.json`. Full graph/sources and readable guide live in repair-container
  files; prompt contains only pointers. No extractor rules, scientific semantics or model budget changed.
- Astra v2 STOPPED at user request for the model switch. Its partial results and costs are preserved in
  `results/workflow-five-v2.json`, `results/workflow-five-v2-token-audit.json`, `docs/WORKFLOW_FIVE_V2.md`.
  Owned containers stopped; no completed/partial Astra outcomes will be pooled into the Luna run.
- Active: freeze and launch `configs/workflow-five-luna-v1.json` on the original five, Luna/xhigh in
  both arms and both treatment stages. Config/TOML checks and 80 relevant runner tests pass.
  Method remains `dc62db2`; only model/effort change, not scientific method or time budgets.
  Final verification: all ten attempt receipts reconciled, official verifier outcomes and per-stage
  input/cached/output/reasoning tokens audited, generated comparison report; preserve v1 separately.
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

- Astra five-task v2 is stopped; do not resume it. Luna original-five launch is next. Preserve user-owned PDFs,
  `.serena/` and `workspace/`.
- Docker memory remains temporarily increased; restore `MemoryMiB=4096` only when no longer needed.
  Original setting/receipt: `results/docker-memory-change.json`.
- All previously used tasks are development-exposed. Task001 has additional posthoc hidden-assertion
  exposure; disclose it before any future attempt. Do not feed private outcomes into extraction.

History only when needed: `docs/archive/WORK_LOG_2026-09-11.md`. This file is current state, not a diary.
