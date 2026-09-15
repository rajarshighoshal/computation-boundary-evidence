# Reproduction

Everything below runs on one laptop (macOS, Docker Desktop, 8 CPUs, ~16 GB for Docker).
No cloud resources are used. Total measured model spend for all runs is recorded in the
receipts; the 30-task extractor validation uses **zero model calls**.

## Prerequisites

- Python 3.12 venv with the repository's dependencies installed (`.venv/`).
- Docker running; benchmark task images are pulled/built on first use.
- `DEEPSEEK_API_KEY` in the environment (host-side only; never mounted into containers).
- Joern on `PATH` is optional; it enables host-side C/C++/Python parsing, dataflow and the
  semantic layer of boundary classification. Fortran/MATLAB use the tree-sitter frontends.

## 1. Verify the extractor (no model calls)

```bash
SCICONSORT_RESTRICTED_OPTIN=1 .venv/bin/python -m scicontext.cli pilot \
  --workspace . --config configs/extractor-validation-30.json \
  --output runs/extractor-validation-30v2 --execute --extract-only
.venv/bin/python scripts/extractor_report.py runs/extractor-validation-30v2
```

Expected (as reported): 30/30 `prepared_graph`; every violated locus preserved;
in-container self-checks pass. Each job directory contains `run.json`, the science store
under `agent-host/science/`, the construction report and `agent-host/self-check.json`.
Note the `-host` suffix: host bookkeeping is deliberately kept out of the container-visible
`/logs/agent` bind (arm isolation).

## 2. One paired repair attempt (paid)

```bash
SCICONSORT_RESTRICTED_OPTIN=1 .venv/bin/python -m scicontext.cli pilot --workspace . \
  --config configs/development-e2e-check.json \
  --output runs/development-e2e-check-v5 --execute
```

Arms are matched: identical model, tools (shell from the start), budget and base
instructions; the science arm additionally receives the graph tools. The official verifier
scores both arms; see `jobs/*/task_*/verifier/reward.json` and `summary/summary.json`.
Reported pair (task 009, v5): both arms reward 1.0; science used less work time and fewer
output tokens; zero provider retries.

## 3. Development and locked evaluations

```bash
# Full development workload (30 tasks x 2 arms, 40 concurrent)
SCICONSORT_RESTRICTED_OPTIN=1 .venv/bin/python -m scicontext.cli pilot --workspace . \
  --config configs/deepseek-dev30-v3.json --output runs/deepseek-dev30-v3 --execute

# Locked-89 evaluation, three replicate runs for repeated measures
bash scripts/run_locked89_k3.sh
```

## 4. Regenerate every number in the report

All figures come from receipts, not prose:

```bash
# Cross-run per-task truth tables, discordants, resources, transitions
.venv/bin/python scripts/compare_dev_runs.py \
    runs/deepseek-development-e2e-40-v1 runs/deepseek-dev30-contracts-low-v1 \
    runs/deepseek-dev30-v3 --output results/dev-comparison.json

# Selection-content audit (independent reviewer; no model calls by the pipeline)
#  -> results/context-recheck-v10-audit.json
# Arm isolation and delivery audit (both directions)
#  -> results/isolation-delivery-audit-v1.json
# Four-run pooled consolidation and task stability
#  -> results/dev30-four-run-consolidation.json
```

Scheduler status labels can mislabel cleanup timeouts as `infrastructure_failure`;
`run.json` stage records and `verifier/reward.json` are the authority, and every analysis
script here reads those, not the labels.

## 5. Task IDs

- Development partition (30, frozen split `configs/interactive-science.split.json`):
  001 002 004 005 006 008 009 010 014 016 019 024 025 027 028 045 051 058 061 070 073 076
  077 078 080 091 099 104 114 119.
- Locked evaluation: the remaining 89 task IDs in `configs/interactive-science.split.json`
  (`locked_evaluation_task_ids`).

## 6. Notes

- Commits during a run are harmless: trials execute from the frozen source snapshot
  (`runs/<run>/frozen-source/`), and HEAD drift is recorded in receipts
  (`head_at_launch`/`head_drift`), never aborted.
- Restricted-license tasks require `SCICONSORT_RESTRICTED_OPTIN=1`; the frozen split lists
  them.
- Provider disclosure and the division of work: see `docs/AI_DISCLOSURE.md`.
