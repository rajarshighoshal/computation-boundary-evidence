# AI-assisted development disclosure

This file records the division of work and the AI/LLM tools used. It is not a claim that any experimental improvement has been established.

## Division of work

- **Rajarshi Ghoshal** formulated the research question, made every scientific decision (method direction, the rejection of the probe-first and API-catalog designs, task selection, model settings, budget policy, exposure disclosures), and reviews all scientific interpretation and final claims.
- **OpenCode orchestrator (deepseek-v4-pro)** implemented, tested and debugged the code: the object/operation/link graph, workflow retrieval, bounded enrichment selection, the anchored enrichment contract, the repair harness, the frozen-source run discipline, the DeepSeek agent route, and the execution-observation extractor. It also managed receipts, archives, and repository hygiene.
- **Codex CLI sessions (GPT-6 Astra via the ChatGPT subscription)** handled early assignment/paper inspection, literature retrieval, and the first implementation passes, and later executed benchmark-agent runs under Astra.
- **Claude Fable 5** was used for three read-only design consultations (external review, core-design analysis, and the extractor build specification). Its output is advisory; it never edited files and never fed evaluated agents.
- **Verify agent (DeepSeek V4.1 Flash)** performed a read-only code verification pass over the DeepSeek agent route; findings were fixed before use.

## Evaluated agents (benchmark runs)

- Codex CLI 0.153.4 in Pier 0.3.0 containers. Models used across development: GPT-6 Astra (high/medium effort), GPT-5.6 Luna (xhigh) for the frozen five-task comparison, and DeepSeek-flash via a custom function-calling agent for later design checkpoints (introduced after the ChatGPT subscription hit its usage limit).
- Arms always match model and effort within a pair. The official benchmark verifier is the primary outcome; no LLM judge decides success.
- Preserved run artifacts record exact settings, prompts, per-stage tokens and durations. Unknown costs are reported as unknown, never as zero.

## Disclosures specific to the experiments

- All five comparison tasks are development-exposed. Task 001 additionally has prior hidden-assertion diagnostic exposure, disclosed in its receipts.
- The frozen five-task comparison (Luna) is wall-clock-matched but token-unmatched, and its audit found helper-source drift across task groups; both facts are reported with the results. The run is presented as a design checkpoint, not a locked evaluation.
- The Codex subscription usage limit interrupted a design check mid-turn; that attempt is preserved as infrastructure-failure, not a result.
- Posthoc AI-assisted review of failures is qualitative interpretation based on public evidence; it was not fed to evaluated agents and is not a correctness oracle.

## Historical work no longer part of the method

Earlier probe-first and API-catalog designs were superseded. Their run receipts are archived (docs/archive/); the code was deleted from the live pipeline. The current method is the execution-observation scientific-meaning extractor per docs/FABLE_EXTRACTOR_SPEC.md.
