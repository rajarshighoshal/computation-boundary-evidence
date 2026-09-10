# TU Graz research task

The original `PhD Research Task-TU Graz.pdf` is authoritative. Rajarshi owns the scientific decisions.

## Research target

Study scientific bug repair across SWE-bench Science. Build an original hybrid scientific-object
representation: code-derived structure and scientific relationships, enriched by LLM interpretation.
An extra LLM reasoning pass, graph-shaped prose or probe generator alone is not this contribution.
Keep the research question narrow and falsifiable; do not restrict the design to the last failure case.
Evaluate against a credible baseline on the full benchmark or a defensibly predeclared subset.

## Submission essentials

- Deadline: 16 September 2026, 23:59:59 CEST. Internal target: 15 September evening IST.
- Interview: 18 September 2026, 16:30–17:30 IST.
- English PDF: at most four main-content pages plus one references page.
- Include repository URL, genuine commit history, reproduction README, results and exact task IDs.
- Disclose all LLM/AI tools and the division of work. Do not overstate Rajarshi's prior research.
- Send to `feifei.niu@tugraz.at`; subject: `PhD Research Task Submission - Rajarshi Ghoshal`.

## Sources

- Paper v2: https://arxiv.org/abs/2608.19799v2
- Official code: https://github.com/OpenMOSS/SWE-bench-Science
- Dataset: https://huggingface.co/datasets/OpenMOSS-Team/SWE-bench-Science
- Project: https://swescience.github.io/

Use primary sources. Keep exact dataset/code revisions, images, model, harness, prompts and task
selection in run records. Do not repeatedly copy benchmark facts into instruction files.

## Working rules

- Answer simple questions directly. Do not create a plan, log entry or tool workflow for a trivial task.
- Keep updates short. Explain material uncertainty; do not silently substitute a different method.
- Use standard tools outside the research contribution. No extra harness, sandbox, judge or guardrail
  unless a concrete need is established and the change is in scope.
- Get approval for model experiments: exact tasks, attempts and budget. Prefer unrestricted licenses;
  restricted tasks need explicit opt-in. Do not begin with a full-benchmark run.
- Use a credible baseline with matched model, tools and total allowance. Declare selection before
  outcomes; separate development from locked evaluation. Official verifier success is the main outcome.
- Preserve failed runs, patches, trajectories and provenance. Generate reported numbers from durable
  scripts/receipts; missing costs remain unknown. Do not claim significance or causality from tiny pilots.
- Keep secrets out of Git/images, large artifacts out of Git, and preserve unrelated user changes.
  Use small meaningful commits. Concurrent writers use separate worktrees from verified commits.
- Run a documented clean reproduction before submission; do not confuse infrastructure success with
  scientific extraction quality or improved repair.

## Compact context, not accumulating history

- `AGENTS.md` contains stable rules only. Replace obsolete rules; do not append results, old plans or diaries.
- `WORK_LOG.md` is the only live ledger: current objective, a few active/next actions, essential blockers
  and the latest verified checkpoint. Update in place and name the final check.
- Remove completed actions from the live list once their outcome is captured in a receipt or commit.
  Consolidate repeated context; link to existing results rather than duplicating them.
- Preserve useful history in Git or an archive, not in routine working context. Read it only for a
  specific historical question. Do not create a new document for every update.
- On resumption, read the compact ledger and relevant current code. Consult older plans only as needed;
  user corrections override stale plans. Reports/receipts, not narrative summaries, establish results.
