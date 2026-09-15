# Interactive scientific understanding for repair

This study asks whether a compact, queryable scientific-code representation helps a repair agent
understand and repair SWE-bench Science tasks under the same total allowance as ordinary repair.

## Current method
Preparation runs the public workflow under an observer, builds a source packet with dynamic
file ranking (trace-executed files first, then callee/caller boundaries, then task mentions; the
former 24-file alphabetical cutoff is gone) and merges a connected task graph before the model
starts. The same agent uses science_find and science_inspect to retrieve quantities, expressions,
conditions and source definitions on demand — including distilled, language-agnostic interface
contracts for C/C++/Fortran/MATLAB/Cython code (boundary signatures, external-library calls with
provider attribution and explicit `unknown_external` labels, governing conditions, return
expressions). science_note optionally saves a revisable, source-linked working model. Both arms
have ordinary repair tools from the start.

There is no separate interpretation model, hard planning gate or second task container.
Python/native/Cython parsers supply structure; Joern supplies parsing, dataflow and the semantic
layer of boundary classification on demand (C/C++/Python; Fortran/MATLAB use the tree-sitter
frontends and declarative `use`/`include` parsing). Unsupported analysis is explicit. Scientific
interpretation belongs to the agent; source IDs and tool use do not prove scientific correctness.

The ordinary baseline has no extra scientific-planning instruction. The comparison measures the
whole added workflow, not an isolated component effect.

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

## Runs so far (interim, all receipts preserved under runs/)
Four independent development evaluations of the fixed30-task set (240 official-verifier
attempts; DeepSeek V4.1 Flash) plus a k=3 locked-89 evaluation:

```bash
# Paired check, one task, both arms
SCICONSORT_RESTRICTED_OPTIN=1 uv run --no-sync scicontext pilot --config configs/development-e2e-check.json --output runs/development-e2e-check-v5 --execute
# Full development workload (30 tasks x 2 arms, 40 concurrent)
SCICONSORT_RESTRICTED_OPTIN=1 uv run --no-sync scicontext pilot --config configs/deepseek-locked89-k1.json --output runs/deepseek-locked89-k1-v1 --execute
# Locked-89 evaluation, three replicate runs (k=3) for repeated measures
bash scripts/run_locked89_k3.sh
```

Consolidated evidence (all with exact task IDs and recomputable receipts):
`results/dev30-four-run-consolidation.json` (task stability across runs), 
`results/context-recheck-v10-audit.json` (selection content audit), 
`results/isolation-delivery-audit-v1.json` (arm isolation and delivery verification).

Honest headline: across the four development evaluations the arms are statistically identical in
solve rate (43 vs 44 of 120 paired attempts, within a measured ±3/30 single-run noise floor) while
the science arm consistently uses 17–25% fewer input tokens; task 077 is solved 3/4 times with the
graph and 0/4 without it.

## What to inspect
Each trial preserves the agent conversation/tool results, model submission, scientific-store
artifacts, patch, verifier output, token accounting and timing. Inspect what the agent actually
queries and receives: correct scientific relationships, useful implementation links, no invented
cause. A missing optional model is not a failed trial; graph availability does not prove tool use.

```bash
uv run --no-sync scicontext summarize /path/to/run/jobs --output /path/to/summary
```

Cached input is part of input tokens; reasoning is part of output tokens. Missing costs remain
unknown. Apparent statuses from the scheduler can mislabel cleanup timeouts; verifier receipts and
`run.json` stage records are the authority.

The approved design is in [RESEARCH_PLAN.md](RESEARCH_PLAN.md), current method details in
[docs/METHOD.md](docs/METHOD.md), frozen-run and boundary-contract design in
[docs/FROZEN_RUNS_AND_BOUNDARY_CONTRACTS.md](docs/FROZEN_RUNS_AND_BOUNDARY_CONTRACTS.md), and live
progress in [WORK_LOG.md](WORK_LOG.md). Old one-shot/probe-first experiments are preserved
separately and are not results of this method.
