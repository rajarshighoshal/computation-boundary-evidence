# Current work

## Fixed target and authority
Connected task-level scientific-code representation, queried by the repair agent. Preserve real
computations, quantities, dependencies, conditions and public evidence. No replacement with an
index, graph-shaped prose, a new agent framework or a mandatory planning gate.

Rajarshi owns scientific decisions. Root is the only code writer; reviewers are read-only.
Preserve unrelated untracked PDF, REPRODUCTION.md, paper/, results, docs and workspace files.
Git, run receipts and this ledger take precedence over older model-written memory.

## Approved work now: five local fixes
User approved these fixes plus tests, independent review and a small end-to-end recheck.
- [verified locally] Self-check refuses existing models and restores memory/disk state; full-file
  hashes use streaming reads; unknown/environment statuses no longer become science violations.
  Explicit failed-check reports retain their kind without guessing a mathematical constraint.
  Regressions failed before the changes;96 focused tests and independent review pass.
- [verified locally] Three focused science tools replace the overloaded interface. science_note
  accepts plain text plus note_target/note_source_ids supplied by inspection; internal IDs and
  required storage fields are filled by code. Current-source refresh replaces stale references,
  preserves unrelated-file citations and labels original execution evidence as preparation-time.
  Shifted/deleted symbols and Python/C++/Fortran/MATLAB/Cython refresh regressions pass.
- [verified] Full suite659 passes. Independent reviews passed both phases;64 focused tests in
  final refresh/UI review. Deleted top-level functions cannot retarget same-named methods;
  first-time expansion supplies usable note fields. No unapproved representation redesign.
- [active] Freeze the corrected code, then recheck009 baseline/science with GLM-5.3-Flash/low,
  1800s work each, two concurrent attempts, unchanged official verifier. Preserve v1 separately.
Final verification: tested fixes plus real preparation→graph query→repair→verifier receipts;
verify note usability/recovery, token/time counts and cleanup. No40-job debugging batch.

## Current verified checkpoint
Main f4607a3; implementation3e57ed4,637 tests passed; independent Luna review passed.
GLM directly uses the same DeepSeekAgent host-API loop, NOT OpenCode CLI. Only provider/body/key
handling changed. Saved zai-coding-plan credential stays host-private; never print/upload it.
User explicitly requested this route after the provider-policy caveat. No further policy debate,
client impersonation, provider change or new harness. Normal shell tools in both arms; science
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
observations. The five known local issues are now fixed and regression-tested. Real-task
revalidation is the active milestone above; unit success alone is not an E2E claim.

Graph relevance on hard cases and40-way capacity are separate validation work, NOT completed by
these five fixes. runs/context-recheck-v4:001/009/091 relevant computations selected;114 includes
constraints.py in its packet but initial graph stays wrapper-heavy. No task-ID-specific hints.
Computation-first selection has been discussed, not implemented. Citations do not prove meaning.

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
