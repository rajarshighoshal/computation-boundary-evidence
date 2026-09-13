# Current work

## Objective

Build the missing hybrid scientific-object extractor for scientific bug repair across domains.
Code derives objects and computational relationships; LLM interpretation enriches that structure.
Probes support the representation, not replace it. Working window: one–two days (interpreting
the user's “1/2 days”). Full-benchmark execution is the target; samples are development only.
Language-specific structure extraction must feed the shared representation.

## Active work

- ONE-CALL INTERPRETATION CHECK COMPLETE: DESC, DeepSeek Flash/default high, one call/no retry,
  52.01s, 81170 input + 12817 output tokens (9546 reasoning, included in output), estimated off-peak
  USD 0.0198657 within approved USD 0.10. Frozen input/prompt/raw response at
  `runs/transformation-interpretation-desc-v1/`; receipt/review `results/transformation-interpretation-desc.json`.
  Final check: JSON and cited source IDs/ranges valid; 173-word summary recovers the main scientific
  chain and discarded gain. Partial scientific pass: six units retain wrapper/reproducer/requirements;
  links omit direct boundary→metrics dependency and mix requirements with flow; summary overgeneralizes
  scaled/projection equality without matching effective nowall. No repair benefit tested or claimed.
  No production prompt/schema changes, repairs, verifier or candidate execution. STOP: review concise
  transformation/link contract next; no repeat call or full-run approval remains. User prioritizes
  finishing quickly and explicitly rejects further elaborate infrastructure.
- TARGETED HELPER RETRIEVAL COMPLETE: connected input follows Python same-file/relative-import/module-
  alias calls using existing source reads and AST scope analysis. Bodies/call/gap records deduplicated;
  call argument/default mappings, return sites, branches and existing caller/result IDs retained.
  Native retrieval, graph scientific semantics, prompts/schema and repair logic unchanged.
  Final verification PASS: 516 tests (12 new cases), offline DESC all six required implementation
  functions together in a packet, source hashes and endpoint references checked. Receipt:
  `results/evidence-helper-retrieval.json`; raw replay `runs/evidence-helper-retrieval-final/`.
  Retrieval/assembly from saved graph/packet 0.1604s; not model/extraction/repair latency. Input grew
  432526→641846 bytes with newly supplied evidence. 43 syntactic argument mappings; 20 unexpanded
  variadic/star mappings explicitly unknown. STOP: review transformation-based interpretation and
  compression next; no model call, candidate execution, benchmark restart or cleanup was performed.
- MANUAL TRANSFORMATION CHECK COMPLETE: one existing DESC development packet worked into three
  connected units, compact context and code/LLM responsibilities in `docs/EVIDENCE_PACKETS_PHASE1.md`.
  Final checks PASS: packet-ID membership, source hashes/slices, key formula/branch line bindings,
  and diff whitespace. Crucial gap: saved input has no vacuum.py passages/bodies; manual public-helper
  retrieval supplies the wall/metric internals. Do not present this as automatic extraction success.
  No pipeline edits, model calls, candidate execution, repair runs or cleanup. STOP for joint review.
  The helper-retrieval gap is addressed by the checkpoint above; general unit construction remains
  pending. User explicitly wants runtime treated as a design goal before acceleration/scale-up.
- PHASE 2 PROMPT DRAFT ON HOLD pending transformation-unit design review: direct instructions, 148 words,
  no blanket hedging; specific missing facts use "unknown" in assumptions. Existing JSON schema,
  guide renderer and repair prompt unchanged. Formatting and real-template adapter wiring verified:
  37 targeted tests pass (API mocked). Existing per-object schema is not the new unit representation. No model calls
  or new runs performed/authorized in this prompt-only step; scientific output quality not yet tested.
- PHASE 1 COMPLETE: connected evidence packets implemented for interpreter input. Packet/merge helpers
  opt into recorded-dependency/candidate-callee bundles with hash-checked source bodies and documentation;
  historical input selection remains available for comparison. No new scientific claims or dispatch proofs.
  Final check: 502 tests pass, including 13 new source/budget/link/wiring regressions. Saved development
  before/after: `docs/EVIDENCE_PACKETS_PHASE1.md`, `results/evidence-packets-phase1.json`, raw inputs in
  `runs/evidence-packets-phase1-final/`. Unresolved inputs and omitted packet seeds remain explicit.
  STOP HERE for joint inspection. LLM prompts, response schema, guide renderer, repair logic and rules
  unchanged. Zero model calls, candidate execution, Docker cleanup or concurrency changes in this phase.
- USER STOP / TAKEOVER (2026-09-13): root now leads implementation; other session should review only.
  Stop active full-119 repair launcher gracefully, preserve all outcomes/partial attempts, then inspect
  context generation and the actual repair prompt before more experiments. Forty-way concurrency is
  a future target requiring context-quality and capacity checks, not approval to launch now.
  Final verification: stopped launcher/owned containers; evidence-backed generation/selection/use
  diagnosis and a short next-version prompt proposal. Do not modify or restart the frozen run.
- APPROVED SCIENTIFIC FIXES (2026-09-13): exact-content equality or explicit unknown (including
  nested/truncated values and downstream comparisons); derive report failures from actual predicates,
  not field-name guesses. Root owns these edits; external reviewer checks afterward. Final checks:
  swapped-array/unknown/nested-value regressions, predicate polarity/tolerance cases, full suite.
  No new model calls, full-benchmark launch or unrelated harness changes in this implementation turn.
- ROLLING ADMISSION VERIFIED (2026-09-13): scheduler refills freed slots in declared order, up to
  the existing configured limit; no batch barrier. Eight-slot, real-subprocess overlap, failure,
  cancellation and partner-image tests pass; full suite 478 passed. Model/budgets/science unchanged.
  Another session committed scheduler/README/review files as `762b9fe` during this work; preserved.
  Its message mentions concurrent pre-pulls, but image pulls remain serial in the actual code.
  Added regression tests remain uncommitted; no commit or run restart by this session.
  User asked how to fix scientific issues: proposed exact-content comparison or unknown, and
  explicit reproducer predicates rather than field-name guesses. Those fixes are NOT implemented.
- REVIEW COMPLETE (2026-09-13): concurrency/cloud/scientific-design review at `c6b973d`, saved in
  `docs/CONCURRENCY_SCIENCE_REVIEW_2026-09-13.md`; executable diagnostics and source hashes in
  `results/concurrency-review-2026-09-13.json` / `scripts/review_concurrency.py`. User has Hetzner;
  VM budget is USD 2 TOTAL, not hourly. Wants rolling slots and eventually 20–30 active attempts.
  Verified batch barrier; synthetic unequal-array/equality collision, false field-name violations,
  and trace failure preventing static fallback. Conditional cheap CX53 quote fits a short rental,
  but public stock unavailable and console/all-in price unverified. No rentals/model calls/runtime
  changes during review. Review docs/receipt were subsequently committed by the other session;
  diagnostic script remains untracked. Avoid changing active launcher's HEAD. Await user direction.
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
- COMPLETE: `runs/workflow-five-luna-v1` launched from clean control commit `972722f`, configured by
  `configs/workflow-five-luna-v1.json`. The cube-reader pair passed in both arms; OpenMC baseline
  passed but context arm failed (extractor timed out; zero scientific annotations, code-only fallback).
  DESC passed both arms (9/9 each). PyPSA failed both arms, with 10/15 baseline versus 13/15 context.
  Autochem failed both arms (1/3 each). All ten attempts and official verifiers finished: baseline 3/5,
  context 2/5, no science-only solved task. Schedule wall time and per-stage costs are in the generated
  `docs/WORKFLOW_FIVE_LUNA_V1_SUMMARY.md`; full report `docs/WORKFLOW_FIVE_LUNA_V1.md`.
  PROVENANCE MISMATCH FOUND: `object_context.py` hashes differ across groups (091/058 frozen,
  009 another hash, 114/001 a third). The running autochem container copy confirms added input-pruning
  code absent from current/frozen source; saved in `runs/workflow-five-luna-v1/provenance-check/`.
  User notified and asked about concurrent edits; origin remains unknown. Read-only input replay found
  substantive differences only for DESC: five literal objects and five links omitted. PyPSA/autochem
  retained identical underlying input plus selection metadata. Do not claim one unchanged method.
  Both treatment stages use Luna/xhigh. Config/TOML checks and 80 runner tests pass.
  Final verification COMPLETE: ten receipts/patch hashes independently reconciled, 14 stage token totals
  verified and OpenMC extraction cost unknown. All Docker task containers stopped. Reporting tests: 40
  pass. No active model call or approved retry remains. Source/prompt changes were not made by this
  monitoring session; reporting now flags per-attempt helper-source drift automatically.
- Next decision is scientific, not implementation: discuss the negative pilot, extractor completion and
  unexplained mid-run input-helper edits before approving a new frozen evaluation. Do not launch more calls.
- This does not establish repair improvement, state-of-the-art quality or full-benchmark coverage.

## Latest checkpoint

**Dev loop status (2026-09-12):** five-task development base running the complete pipeline (execution trace -> constraint loci -> bounded anchored enrichment -> sharp guide with measured findings, sibling-implementation convention evidence, and static candidates). Both arms DeepSeek-flash, uniform ceiling, counterbalanced, official verifier. Every attempt fully instrumented: streamed session JSONL (content/reasoning/tool calls/usage), uncapped tool outputs, assembled prompts, repair-context copies, extraction-phase timeline.

**Latest five-task iteration results and mechanisms:**
- 091: science 3/3 PASS vs baseline 0/3 FAIL. Mechanism: the constraint-locus annotation carried the coordinate-frame convention; the science patch subtracts the cube grid origin (Bohr->Angstrom); the baseline wrapped coordinates cosmetically (`to_unit_cell=True`).
- 058: both arms 9/9. Mechanism: relative-tolerance fix via the repo's own `coincident` helper; guide carried the completion finding + C++ interface annotations.
- 009: baseline 9/9 PASS vs science 6/9 FAIL. Mechanism: premature convergence - the guide localized the bug (R1 at `build_projection_wall`) but not the intended construction convention; the science arm explored 42 steps/1.9M tokens versus baseline's 79/8.0M and invented a poloidal-tangent normal instead of the radial-derivative convention. Fix applied: findings now list sibling implementations (convention carriers).
- 114: baseline 13/15 fail; science extraction died on a transport `IncompleteRead` (retry now added).
- 001: treatment delivered (invariance finding + annotations); both arms fail on the task where no patch passes (best 1/3).

**Infrastructure findings:** Docker's predefined address pools exhaust after many runs (each attempt creates networks) - fixed with auto-prune at run start plus stagger launches and a warm egress-proxy build cache. Concurrency raised to 6 after measuring actual container memory (~30 MiB; the 8 GiB is a limit, not usage); host has 14 cores.

**Six delivery bugs found and fixed (each silently made the treatment a no-op):** trace sys.path for task-local packages; prompt `.format` brace collision; enrichment envelope schema_version + string-vs-array normalization; merge-dynamic missing the script report; prepare missing --observe/--shims; packet caps excluding native files (bounded direct native scan added).


**Iteration 2 (dev-five-v4, concurrency 6, 90-min ceiling, convention evidence):** all 10 attempts completed, zero infrastructure failures.
- 091: baseline 3/3 PASS; science 0/3 - hit the 100-iteration loop cap (8.76M tokens, no patch written). Mechanical; cap raised to 200 with recorded exit reasons in the working tree.
- 058: both 9/9 (tie).
- 009: both 9/9 (tie) - **science recovered from 6/9**: with sibling implementations in the finding, the science arm consulted `_scaled_wall_arrays`/`rspvi` (9 tool calls, 3.2M input) and produced a passing radial-convention fix.
- 114: both 13/15 (tie, fail).
- 001: both 1/3 (tie, task ceiling - no known patch passes).

**Convention-evidence iteration verdict:** the fix works where the mechanism predicted (009), ties elsewhere, and the only loss (091) was iteration exhaustion, not wrongness. Iteration 3 tests the raised cap.

Suite: 474 passed.
## Carry forward

- Astra v2 stopped; Luna original-five finished. No active runs or automatic retries. Preserve user-owned PDFs,
  `.serena/` and `workspace/`.
- Docker memory remains temporarily increased; restore `MemoryMiB=4096` only when no longer needed.
  Original setting/receipt: `results/docker-memory-change.json`.
- All previously used tasks are development-exposed. Task001 has additional posthoc hidden-assertion
  exposure; disclose it before any future attempt. Do not feed private outcomes into extraction.

History only when needed: `docs/archive/WORK_LOG_2026-09-11.md`. This file is current state, not a diary.
