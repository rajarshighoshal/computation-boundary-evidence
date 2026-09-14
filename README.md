# Interactive scientific understanding for repair

This study asks whether a compact, queryable scientific-code representation helps a repair agent
understand and repair SWE-bench Science tasks under the same total allowance as ordinary repair.

## Current method
Static preparation indexes public files and gives the agent a tiny task map. The same agent uses
science.find and science.inspect to retrieve quantities, expressions, conditions and source
definitions on demand. science.record_model saves its source-linked scientific working model and
unlocks ordinary repair tools. The science tool remains available during repair.

There is no separate interpretation model, mandatory reproduction/build, or second task container.
Python/native/Cython parsers supply structure; targeted Joern analysis adds data/control flow when
available. Unsupported analysis is explicit. Scientific interpretation belongs to the agent; source
IDs and tool use do not prove scientific correctness.

The ordinary baseline has no extra scientific-planning instruction. The comparison measures the
whole added workflow, not an isolated component effect. No repair improvement is established yet.

## Install and verify
Use Python3.12, uv, Docker linux/amd64 support, and the pinned dependencies:

```bash
uv sync --python 3.12 --locked --extra test --extra runner
uv run --no-sync pytest -q
```

Joern is an optional host analyzer; unavailable frontends are reported, not silently replaced by
scientific claims. Native source frontends do not execute candidate code.

## Frozen development/evaluation split
configs/interactive-science.split.json fixes30 development tasks and89 locked evaluation tasks.
It includes13 documented design cases and17 seeded random unrestricted cases. Historical pipeline
activity, method-development use and private-diagnostic exposure are distinct metadata.
The locked set is not claimed to be historically untouched. License gates remain explicit.

## Run the approved pilot
The initial paired pilot uses001/009/058/091/114, one attempt per arm, DeepSeek Flash/high,
1800seconds including preparation, queries and repair, and rolling concurrency2.

```bash
uv run --no-sync scicontext pilot --config configs/interactive-five.json --output runs/new-pilot
uv run --no-sync scicontext pilot --config configs/interactive-five.json --output runs/new-pilot --execute
```

The first command is a dry run; use a fresh output directory for execution. The DeepSeek key is
read from DEEPSEEK_API_KEY on the host and is never mounted in the task container.
No Claude calls are used. Larger cohorts require a reviewed pilot and explicit launch approval.

## What to inspect
Each trial preserves the agent conversation/tool results, model submission, scientific-store
artifacts, patch, verifier output, token accounting and timing. Inspect the pre-edit model and
subsequent repair: correct scientific relationships, useful implementation links, no invented cause.

```bash
uv run --no-sync scicontext summarize /path/to/run/jobs --output /path/to/summary
```

Cached input is part of input tokens; reasoning is part of output tokens. Missing costs remain
unknown. Forty scheduler slots do not imply this laptop can run forty heavy scientific workloads.

The approved design is in [RESEARCH_PLAN.md](RESEARCH_PLAN.md), tool contract in
[docs/OBJECT_ENRICHMENT.md](docs/OBJECT_ENRICHMENT.md), and live progress in [WORK_LOG.md](WORK_LOG.md).
Old one-shot/probe-first experiments are preserved separately and are not results of this method.
