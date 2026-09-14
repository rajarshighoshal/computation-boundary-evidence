# AI-assisted development disclosure

This records assistance and experiment tools, not a claim of research success.

- Rajarshi Ghoshal formulated the research question and approves scientific direction, experimental
  protocol and final claims. He evaluates the scientific usefulness of the generated models.
- Codex development sessions implemented and reviewed the code and experiment machinery. Earlier
  sessions used GPT-6 Astra; preserved run/configuration records identify evaluated models.
- OpenCode/worker sessions used DeepSeek models and GLM-5.3; an earlier short Muse Spark session is
  also recorded in the session history. They contributed source extraction, runtime observation,
  experiment machinery, debugging and reviews.
- Claude Fable was used earlier for planning/review and coordinating GLM work. Claude is no longer
  used; the current interactive implementation involves no Claude consultations or model calls.
- Read-only AI reviewers checked source identity, scientific evidence, tool delivery and runtime
  behavior. Their reviews are advisory, not correctness oracles.

Current planned repair comparison: DeepSeek Flash/high in both arms, through the existing
function-calling agent and Pier0.3.0. Historical development also used Codex CLI0.153.4 with
GPT-6 Astra/high or medium and GPT-5.6 Luna/xhigh. Exact settings and resolved provider metadata
belong in the run receipts.

The ordinary baseline and interactive-science arm share a model and total allowance. Source
preparation does not call an LLM; the repair agent constructs its own scientific model through
the science tool. The official benchmark verifier determines repair outcomes, not an AI judge.

Thirty development tasks and89 locked evaluation tasks are frozen in the split manifest. Earlier
pipeline activity is disclosed separately from task-specific design use and private-diagnostic
exposure. The known001 private-diagnostic flag remains explicit. Prior broken-treatment runs are
historical engineering/development evidence, not a clean negative test of the current hypothesis.

Before submission, reconcile this disclosure with the preserved session and run records; do not
invent exact consultation counts or claim that every historical artifact was reviewed by Rajarshi.
