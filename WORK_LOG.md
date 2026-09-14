# Current work

## Approved design
Interactive scientific understanding for repair. Static-first preparation; one continuous
DeepSeek Flash/high agent; science queries on demand; source-linked working-model checkpoint
before ordinary repair tools. Baseline is ordinary repair. No separate interpretation LLM,
automatic trace/build, second task container, Claude calls or new agent framework.

## Live milestones
- [verified] Science find/inspect/record_model implemented with expandable evidence and model-first
  gate; lightweight preparation, same conversation/container, all agent work within1800seconds.
- [verified] Frozen30/89 split: configs/interactive-science.split.json. Prior activity, development
  use and private-diagnostic exposure recorded separately; license gates retained.
- [verified] Final regression run551passed; independent reviewer found no pilot plumbing
  blocker; no-model public001 container check and real OpenMC C++ Joern-to-model check passed.
  Separate interpretation/extraction live paths removed; method and reproduction docs updated.
- [in progress] Freeze and launch five-task paired pilot at runs/interactive-five-v1:
 001/009/058/091/114, one attempt/arm, DeepSeekFlash/high,1800s, concurrency2.
 Review scientific models and tool use before interpreting repair outcomes. No method edits live.
Final check: actual pre-edit scientific model + grounded tool interactions + preserved paired
verifier/token/time receipts. Larger development/evaluation runs follow reviewed pilot evidence.

## Boundaries and continuity
One writer (Codex); reviewers read-only. Retain useful GLM source/trace fixes and existing
expression/quantity/condition representation. Preserve all historical runs and unrelated files.
No commits during live trials. Every method revision remains separate.
Known design anchors:001,002,004,009,010,016,019,025,051,058,077,091,114.
License gates remain explicit. No full-test-set launch or cloud rental without authorization.
40 scheduler slots are software-tested, not proof of40-heavy-workload capacity; Docker8CPUs/~8.7GiB.
Latest full suite551passed; multilingual discovery/owned-cleanup delta45targetedtests passed.
Receipts: runs/interactive-implementation-tests.xml; runs/interactive-container-check/receipt.json;
runs/interactive-backend-check/integration-receipt.json. Integration models are fixtures, not
evidence of automatic scientific understanding. No model calls for the new method yet.
Prior live50000be extraction delivered0/5; preserve evidence. No repair-benefit/readiness claim.
