# AI-assisted development disclosure

Rajarshi Ghoshal formulated and refined the research direction, challenged the proposed scope, and approved the two-condition design, hybrid extraction approach, development tasks, model setting and time allowance.

Codex assisted with assignment/paper inspection, literature retrieval and synthesis, design discussion, implementation, tests, debugging and experiment machinery. GPT-6 Astra is the model used for the current implementation conversation and its delegated code/review work. The exact model snapshot for the earliest pre-switch inspection was not captured and must be recovered from session records before making a stronger disclosure claim.

Parallel implementation used isolated Git worktrees for the source-evidence, semantic-graph, result-analysis and process-supervision modules. The main Codex session reviewed and integrated them and made the runner/integration changes. Web/documentation tools and local Python/Docker tools supported retrieval and verification.

The planned evaluated agent is native Codex CLI 0.153.4 with GPT-6 Astra/high through Rajarshi's ChatGPT subscription, in both conditions. The extraction session uses the same model. Exact run settings, prompts and usage are preserved in artifacts. No separate LLM judge is used as the primary outcome; the official benchmark verifier supplies repair outcomes.

This file records the division of work, not a claim that any experimental improvement has been established. Pilot and final results must be generated from preserved run artifacts and reviewed by Rajarshi.
