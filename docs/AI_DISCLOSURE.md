# AI-assisted development disclosure

Rajarshi Ghoshal formulated and refined the research direction, challenged the proposed scope, and approved the two-condition design, hybrid extraction approach, development tasks, model setting and time allowance.

Codex assisted with assignment/paper inspection, literature retrieval and synthesis, design discussion, implementation, tests, debugging and experiment machinery. GPT-6 Astra is the model used for the current implementation conversation and its delegated code/review work. The exact model snapshot for the earliest pre-switch inspection was not captured and must be recovered from session records before making a stronger disclosure claim.

Parallel implementation used isolated Git worktrees for the source-evidence, semantic-graph, result-analysis and process-supervision modules. The main Codex session reviewed and integrated them and made the runner/integration changes. Web/documentation tools and local Python/Docker tools supported retrieval and verification.

Evaluated agents use Codex CLI 0.153.4 and GPT-6 Astra through Rajarshi's ChatGPT subscription. Historical checks use high effort; the later initial-check continuation uses medium at his request. Both arms match effort within a task pair. Execution reuses upstream Pier Codex.run; the latest extraction uses native Codex read-only mode and code-owned output saving, without the rejected custom Git guard. Repair retains normal container execution. Exact run settings, prompts and usage are preserved in artifacts. No separate LLM judge is used as the primary outcome; the official benchmark verifier supplies repair outcomes.

The random-five checks were explicitly designated initial research feasibility work, not a locked
experiment. Method/effort changes, an operator stop, and the later subscription-quota failure are
preserved separately. No API-key billing fallback was used. Posthoc AI-assisted patch/graph review
is qualitative interpretation, was not fed to evaluated agents, and is not a scientific correctness
oracle. Rajarshi must review the scientific interpretation and final claims.

This file records the division of work, not a claim that any experimental improvement has been established. Pilot and final results must be generated from preserved run artifacts and reviewed by Rajarshi.
