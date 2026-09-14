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
- [verified] Took over b11625c. New commits fix R1-as-observation, Python symbol-source lookup,
  bounded large-file prefix reads, analyzer replay and namespace/cut-call cases; no gate remains.
- [verified] runs/extractor-validation-30 completed30/30 at2026-09-14T15:54:32Z with zero model
  calls on frozenb11625c. Earlier drift8 is separate. These are preparation results, not evidence
  that all graphs contain the right science.
- [verified] Plain baseline checkpoint:585 tests pass; independent45-test launch/config review
  passes. Config dry-runs produce009's2 attempts then remaining29's58,40 total slots. The only
  behavioral change is removal of the mandatory planning instruction; graph-quality fixes remain.
- [verified] Side capacity diagnostic ran4/8/16 public reproducer workloads without OOM/stall;
  runs/capacity-check-b116/receipt.json. This does NOT validate40 full trials.
- [active] Freeze and run configs/development-e2e-check.json → runs/development-e2e-check-v1.
  Check009's actual prepared graph, delivered prompt/tool replies, graph use, repair and official
  verification before admitting the larger batch. Successful setup alone is insufficient.
- [next] Run the approved fixed30 both-arm development/capacity test at40 total concurrency;
  configs/development-e2e-40.json → runs/development-e2e-40-v1. Monitor resources, preserve failures,
  and stop admission if the host cannot sustain the load. No retries or code changes during a run.
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
The prior index-first repair pilot is stopped and does not evaluate this prepared-graph method.
Current Docker8CPUs/~9GiB, host14logicalCPUs/24GiB. Scheduler supports40; full workload capacity
is not yet established. Specialist comparison is complete in docs/SPECIALIST_EXTRACTOR_COMPARISON.md.
