# Fable design review (2026-09-11)

External design opinion from Claude Fable 5 (read-only, dispatched via the orchestrator). Evidence read: docs/METHOD.md, docs/OBJECT_ENRICHMENT.md, docs/WORKFLOW_FIVE_LUNA_V1.md, prompts/enrich_objects.md, prompts/repair.md, object_context.py, workflow_retrieval.py.

## Verdict

The design is coherent and defensible as a research-task submission, with one framing caveat: the code-derived *scientific* layer is inert on real benchmark tasks (0/266 API calls recognized). What actually operates is workflow-evidence localization + ID-anchored annotation. The report must say exactly that, not "hybrid scientific-object representation" — evaluators will check whether the scientific half did anything, and the receipts say it did not.

## Three strongest threats to validity

- T1. Zero statistical information in the repair comparison. n=5 paired, one stochastic attempt per arm. Even 5/5 vs 0/5 gives exact McNemar p≈0.06; 3/5 vs 2/5 is indistinguishable from a coin flip. Say "no detectable effect", never "negative".
- T2. "Same total budget" is false on the token dimension. Treatment totals run +35% to +105% on measurable tasks. Task 058's context-arm failure is a harness confound (empty guide + less repair time), not a treatment result.
- T3. Contamination and no locked evaluation. All 5 tasks development-exposed; 001 has prior hidden-test exposure; helper source drifted (since fixed). No measurement of whether the repair agent used the guide at all; the prompt hedges three times, inviting an xhigh agent to ignore it.

## Recommended changes (ranked)

- A. Split into RQ1 (localization: does workflow-evidence retrieval place fix-touched files/functions in the guide more often than a text baseline like TF-IDF/BM25?) — offline, no agent runs, scalable — and RQ2 (repair: does the guide change verifier success under matched model/time/tokens?). RQ1 is the single highest-value deadline-feasible upgrade; requires reference targets at the pinned dataset revision.
- B. Zero-cost guide-utilization analysis on existing science trajectories: did the agent cite object IDs, open scientific-graph.json, or reference guide source spans? If ~0, that itself explains the null and is a stronger finding than the pass/fail table.
- C. Report 0/266 as a benchmark finding: bug-relevant paths are bespoke/multilingual code that does not route through numpy/scipy/astropy calls, so API-knowledge-graph approaches do not transfer. One paragraph, one table.
- D. Budget honesty: label the comparison "wall-clock-matched, token-unmatched" with the per-task token delta table. Never write "same budget" where tokens differ.
- E. If further runs are affordable: a fresh predeclared locked cohort (≥8 unrestricted-license tasks), ≥2 attempts per arm, same model both arms; optional "code-only guide" ablation arm; never pool models; do not rerun dev tasks as the final evaluation.
- F. Prompt: drop the triple hedge to one sentence; add "inspect the source spans listed for the workflow interfaces first". Only for new runs.

## Strongest honest 4-page structure

- p1: Problem and narrowed RQ1/RQ2. One-line statement of the null pilot up front. Contribution: (a) code-owned object model with ID-anchored LLM enrichment (LLM cannot create structure), (b) workflow-evidence localization from public reproducers, (c) receipt-level evaluation harness, (d) two empirical findings: scientific-API recognition is inert on this benchmark; a 5-task paired pilot shows no detectable effect and why it cannot.
- p2: Method — one pipeline figure, one real annotated object (task 009 or 114: ID, span, meaning, assumption), the enrichment contract in ~6 lines, budget definition.
- p3: Results — Table 1 API-recognition coverage per repo (0/266); Table 2 localization hit rate (RQ1); Table 3 paired pilot with pass/fail, agent-seconds, tokens per stage, the 058 timeout flagged; guide-utilization counts.
- p4: Threats to validity (T1–T3 verbatim), what the receipts do and do not show, precise specification of the locked experiment that would decide RQ2 (task IDs, attempts, model, token cap). Disclose LLM tooling and division of labour.
- Refs: SWE-bench Science, SpecRover, DSrepair, SKEMA, dataflow-graph enrichment, ReproAgent.

## Interview answers

- "Why not test-generation/probes?" — the rejected predecessor is precisely that, rejected on principle: probes let the LLM substitute claims for structure.
- "What would have made the science layer fire?" — units/dimension rules need typed quantities; bespoke code has none. A data-representation gap, not a rule-count gap.
