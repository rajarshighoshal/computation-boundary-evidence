# Current work

## Fixed target
Build a connected, task-relevant scientific-code graph before the repair model starts. Preserve
actual quantities/computations/dependencies/conditions and public scientific evidence; persist
and expand the same graph through compact queries. A file inventory, arbitrary groupings or
node counts are not substitutes for scientific relevance. Use existing multilingual analyzers.
DeepSeek Flash remains the model; no specialist-model integration or new framework.

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
- [active: Luna/xhigh] User approved16GB and the same58-trial retry. Root changed only active
  settings-store.json MemoryMiB9216→16384; Luna owns restart/verification/run monitoring.
  runs/development-e2e-40-v3 is running40 slots from immutablea491759, without main's science
  changes. Preserve the previous9216 setting for restoration when research no longer needs16GB.
- [verified: root] General science fixes: observations are not requirements; unknown outputs or
  uncontrolled receiver state cannot imply a parameter response; summary similarity is not
  equality; displayed computations retain their guards and shown citations. Source selection
  preserves single-call workflow paths and shares the512-entry budget without early-file
  starvation.599 tests pass; independent reviews plus requested correction applied.
  Fresh public-source rechecks: runs/context-recheck-v4.001/009/091 relevant computations are
  selected;114 has constraints.py evidence but its initial view remains wrapper-heavy.
- [next] Review a computation-first selection change using public task/docs and actual links,
  then check the fixed30 development set before freezing. Do not hardcode task IDs or known
  fix-function names. R6's unknown-status classification and meaning-to-citation entailment
  remain gaps. No additional LLM verifier or graph/framework redesign is approved.
  Merge reviewed a491759 adapter cleanup into main after the science checkpoint commit.
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
Current Docker8CPUs/~9GiB, host14logicalCPUs/24GiB. Scheduler supports40; full workload capacity
is not yet established. Specialist comparison is complete in docs/SPECIALIST_EXTRACTOR_COMPARISON.md.
