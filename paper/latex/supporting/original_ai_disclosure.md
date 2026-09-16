# AI-assisted development disclosure

This records assistance and experiment tools, not a claim of research success.

- Rajarshi Ghoshal formulated the research question, designed the method and experimental
  protocol, approves scientific direction, and owns the final claims. He evaluates the scientific
  usefulness of the generated models.
- Codex development sessions (GPT-6 Astra) implemented and reviewed the earlier code and experiment
  machinery; preserved run/configuration records identify evaluated models. The Codex lane was
  replaced by the Oh-My-Pi harness session (GLM-5.3, then DeepSeek V4.1 Flash as the writer) after
  its usage limit was reached on 15 September 2026.
- OpenCode/worker sessions used DeepSeek models and GLM-5.3; they contributed source extraction,
  runtime observation, experiment machinery, debugging and reviews. Read-only AI reviewers
  (DeepSeek V4.1 Flash) checked source identity, evidence selection, tool delivery, run isolation
  and runtime behavior; their reviews are advisory, not correctness oracles.
- Claude Fable was used earlier for planning/review; no Claude consultations or model calls are
  involved in the current implementation or the reported runs.
- Worker subagents (DeepSeek V4.1 Flash) implemented two bounded engineering tracks under human
  direction and root-session review: the file-ranking/limit change, the boundary-contract
  cascade. All changes were reviewed, tested and committed by the root session.

Reported repair comparison: DeepSeek V4.1 Flash (reasoning effort low for the reported runs,
high for one earlier replicate), through the host-side function-calling agent and Pier 0.3.0 in
offline task containers. Historical development also used Codex CLI 0.153.4 with GPT-6 Astra/high
and GPT-5.6 Luna. Exact settings and resolved provider metadata belong in the run receipts.

The ordinary baseline and interactive-science arm share model, tools, total allowance, and base
instructions; only the prepared scientific representation and its query tools differ. Source
preparation does not call an LLM. The official benchmark verifier determines repair outcomes,
not an AI judge.

Thirty development tasks and 89 locked evaluation tasks are frozen in the split manifest. Earlier
pipeline activity is disclosed separately from task-specific design use and private-diagnostic
exposure. The known 001 private-diagnostic flag remains explicit. Prior broken-treatment runs are
historical engineering/development evidence, not a clean negative test of the current hypothesis.

Development evidence is consolidated in results/ (four independent evaluations, 240 attempts;
arm-isolation and delivery audits; selection-content audit). Scheduler status labels can
mislabel cleanup timeouts; verifier receipts and run.json stage records are the authority.
No exact consultation counts are claimed, and no historical artifact is claimed to have been
reviewed by Rajarshi unless a receipt records it.
