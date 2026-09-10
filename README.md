# Scientific context for Codex repair

An experimental preparation stage for SWE-bench Science. It combines source-backed expression alignment, conditional scientific operation interpretation, and dimension/scale/shape analysis before a fresh Codex repair session.

The controlled comparison is ordinary Codex versus extraction followed by repair. Both use GPT-6 Astra/high and a 30-minute total agent allowance; extraction consumes at most six minutes of the treatment allowance. This implementation is a research prototype, not a scientific-correctness prover.

The runner reuses Pier's standard Codex launch and subscription authentication. Docker provides isolation; there is no extra Codex sandbox policy. The earlier development pilot passed both tasks in both conditions, with greater elapsed time for context and no observed success gain. The revised bounded extractor has now passed extraction-only checks without timing out; repair effectiveness has not been re-evaluated for this revision. See [pilot results](docs/PILOT_RESULTS.md), [extractor verification](docs/EXTRACTOR_VERIFICATION.md), and [runtime status](docs/RUNTIME_STATUS.md).

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

The current extractor uses code-owned indexing, citations, graph assembly and checks; the LLM saves compact scientific annotations and optional probe scripts. Preparation overlaps interpretation, and independent probes can run concurrently. The shared extraction allowance includes bounded interpretation, probes, collection and shutdown. See [the implemented contract](docs/EXTRACTION_V2.md).

Verify only extraction on the development tasks, without repair or private verification:

```bash
uv run --no-sync scicontext pilot --extract-only --execute --output runs/extractor-annotations-v2
```

Inspect the exact schedule without inference:

```bash
uv run --no-sync scicontext pilot --output runs/pilot-v3
```

Run a bounded subscription smoke first, then the approved two-task pilot:

```bash
uv run --no-sync scicontext pilot --smoke --execute --output runs/standard-smoke-v2
uv run --no-sync scicontext pilot --execute --output runs/pilot-v3
```

Use a fresh output directory for every attempt. Existing attempts are never overwritten. The pilot runs one attempt per condition on tasks **002 and 077**, with counterbalanced condition order. The CLI deliberately does not launch unrestricted full-suite experiments. Full 119-task evaluation follows pilot review and the benchmark's restricted-license opt-in decision.

Authentication defaults to the saved ChatGPT cache at `~/.codex/auth.json`; `--auth-file` accepts a private subscription cache. API-key auth is rejected. Upstream Pier uploads and removes its temporary authentication files. They stay outside source/Git and image builds, but commands inside the same container can access them. This is the documented standard container mode, not a hostile-code credential-isolation system. Do not mount personal home directories or a Docker socket into task containers, and review raw logs before publishing.

Codex 0.153.4 uses the normal Linux x64 binary in the pinned amd64 task image, including on Apple Silicon through Docker's existing emulation. The standard Pier command does not create the extra nested sandbox that caused the earlier `/proc` failure. Both conditions use the same execution path. Docker memory allocation still needs to accommodate the task's declared resources before locked evaluation.

## Recompute results

```bash
uv run --no-sync scicontext summarize runs/pilot-v2/jobs --output runs/pilot-v2/summary
uv run --no-sync python scripts/recompute_results.py runs/pilot-v2/jobs --verify runs/pilot-v2/summary/summary.json
```

The independent script does not import the application aggregator. Summaries retain missing pairs, failed attempts, official reward versus exact private success, stage usage, timing, provenance and development exposure. Fail2Pass/Pass2Pass remain unavailable unless original baseline and candidate private test identities can be matched; aggregate pass counts cannot reconstruct them.

Raw job directories preserve stage JSONL/stderr, partial/final graphs, semantic findings, source evidence, submitted patches and official verifier output. Do not feed held-out verifier feedback back into the extractor or silently rerun tuned methods on the same evaluation set.

## Research status

See `WORK_LOG.md` for the current verified state. Task 002's private failures were inspected during the initial infrastructure session; both 002 and 077 are development tasks. Results from them are exploratory, not untouched final evaluation.

The original assignment requires a four-page main report plus up to one references page, exact evaluated task IDs, genuine commit history, reproduction commands and AI disclosure. See `docs/AI_DISCLOSURE.md`.
