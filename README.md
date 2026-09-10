# Scientific context for Codex repair

An experimental preparation stage for SWE-bench Science. It combines source-backed expression alignment, conditional scientific operation interpretation, and dimension/scale/shape analysis before a fresh Codex repair session.

The research comparison is ordinary Codex versus extraction followed by repair under the same total agent allowance. Current initial checks use GPT-6 Astra/medium; earlier checks used high. These are exploratory feasibility checks, not a locked experiment. This implementation is a research prototype, not a scientific-correctness prover.

The runner reuses Pier's Codex launch and subscription authentication. Extraction uses Codex's built-in read-only mode; code saves its returned annotations and probe scripts. Repair retains standard container execution. There is no custom Git source-change guard. See [initial high-effort results](docs/RANDOM_FIVE_HIGH_RESULTS.md), [qualitative notes](docs/RANDOM_FIVE_NOTES.md), and [runtime status](docs/RUNTIME_STATUS.md). Historical development results remain separate.

The current approved revision adds [scientific-object bindings and a bounded feedback correction](docs/SEMANTIC_FEEDBACK.md).
Local tests check the implementation; improved live extraction quality and repair performance have
not yet been established for this revision. Earlier results below evaluate their recorded versions.
The [local verification](docs/SEMANTIC_FEEDBACK_VERIFICATION.md) is complete, including a preserved-source
regression and its fix. Parallel mode now supports two simultaneous attempts with separate receipts.

The original random-five checks are complete: [outcomes and token accounting](docs/INITIAL_FIVE_OVERVIEW.md).
The task-local redesign is now implemented and has separate [extraction-only results](docs/EXTRACTOR_TASK_LOCAL_CHECK.md).
It improves source retrieval and binding coverage on the development examples. The restarted
[end-to-end comparison and stage-token accounting](docs/TASK_LOCAL_FIVE_V2_RESULTS.md) are complete;
they do not demonstrate a repair-success improvement. See the [paired qualitative review](docs/TASK_LOCAL_FIVE_V2_NOTES.md)
for scientific ambiguities and remaining mechanical limitations.
The later [task001 failure diagnosis](docs/TASK001_FAILURE_DIAGNOSIS.md) inspects the saved assertion
and reproduces a candidate axis-boundary mechanism on a separate public counterexample, without
new benchmark-agent attempts or method changes.

The later end-to-end comparison was stopped by the user after an assembly sub-limit failure;
[partial records](docs/TASK_LOCAL_FIVE_INTERRUPTED.md) remain separate. That premature cap is now
[fixed and replay-tested](docs/ASSEMBLY_TIMEOUT_FIX.md), and a
[single full extraction check](docs/ASSEMBLY_BUDGET_CHECK.md) passed its timing/artifact criteria.
The user-authorized comparison in `runs/task-local-five-v2` completed with the frozen
`configs/task-local-five-v1.json`. See `WORK_LOG.md` for verification receipts. These are previously inspected
development tasks; useful scientific content is not guaranteed merely by timely output.

## Layout

```text
src/scicontext/       Python implementation and native runner adapter
tests/               Synthetic and integration tests
prompts/             Versioned extractor and repair guidance
configs/             Explicit experiment configuration
scripts/             Release restoration and independent result audit
docs/                Interfaces, method details, and disclosures
results/             Compact committed experimental summaries
RESEARCH_PLAN.md     Approved research/implementation plan
WORK_LOG.md          Canonical milestone status and verification receipts
vendor/              Pinned upstream source (ignored)
data/                Pinned dataset and materialized selections (ignored)
runs/                Raw run artifacts and generated summaries (ignored)
.cache/              Verified Codex/helper assets (ignored)
```

## Install and test

Requires Python 3.12, uv, Docker with amd64 support, and a Codex subscription login for live trials.

```bash
uv sync --python 3.12 --locked --extra test --extra runner
uv run --no-sync pytest -q
uv run --no-sync scicontext prepare --task-id 002,077
```

The release is pinned to Git commit `42e7e97915ff7d73436a5d37b5cbe6b77e9c2a00` and Hugging Face revision `d8bdbcb4ecb2b565686382459c815d2b6291fd31`. `data/release-receipt.json` records hashes and image references. Existing modified inputs are rejected rather than overwritten.

## Inspect the scientific helpers

```bash
uv run --no-sync scicontext schema --output .cache/graph.schema.json
uv run --no-sync scicontext index --root /path/to/public/task source/model.py
uv run --no-sync scicontext cite --root /path/to/public/task paper.md 10 20
uv run --no-sync scicontext expression 'sum(density * volume)'
uv run --no-sync scicontext analyze --root /path/to/public/task --graph /path/to/graph.json --output /path/to/checkpoints
```

The graph uses evidence IDs, exact source lines/hashes, quantities, claims, assumptions and observations. Dimensions and bindings use arrays, matching the strict JSON output schema. Mechanical checks do not establish the truth of scientific assumptions. The renderer retains unsupported regions and conflicting evidence.

## Run the development pilot

The current extractor uses code-owned indexing, citations, entity bindings, graph assembly and checks. A read-only draft is followed by public-probe feedback and at most one bounded correction. Code saves outputs and keeps call artifacts separate. Preparation overlaps interpretation, and independent probes can run concurrently. The shared extraction allowance includes both model calls, probes, assembly, collection and shutdown. See [the implemented contract](docs/SEMANTIC_FEEDBACK.md).

The quota-interrupted initial run was resumed and completed without replacing tasks. Its failed
launch remains preserved. There is no unfinished initial-task pair to resume. The current
extraction-only configuration can be inspected without inference:

```bash
uv run --no-sync scicontext pilot --config configs/extractor-task-local-check.json --extract-only --output runs/extractor-task-local-check-v2
```

Do not pool different effort/method revisions into a purported uniform experiment. Use an explicit
configuration for new calls; the default development configuration is historical and uses high effort.

With an agreed model-run budget, execute only extraction, without repair or hidden tests:

```bash
uv run --no-sync scicontext pilot --config configs/extractor-task-local-check.json --extract-only --execute --output runs/extractor-task-local-check-v2
```

The implemented task-local retrieval, source-reference expansion and binding interfaces are
documented in [the historical extraction contract](docs/EXTRACTION_V2.md). The later semantic-feedback
revision adds one planned correction call inside the same budget; no larger model allowance is implied.

Use a fresh output directory for every attempt. Existing attempts are never overwritten. The default development configuration uses tasks **002 and 077**; explicit configurations support bounded selections from a materialized release receipt. Full-benchmark evaluation requires a subsequent protocol/budget decision and restricted-license opt-in where applicable.

Set `concurrency` to `2` for paired parallel execution, or retain `1` for serial. Full comparisons
drain each task's baseline/treatment pair before the next task; extraction-only checks group two
tasks. Both share Docker memory and CPU capacity. Provider/infrastructure failure stops further
admission and interrupts the active peer; a failed scientific test is retained as an outcome.

The proposed next extraction-only check can be inspected without model calls:

```bash
uv run --no-sync scicontext pilot --config configs/semantic-feedback-check-v1.json --extract-only --output runs/semantic-feedback-check-v1
```

That configuration is prepared, not authorization to execute it. Live execution requires the
separate task/budget approval requested from Rajarshi.

To inspect a reproduction of the frozen task-local comparison, materialize its existing selection
without drawing replacement tasks, then create a dry-run schedule:

```bash
uv run --no-sync scicontext prepare --task-id 091,058,009,114,001 --receipt data/random-five-v1-release.json
uv run --no-sync scicontext pilot --config configs/task-local-five-v1.json --output runs/task-local-five-reproduction
```

Actual inference requires a newly agreed budget and `--execute` with a fresh output directory.
Use the evaluated method revision recorded in the report; these previously inspected tasks do
not constitute an untouched evaluation set.

Authentication defaults to the saved ChatGPT cache at `~/.codex/auth.json`; `--auth-file` accepts a private subscription cache. API-key auth is rejected. Upstream Pier uploads and removes its temporary authentication files. They stay outside source/Git and image builds, but commands inside the same container can access them. This is the documented standard container mode, not a hostile-code credential-isolation system. Do not mount personal home directories or a Docker socket into task containers, and review raw logs before publishing.

Repair uses pinned Codex's Linux x64 binary in the original amd64 task image. On an ARM Docker host, extraction uses the native ARM Codex build so its built-in read-only mode works; it does not change the scientific image or repair runtime. No bespoke permission profile is added. Setup receipts record both architectures. The user-approved [temporary Docker memory increase](results/docker-memory-change.json) was applied only after the comparison finished. Historical results retain their original resource limitation; the new allocation applies to subsequent work and must still be checked against each selected task's requirements.

## Recompute results

```bash
uv run --no-sync scicontext summarize runs/pilot-v2/jobs --output runs/pilot-v2/summary
uv run --no-sync python scripts/recompute_results.py runs/pilot-v2/jobs --verify runs/pilot-v2/summary/summary.json
uv run --no-sync python scripts/report_initial_five.py
uv run --no-sync python scripts/report_task_local_extractor.py --run-root runs/extractor-task-local-check-v1 --json-output results/extractor-task-local-check-v1.json --markdown-output docs/EXTRACTOR_TASK_LOCAL_CHECK.md
uv run --no-sync python scripts/report_comparison.py --run-root runs/task-local-five-v2 --summary results/task-local-five-v2.json --output docs/TASK_LOCAL_FIVE_V2_RESULTS.md
uv run --no-sync python scripts/audit_session_tokens.py --run-root runs/task-local-five-v2 --output results/task-local-five-v2-token-audit.json
```

The independent script does not import the application aggregator. Summaries retain missing pairs, failed attempts, official reward versus exact private success, stage usage, timing, provenance and development exposure. Fail2Pass/Pass2Pass remain unavailable unless original baseline and candidate private test identities can be matched; aggregate pass counts cannot reconstruct them.

Raw job directories preserve stage JSONL/stderr, partial/final graphs, semantic findings, source evidence, submitted patches and official verifier output. Do not feed held-out verifier feedback back into the extractor or silently rerun tuned methods on the same evaluation set.

## Research status

See `WORK_LOG.md` for the current verified state. Task 002's private failures were inspected during the initial infrastructure session; both 002 and 077 are development tasks. Results from them are exploratory, not untouched final evaluation.

The original assignment requires a four-page main report plus up to one references page, exact evaluated task IDs, genuine commit history, reproduction commands and AI disclosure. See `docs/AI_DISCLOSURE.md`.
