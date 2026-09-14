# Current work

## Fixed target
Build a connected, task-relevant scientific-code graph before the repair model starts. Preserve
actual quantities/computations/dependencies/conditions and public scientific evidence; persist
and expand the same graph through compact queries. A file inventory, arbitrary groupings or
node counts are not substitutes for scientific relevance. Use existing multilingual analyzers.
Same existing host-API agent harness; user now requests GLM Flash/low as a temporary provider
replacement. No OpenCode runner, specialist model, graph redesign or new framework.

## Ownership and scope
Rajarshi handed writing back to Codex after the OpenCode writer finished. Codex is the only code
writer; reviewers are read-only. User explicitly chose PLAIN baseline vs graph-assisted treatment:
normal tools immediately, no hard gate, no mandatory added planning note in either arm.
User approved the fixed30 development tasks in both arms (60 paid end-to-end trials), DeepSeek
Flash/high, 1800s per trial, with40 concurrent trials TOTAL. Latest instruction: verify a complete
pair first, then the concurrent development test, inspect failures and fix step by step. This is
development/capacity evidence, not locked evaluation. User now approved repeating the remaining29
pairs (58 trials) at40 slots after the offline-network fix, delegated to a Luna/xhigh run manager.
Root works on scientific-context fixes in parallel. Model remains DeepSeek Flash/high1800s.
No cloud rental is approved. The89 locked evaluation tasks stay outside this iteration.

## Live milestones
- [verified] GLM provider/key/configuration adapter added to the SAME host-API loop. Saved
  zai-coding-plan credential stays in host-private storage; no OpenCode CLI or impersonation.
  Shell/science tools, graph and verifier unchanged. GLM nested cache accounting, dict/string
  tool arguments, preserved reasoning and top-level errors tested. HTTPX + an absolute async
  timeout replaces the socket-only request timeout. Full suite637 passes; independent Luna
  review73 focused tests passes. User explicitly requests direct calls despite the earlier caveat.
- [verified] RealGLM-5.3-Flash/low protocol check passed on3e57ed4: tool call→result→READY,
  both requests first-attempt success,9.50s total. Receipt runs/glm-provider-check-v1.json;
  requested/reported model match, usage includes cache and reasoning fields. No OpenCode CLI.
- [active] Run configs/glm-development-e2e-check.json:009 baseline+science,1800s work budget each,
  two simultaneous attempts, existing graph/tools/officialverifier. User is sleeping and asks
  to continue reliably, stop on access blockers. Final verification: actual provider response,
  in-container graph delivery/use, repair, official verifier and token/time receipts. No full40
  batch during adapter debugging; no commits in the frozen live trial.
- [review verified] The pasted0acc214..b11625c review is partly stale: insensitive_pairs are
  already exposed as observations (4ecfd4e). Self-check deleting pre-existing model artifacts
  remains real; prepared full-file hashes vs bounded prefixes remain a latent edge. Both
  independently reproduced on temporary fixtures only; neither is fixed by this provider change.
- [verified] Latest user-approved retry policy implemented: five retries after the initial
  request, exponential backoff2/4/8/16/32s. Actual retry waits pause the1800s work allowance
  in the API, repair loop and controller; request/tool execution still counts. Pier's outer
  agent-only wall ceiling allows the configured waits; official verifier time is unchanged.
  Wall/work/wait durations are separate in receipts and both independent summary paths;
  mixed-budget-policy pairs are refused. Full suite627 passed; independent review passed,
  including cancellation and charged-work checks. Mocked-HTTP end-to-end tests in both arms
  continued through a3s wait under a2s work budget, shell call and final response. No paid run
  launched by this change; next operational check is provider health before another batch.
- [checked / fallback decision pending] Latest live DeepSeek diagnostic onf52a8f2 returned
  no completion: transport read timeout, 241.31s elapsed, no retry sleeps and unknown usage.
  Receipt/script: runs/development-e2e-40-v3/diagnostic-provider-retry5.{json,py}. Process ended.
  The standalone socket request exceeded its120s requested allowance; do not claim that this
  diagnostic had an absolute request deadline. Trial/controller timers are separately tested.
  User proposes temporaryGLM-5.3-Flash; official API supportslow/high/max, NOTmedium. Verified
  published USD/Mtoken pricing: input0.15/cached0.03/output0.50. User has only the Z.ai Coding
  Plan and requests its saved OpenCode key with Flash/low. Credential presence verified for
  zai-coding-plan WITHOUT printing/copying it. Official FAQ/usage policy limits plan use to
  supported tools; our custom direct API loop is not listed. Supported Flash is GLM-5.3-Flash,
  not5.2-Flash. User REJECTED switching the harness to OpenCode and explicitly requests direct
  GLM calls with the same agent and saved key. Keep results separate from DeepSeek; no new
  provider framework. Sources for the earlier caveat: docs.z.ai/devpack/faq and
  docs.z.ai/devpack/tool/others. Coding Plan concurrency is tier/load-dependent, not verified40.
- [verified] 009 pair completed on273d23c, runs/development-e2e-check-v1/summary/summary.json:
  baseline8/9 private, science9/9. Agent durations1094.87s/387.22s, science preparation5.32s.
  Actual graph/node queries, persisted analysis/model/patch and official verifier checked; zero
  infrastructure failures. Independent review found optional citation friction and mismatched
  claim-to-snippet meanings. One positive development pair is not a general benefit claim.
- [verified] runs/development-e2e-40-v1 reached40 live task containers +40 proxies, then observed
  DockerOOM on004 and exit137 preparation failures on001/016. Stopped owned launcher25602;
  finalized2026-09-14T16:50:51Z:2 infrastructure failures,40 interrupted,16 not_run;42 cleanup
  receipts complete. Both stages used identical273d23c frozen files. This is a capacity failure,
  not a negative scientific repair result. See capacity/ samples and oom-review.json in the run.
- [verified] Corrected DeepSeekAgent's inherited OpenAI allowlist with Pier's standard empty
  allowlist for BOTH arms. Both new regression cases failed before the fix;587 tests nowpass,
  independent9-test reviewpasses. No new service, benchmark-image or verifier change.
- [verified] Real009 preparation check oncf32d16, runs/offline-network-check-v1: completed7.30s,
  prepared_graph, model_calls=0. network-check.json has45 observations of network_mode:none,
  no proxy. All owned containers are down. This verifies the fix, not40-way workload capacity.
- [verified: Luna/xhigh] a491759 in the separate checkout removes baseline-visible science
  helpers; actual DeepSeek API fields were compatible. Independent review +588 tests passed.
  runs/development-e2e-40-v2 was a no-model sandbox-launch interruption; preserved separately.
  runs/development-e2e-40-v2-retry reached40 mains,network:none,zero proxies; stopped after014
  baselineOOM. All containers/processes down. Own014 limit8GiB, sampled1.926GiB beforeOOM;
  aggregateVM pressure more likely, transient spike not excluded. See capacity/oom-diagnosis.json.
- [capacity pending provider recovery] User approved16GB; active MemoryMiB16384,
  previous9216 retained for later restoration. v3 reached40 mains/no proxies/no OOM, but failed
  on non-completion API responses (39 KeyError:choices,19 interrupted). All58 cleanup receipts
  complete; no live trials. This does not validate sustained40-way repair/verifier capacity.
  Original response bodies were not saved, so v3's precise original cause is UNKNOWN. A later
  minimal diagnostic returnedHTTP503 service_unavailable_error("Service is too busy") in1.37s;
  see diagnostic-provider-response-120s.json. No new batch; provider recovery is not established.
  API fixes integrated fromd85ca9c/2cc440a and corrected in main: permanentHTTP statuses override
  wording; keys are redacted; failed/retried totals are unknown with reported prefixes preserved.
  The formertwo-attempt policy is superseded by the verified five-retry policy above.
- [verified: root] General science fixes: observations are not requirements; unknown outputs or
  uncontrolled receiver state cannot imply a parameter response; summary similarity is not
  equality; displayed computations retain their guards and shown citations. Source selection
  preserves single-call workflow paths and shares the512-entry budget without early-file
  starvation. Science committed4ecfd4e; reviewed adapter cleanup integrated as4162ed8.
  Combined science/adapter checkpoint600 tests passed; independent review corrections applied.
  Fresh public-source rechecks: runs/context-recheck-v4.001/009/091 relevant computations are
  selected;114 has constraints.py evidence but its initial view remains wrapper-heavy.
- [next] Review a computation-first selection change using public task/docs and actual links,
  then check the fixed30 development set before freezing. Do not hardcode task IDs or known
  fix-function names. R6's unknown-status classification and meaning-to-citation entailment
  remain gaps. No additional LLM verifier or graph/framework redesign is approved.
Methodology: these are manual, failure-driven task-agnostic refinements, not model training;
development-set overfitting remains possible. Freeze before the89 locked-task evaluation and
disclose earlier exposure. The current40-slot run is capacity/development evidence only.
Final verification: actual preparation→query/expansion→repair→official verifier receipts; observed
concurrency/resource failures, token/time/cost reporting, and independent review of each fix.

## Guardrails against drift
Do not change the RQ, graph requirement, model, baseline, cohort or gate policy without Rajarshi.
Fix demonstrated problems within this design; show missing capability instead of substituting a
proxy. No changes in the frozen execution checkout during a run. Main-checkout science edits are
isolated from it and are NOT part of that run. Keep the ledger compact. No further archiving project; do not delete existing artifacts
or unrelated files without instruction. No premature report/submission pivot.

## Essential context
Frozen30/89 split: configs/interactive-science.split.json. Licensing/prior exposure metadata remain.
The earlier preparation-only30-task sweep is runs/extractor-validation-30 (b11625c); construction
completed30/30 but scientific relevance/source gaps remain. Earlier drift8 is separate.
The prior index-first repair pilot is stopped and does not evaluate this prepared-graph method.
Current Docker8CPUs/16GiB, host14logicalCPUs/24GiB. Scheduler supports40; full workload capacity
is not yet established. Specialist comparison is complete in docs/SPECIALIST_EXTRACTOR_COMPARISON.md.
