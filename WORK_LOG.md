# Current work

## Fixed target and authority
Connected task-level scientific-code representation, queried by the repair agent. Preserve real
computations, quantities, dependencies, conditions and public evidence. No replacement with an
index, graph-shaped prose, a new agent framework or a mandatory planning gate.

Rajarshi owns scientific decisions. Root is the only code writer; reviewers are read-only.
Preserve unrelated untracked PDF, REPRODUCTION.md, paper/, results, docs and workspace files.
Git, run receipts and this ledger take precedence over older model-written memory.

## Active: locked-89 k=3 evaluation running; code/documentation cleanup in progress
- [verified] Frozen-run semantics: trials execute from runs/<run>/frozen-source; HEAD drift is
  recorded in receipts (head_at_launch/head_drift), never aborts (commit 39eef13). Same commit
  raised the Joern export budget (16k nodes / 60k edges). Split-validation crash demoted to a
  warning (11cf0e6) - it had aborted the first locked launch.
- [verified] Four independent development evaluations (240 attempts): pooled baseline 43/120 vs
  science 44/120; measured single-run noise floor ~±3/30 from the code-invariant baseline arm.
  Token accounting is effort-dependent: science 25% cheaper input at high effort, ≈30% costlier
  at low effort (graph results enter context) - the earlier "17-25% fewer" claim was a
  within-science improvement, not an arm comparison, and is corrected in README/METHOD.
  077 solved 3/4 with graph, 0/4 without. results/dev30-four-run-consolidation.json. Dynamic
  ranking admitted previously-excluded kernels (058/051/073/076 verified in prepared states).
- [verified] Boundary cascade implemented and tested (commit af22a7c): Joern semantic layer,
  BOUNDARY_DECLS include/use/import/cimport table, unknown_external fallbacks, uniform schema;
  715 tests pass. Prompt now forbids retrying failed optional notes (6df40da; 019-science lost
  25min to a record_note retry loop).
- [verified] Determinism audit (results/determinism-audit-v1.json): temperature already 0.0 on
  every request; provider IGNORES the seed parameter (two identical seeded calls produced
  different output); PYTHONHASHSEED=0 now pinned for host subprocesses and in-container science
  commands; time-allowance text rounded to whole minutes. 715 tests pass. Commit 739d038.
- [verified] First locked chain aborted at ~64/178 (k1) by decision: replicates must share one
  frozen code revision. Partial run preserved (runs/deepseek-locked89-k1-v1) and excluded from
  the evaluation. Fresh chain relaunched as locked89-k3-v2 with the determinism controls.
- [next] Analysis (repeated measures across k=3), report numbers, reproduction pass, PDF.
Final verification: submission-ready 4-page PDF + receipts + reproduction README before
16Sep2026 23:59:59 CEST (17Sep 03:29 IST).

## Completed: DeepSeek V4.1 Flash provider check
User approved trying V4.1 Flash after confirming that original V4 Flash is retired on the direct API.
- [verified] One tiny health request through the existing DeepSeek adapter, then one batch of40
  simultaneous tiny requests only if the first succeeds. Model deepseek-flash, high effort (the
  existing DeepSeek setting), max1024 output tokens/request,120s request work with the existing
  five retries. No benchmark rerun, Docker operations, scientific-method edits or harness change.
- [verified] All41 returned HTTP200 on first attempt, zero retries/429s; peak40 client HTTP
  requests in flight, batch2.2698s, total4.0606s. Tokens1435input/982output including857reasoning;
  estimated off-peak cost USD0.00080445. Two replies were READY. rather than READY; preserve
  the raw strict-answer status as failed, separate from successful provider transport.
- [verified] Independent reviewer reproduced counts, timings, usage and cost from receipts.
Final verification passed for provider transport only: runs/deepseek-v41-capacity-check-v1/summary.json.
This is not40 complete repair/verifier trials. Scientific selection work is now approved above.

## Broader frozen validation: stopped; audit handoff pending
User explicitly approved the30-task graph audit and40-concurrent E2E development test ASAP.
- [verified] GLM Flash/low config for ALL30 development tasks, baseline+science (60 attempts),
  40 TOTAL simultaneous trials;1800s work and separate1800s official verifier. Full suite665
  passes; independent instrumentation review passes. Full initial state is snapshotted before
  inference for the audit (not added to the prompt). Config: configs/glm-development-e2e-40.json.
- [verified] GLM run stopped after provider HTTP429/code1302 exhausted five retries in43/60
  trial receipts. Peak40 main containers,0 verifiers,5.176GB summed Docker working set,0 observed
  OOM. All60 cleanup receipts complete; no repair score. runs/glm-development-e2e-40-v1.
- [verified] All30 immutable initial graphs captured with matching hashes, no dangling edges
  and no unmatched packet source IDs. Scientific review inspected all30; several initial views
  expose early setup/validation instead of the central calculation. The targeted selection fixes
  now pass local tests above; the real-task table still needs saving/reconciliation.
- [pending] Consolidate the30 immutable pre-repair graph-bundle reviews produced by this SAME
  run; no duplicate preparation containers. Separate construction/grounding checks from
  scientific relevance, inspect hard cases against public task/workflow context. Locked89 untouched.
  Relevance review uses initial snapshots/public task evidence, not private-test bodies or
  candidate patch outcomes. Central-computation coverage, workflow-only graphs and uncertainty
  are reported separately; graph counts alone never establish scientific understanding.
- [next] Independent outcome/resource/graph audit and concise handoff with exact task IDs.
Final verification: all60 attempted/status-accounted, initialgraphs audited for30tasks, actual
40-way peak measured (or explicitly not reached), outcomes/tokens/time independently recomputed.

## Completed prerequisite: five local fixes
User approved these fixes plus tests, independent review and a small end-to-end recheck.
- [verified] Self-check refuses existing models and restores memory/disk state; full-file
  hashes use streaming reads; unknown/environment statuses no longer become science violations.
  Explicit failed-check reports retain their kind without guessing a mathematical constraint.
  Regressions failed before the changes;96 focused tests and independent review pass.
- [verified] Three focused science tools replace the overloaded interface. science_note accepts
  plain text plus the inspected target; displayed evidence is attached automatically. Explicit
  inspected object/source references are resolved by code, never invented or unseen citations.
  Internal IDs and required storage fields are filled by code. Refresh replaces stale references,
  preserves unrelated-file citations and labels original execution evidence as preparation-time.
  Shifted/deleted symbols and Python/C++/Fortran/MATLAB/Cython refresh regressions pass.
- [verified] Full suite661 passes. Independent reviews passed both phases and the final
  reference-binding adjustment (66 focused tests). Deleted functions cannot retarget other methods;
  first-time expansion supplies usable note fields. No unapproved representation redesign.
- [verified] Paired recheck completed on a4cac9b: runs/glm-development-e2e-check-v2, GLM Flash/low,
  1800s work each, concurrent2, public1/1 both; baselineprivate6/9, science9/9. Independent
  recomputation matches its summary. Note nesting/stale errors disappeared, but2 reference-type
  rejections remained: GLM included its inspected computation ID with valid source IDs.
  Final binding adjustment resolves such references and removes mandatory manual source IDs.
  Both EXACT rejected requests now save on copied real public artifacts; a fresh GLM note call
  also saved first try. runs/note-interface-replay-v3/live-receipt.json records source/code hashes.
  This final adjustment was checked separately, NOT silently counted as an error-free v2 repair
  run. No whole-pair rerun after that last note-only change; v1/v2 results remain separate.
The five-fix pass is complete; broader validation above is now authorized and must be carried through.

## Current verified checkpoint
Current selection checkpoint passes684 tests; previous frozen source164ccb0 had665.
Provider integration3e57ed4; paired checkpointa4cac9b.
GLM directly uses the same DeepSeekAgent host-API loop, NOT OpenCode CLI. Only provider/body/key
handling changed. Saved zai-coding-plan credential stays host-private; never print/upload it.
User explicitly requested the GLM route, then approved DeepSeek V4.1 Flash for the provider check.
No client impersonation or new harness. Normal shell tools in both arms; science
adds evidence tools. Recording is optional and revisable, never a repair gate.

Real GLM protocol check: runs/glm-provider-check-v1.json; echo→result→READY,9.50s, no retries.
Real pair: runs/glm-development-e2e-check-v1, frozen2723478, both completed and images cleaned:
- Baseline: public1/1, private6/9,117.01s; input75144/cached61632/output3038/reasoning1002.
- Science: public1/1, private9/9,215.38s including4.68s preparation;
  input265385/cached239232/output7521/reasoning1047. No provider failures/retries.
Independent recomputation matches summary/summary.json; independent receipt audit agrees.
This is ONE development pair, not a general benefit or full scientific-correctness claim.
Science read the graph overview before editing, but detailed nodes only after its patch; no
subsequent code changes. Seven optional note-recording failures, no note saved. Therefore the
score difference cannot be attributed to detailed scientific interpretation. Baseline concretely
used zpvi (Z position) where ztpvi (Z_theta) was needed in its normal construction.

## Known defects and boundaries
The pasted review of0acc214..b11625c was partly stale: insensitive_pairs already appear as
observations. The five known local issues are fixed and regression-tested. Real-task and
exact-request revalidation are recorded above; undiscovered bugs are not claimed eliminated.

Graph relevance on hard cases and40-way capacity are separate validation work, NOT completed by
these five fixes. runs/context-recheck-v4:001/009/091 relevant computations selected;114 includes
constraints.py in its packet but initial graph stays wrapper-heavy. No task-ID-specific hints.
Result/dependency-first selection is implemented and reviewed, awaiting the30-task source rebuild.
Citations do not prove meaning; full graph relevance and repair benefit remain unvalidated.

## Frozen experiment and operating policy
configs/interactive-science.split.json fixes30 development /89 locked tasks; disclose prior
exposure. No new locked-task experiments or silent tuning. GLM results stay separate from old
DeepSeek results. No cloud rental. Deadline16Sep2026 23:59:59CEST; internal15Sep eveningIST.
Do not pivot to report-writing as a substitute for testing the research question.

Five provider retries after the initial request, waits2/4/8/16/32s. Actual backoff is excluded
from1800s work; requests/tools still count. Wall/work/wait are separately reported. HTTPX absolute
async cancellation fixes the former standalone socket-timeout overrun. Pier agent-only wall
ceiling allows configured waits; official verifier remains1800s. Do not commit during live runs.

Docker8CPUs/16GiB, host24GiB. User approved temporary MemoryMiB16384 in settings-store.json;
restore previous9216 when research allocation is no longer needed, NOT inactive legacy4096.
Standard Pier offline containers; no unnecessary OpenAI egress proxies. Forty mains were reached
but not full40 repairs/verifiers: v1/v2 had9GB OOM, v3 had provider failures at16GB. Preserved runs:
runs/development-e2e-40-v1, -v2-retry, -v3. Current GLM validation only established two concurrent
full trials. Luna's former isolated checkout .cache/capacity-runner-2ac921a remains at2cc440a;
do not execute it as current science code. No active experiment from the completed GLM pair.
