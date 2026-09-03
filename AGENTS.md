# TU Graz PhD Research Task Workspace

This workspace is for the technical take-home task for the TU Graz PhD position in AI for Software
Engineering / Software Engineering for AI (reference `7160 / 2026 / 9581`, PI: Dr. Feifei Niu).

The original assignment PDF in this directory is authoritative. If this file conflicts with the PDF,
follow the PDF.

## Objective

Study SWE-bench Science, identify a precise research problem, implement an original method, compare
it with at least one reasonable baseline, and evaluate it on the full benchmark or a defensible
pre-declared subset. The outcome must demonstrate research judgment, not merely repository setup or
agent orchestration.

## Hard Constraints

- Submission deadline: **16 September 2026, 23:59:59 CEST (UTC+2)**.
- Internal completion target: **15 September 2026 evening IST**.
- Interview: **18 September 2026, 16:30-17:30 IST**.
- Report: at most **4 pages of main content plus 1 references page**, in English and PDF.
- Also required: repository URL with genuine commit history, concise reproduction README,
  experimental results, and the exact evaluated task IDs.
- Disclose every LLM and AI-assisted development tool used.
- Submission recipient: `feifei.niu@tugraz.at`.
- Required subject: `PhD Research Task Submission - Rajarshi Ghoshal`.

## Primary Sources

- Assignment: `PhD Research Task-TU Graz.pdf`
- Current paper version: https://arxiv.org/abs/2608.19799 (use v2, revised 1 September 2026)
- Official benchmark repository: https://github.com/OpenMOSS/SWE-bench-Science
- Official dataset: https://huggingface.co/datasets/OpenMOSS-Team/SWE-bench-Science
- Project/leaderboard: https://swescience.github.io/

Use primary sources for technical claims. Record the exact paper version, dataset revision, container
digests, runner version, model, agent harness, prompts/configuration, and task selection used.

## Verified Benchmark Facts

These are orientation facts, not substitutes for reading the paper and repository:

- The release contains 119 tasks from 98 repositories across 20 scientific domains.
- Tasks belong to issue-driven, expert-exploratory, or engineering-integration paradigms.
- The default unrestricted selection has 96 tasks; 23 tasks require an explicit license opt-in.
- The science-knowledge ablation flag covers 91 tasks.
- The paper reports best-agent Pass@1 below 50 percent.
- Its failure analysis identifies scientific knowledge/abstraction deficits, misguided exploration or
  surface repair, incomplete repair or integration, and failure to generalize scientific knowledge.
- Scientific guidance is not uniformly beneficial. Grounded guidance can constrain repair and reduce
  tokens, while poorly aligned guidance can anchor the agent without improving exact success.
- The public release intentionally excludes gold patches, private verifier tests, credentials, and
  agent trajectories.
- Evaluation uses pinned environment and verifier images through Pier. The documented runner requires
  Python 3.12+, Docker with `linux/amd64` support, and `datacurve-pier==0.3.0`.

Re-verify all of these against the checked-out release before relying on them in the report.

## Candidate Context

Rajarshi's strongest directly relevant evidence is:

- production experience building and evaluating LLM systems, coding/agent workflows, and release
  validation;
- research on internal LLM representations and inference-time routing;
- exact graph-algorithm and HPC research, including independent-set reformulation for dense
  k-clique-counting subproblems;
- strong Python/C++ implementation and experiment-engineering experience.

Do not imply prior research in program repair, formal program analysis, or scientific-software
benchmarks. The task should demonstrate transferable ability and new learning honestly.

Rajarshi is the scientific decision-maker. AI tools may assist with literature retrieval, code,
experiment machinery, debugging, and analysis because the assignment permits them with disclosure,
but he must understand, challenge, and approve the research question, method, protocol, findings, and
claims. Preserve enough records to describe the division of work accurately.

## Research Taste And Fit

Prefer a narrow, falsifiable question about representation, evidence, constraints, or reliability.
Do not build a broad multi-agent framework simply because it sounds ambitious. A useful method must
change a measurable behavior under a fair comparison and fit the available compute and time.

Dr. Niu's work emphasizes software quality, benchmark validity, requirements, traceability, fault
localization, testing, and trustworthy empirical evidence. A strong task should therefore connect an
agent intervention to executable evidence and analyze when it works or fails.

## Unfrozen Starting Hypothesis

One promising direction is an **evidence-grounded scientific-context gate**:

> Before repair, require each proposed scientific constraint to be linked to repository evidence, an
> executable probe or test, and a stated falsification condition. Discard or down-weight guidance
> that cannot be grounded.

A possible controlled comparison is:

1. no auxiliary scientific guidance;
2. the benchmark's raw scientific guidance; and
3. the same agent/model/budget with the evidence-grounding gate.

This is only a lead. Do not implement it until the paper's ablation protocol, available task fields,
and agent-visible context have been inspected. It must be rejected or revised if the released data
cannot support a fair test.

A graph-flavoured alternative may represent code entities, tests, issue evidence, dependencies, and
scientific constraints as a typed relation graph for fault localization. Pursue it only if a small
sample shows that the relations are recoverable without building an entire research platform.

## First Technical Session

1. Initialize Git immediately and preserve the assignment and this context in an initial commit.
2. Read the assignment, paper v2, repository README, dataset contract, architecture, and runner docs.
3. Inspect the local machine, Docker/architecture compatibility, available model routes, and likely
   cost. Do not spend money or start a large model run without Rajarshi's approval.
4. Materialize one or two unrestricted tasks and run the documented no-agent infrastructure smoke.
5. Inspect 5-10 tasks across several domains, including task fields, scientific guidance, tests,
   verifier behavior, expected runtime, and failure observability.
6. Propose at most three research questions. For each, report the required intervention, baseline,
   measurable outcome, expected failure mode, compute estimate, and the fastest falsification test.
7. Ask Rajarshi to freeze one question, the subset rule, baselines, and budget before substantive
   outcome-producing experiments.

Do not begin with a full-dataset run.

## Experimental Standards

- Define task inclusion/exclusion rules before seeing comparative outcomes.
- Prefer unrestricted-license tasks unless there is a clear reason and explicit approval to opt in.
- Keep the model, harness, token/time limits, attempts, tools, and environment equal across methods.
- Include at least one credible baseline; do not compare against an intentionally weak prompt.
- Treat verifier success as the primary outcome. Record Fail2Pass, Pass2Pass, Pass@1, token use,
  runtime, and failure categories when available and meaningful.
- Preserve raw trajectories, patches, verifier output, configuration, selection metadata, and failed
  runs. Never silently remove inconvenient observations.
- Separate exploratory trials from the locked evaluation set.
- Avoid significance claims unsupported by sample size. Emphasize effect estimates, paired outcomes,
  uncertainty, and concrete failure analysis.
- Run a clean reproduction from documented commands before finalizing the report.

## Repository Hygiene

- Keep secrets outside the repository and image build contexts. Never commit API keys or tokens.
- Use small, meaningful commits from the beginning; do not manufacture history at the end.
- Keep generated benchmark images, large caches, and bulky raw artifacts out of Git.
- Suggested evolving records: `DECISIONS.md`, `EXPERIMENTS.md`, machine-readable run configs, and a
  final `README.md`. Do not create elaborate structure before it is needed.
- Every reported number must trace to a preserved run artifact and exact task list.

## Working Schedule

- Sep 3-4: source reading, environment check, task inspection, smoke run, and question freeze.
- Sep 5-7: implement and smoke-test the baseline and proposed method.
- Sep 8-11: run the locked experiment and preserve outputs.
- Sep 12: analyze failures and run at most one justified ablation.
- Sep 13-14: write the report and reproduction README.
- Sep 15: clean reproduction, report rendering, link/claim QA, and submission package.
- Sep 16-17: buffer and interview preparation; do not plan core research for this buffer.

## Communication With Rajarshi

Keep updates concise. Surface one consequential scientific or budget decision at a time. Explain the
evidence and tradeoff, then let Rajarshi choose. Do not bury him in long generated notes or silently
turn a tentative hypothesis into the project direction.
