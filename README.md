# Scientific context for Codex repair

An experimental preparation stage for SWE-bench Science. Code extracts objects, operation syntax,
interfaces and source references; a scientific-reading LLM attaches meanings, conventions and
assumptions to those same objects before a fresh repair session.

The research comparison is ordinary Codex versus extraction followed by repair under the same total agent allowance. Current initial checks use GPT-6 Astra/medium; earlier checks used high. These are exploratory feasibility checks, not a locked experiment. This implementation is a research prototype, not a scientific-correctness prover.

The runner reuses Pier/Codex and subscription authentication. The current scientific-object mode
uses one read-only interpretation call, with no probe/refinement loop. Code joins anchored output;
repair retains normal execution. See the [method](docs/METHOD.md) and
[enrichment contract](docs/OBJECT_ENRICHMENT.md).

[Live scientific-reading checks](docs/SCIENTIFIC_READING_V1.md) recovered substantive documented
science but exposed [poor implementation grounding](docs/SCIENTIFIC_READING_V1_NOTES.md).
The subsequent retrieval change follows public workflow references into implementation functions
and retains candidate call links. Its [live before/after check](docs/SCIENTIFIC_READING_V1_V2.md)
shows improved scientific implementation anchoring, with [documented limitations](docs/SCIENTIFIC_READING_V2_NOTES.md).
Neither a valid graph nor scientific prose demonstrates improved repair. Compiler IR is not in scope.

Historical methods/results remain separate: [initial five](docs/INITIAL_FIVE_OVERVIEW.md),
[task-local comparison](docs/TASK_LOCAL_FIVE_V2_RESULTS.md), and
[probe-first comparison](docs/PROBE_FIRST_PAIRS_V1.md). Current status is in `WORK_LOG.md`.

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

The current `scientific_objects` extractor combines code-owned structure and public-workflow
localization with one read-only scientific interpretation call. The LLM annotates existing object IDs;
it does not create structure or probes. Repair reads `scientific-guide.md` and selectively queries
the complete `scientific-graph.json`, with public passages in `scientific-sources.json`. All three are
durable files under `/opt/scicontext/context/` in the repair container, also preserved in host agent
artifacts. The prompt carries file pointers, not the full graph. Both arms use the standard
[Codex stdin prompt route](https://learn.chatgpt.com/docs/non-interactive-mode#use-codex-exec---when-stdin-is-the-prompt)
through pinned Pier's existing launch/auth lifecycle. Extraction, transfer and shutdown count inside
the science arm's total budget. Older probe-first configurations below are historical, not this method.

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

Set `concurrency` from `1` (serial) through `8`. Parallel execution uses a rolling pool: whenever
an attempt finishes, the next queued attempt is prepared and launched without waiting for its
task partner or batch. Image preparation still takes time; launches above two workers retain
the existing minimum eight-second spacing. Images are removed only after all planned arms of
their task finish. Attempts share Docker memory and CPU capacity. An attempt's preparation, provider or execution
failure is recorded without cancelling its sibling or stopping the remaining queue. No automatic
retry is made. A drained queue with failures is `completed_with_failures`; missing verifier outcomes
remain unknown. Operator cancellation, invalid global inputs or an unresolved cleanup/integrity
failure still stop the schedule. A failed scientific test is retained as an ordinary outcome.

The offline [OpenMC handoff check](results/file-handoff-check-v1.json) preserves the original graph
and all annotations, with identical host/repair-container file hashes. Reproduce it without model
or verifier calls (use a fresh output directory):

```bash
uv run --no-sync python scripts/check_file_handoff.py \
  --bundle runs/workflow-five-v1/jobs/task-058-science/task_058__y56EQiC/graph-bundle.json \
  --output runs/file-handoff-check-reproduction \
  --image docker.io/kevinxulearning/swe-bench-science-environment-python-cpp-task-058:v0.1.2@sha256:1b7822c1dbae675f2c32a19ec6cee830f93bd8248e459d3836d962805a3e680b
```

The proposed next extraction-only check can be inspected without model calls:

```bash
uv run --no-sync scicontext pilot --config configs/semantic-feedback-check-v1.json --extract-only --output runs/semantic-feedback-check-v1
```

That approved check is complete in `runs/semantic-feedback-check-v1`. Repeating it requires a fresh
output directory and a new budget decision; do not silently rerun or change settings after outcomes.

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
