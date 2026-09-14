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
development/capacity evidence, not locked evaluation. No cloud rental is approved. The89 locked
evaluation tasks stay outside this iteration.

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
- [decision] Ready for a fresh40-slot development test after the network fix; repeat paid
  attempts have not been launched. Original interrupted run stays separate; do not silently
  retry/merge cancelled trials or claim40-way capacity is validated.
- [next] Inspect concrete failures, apply small task-agnostic fixes with regression tests, and
  recheck. Known graph-content gaps include114 missing sources,001 selection,091 missing guard,
  and false R2/R4 requirements; do not label node counts/self-checks as scientific quality.
Final verification: actual preparation→query/expansion→repair→official verifier receipts; observed
concurrency/resource failures, token/time/cost reporting, and independent review of each fix.

## Guardrails against drift
Do not change the RQ, graph requirement, model, baseline, cohort or gate policy without Rajarshi.
Fix demonstrated problems within this design; show missing capability instead of substituting a
proxy. No source/commit changes during scientific trial runs; capacity diagnostics use frozen
inputs. Keep the ledger compact. No further archiving project; do not delete existing artifacts
or unrelated files without instruction. No premature report/submission pivot.

## Essential context
Frozen30/89 split: configs/interactive-science.split.json. Licensing/prior exposure metadata remain.
The earlier preparation-only30-task sweep is runs/extractor-validation-30 (b11625c); construction
completed30/30 but scientific relevance/source gaps remain. Earlier drift8 is separate.
The prior index-first repair pilot is stopped and does not evaluate this prepared-graph method.
Current Docker8CPUs/~9GiB, host14logicalCPUs/24GiB. Scheduler supports40; full workload capacity
is not yet established. Specialist comparison is complete in docs/SPECIALIST_EXTRACTOR_COMPARISON.md.
