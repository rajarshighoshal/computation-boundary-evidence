# Reproduction

Everything below runs on one laptop (macOS, Docker Desktop, 8 CPUs, ~9 GB for Docker).
No cloud resources are used. Total measured model spend for all runs in the report is
recorded in the receipts; the 30-task extractor validation uses **zero model calls**.

## Prerequisites

- Python 3.12 venv with the repository's `requirements` installed (`.venv/`).
- Docker running; benchmark task images are pulled/built on first use.
- `DEEPSEEK_API_KEY` (or the GLM key after the provider switch) in the environment.
- Joern on `PATH` is optional; it enables host-side C/C++ analysis on node inspection.

## 1. Verify the extractor (no model calls)

```
SCICONSORT_RESTRICTED_OPTIN=1 .venv/bin/python -m scicontext.cli pilot \
  --workspace . --config configs/extractor-validation-30.json \
  --output runs/extractor-validation-30 --execute --extract-only
.venv/bin/python scripts/extractor_report.py runs/extractor-validation-30
```

Expected (as reported): 30/30 `prepared_graph`; findings kept = loci for every task;
self-check `recorded` 29/30; `unseen refused` 28/28. Each job directory contains the
receipt (`run.json`), the exported science store (`agent/science/`), construction report
and `agent/self-check.json`.

## 2. One paired repair attempt (paid)

```
.venv/bin/python -m scicontext.cli pilot --workspace . \
  --config configs/development-e2e-check.json \
  --output runs/development-e2e-check-v1 --execute
```

Arms are matched: identical model, tools (shell from the start), budget, base instructions
and note request; the science arm additionally receives the graph tool. The official
verifier scores both arms; see `jobs/*/task_*/verifier/reward.json` and
`summary/summary.json`. Reported pair (task 009): science 9/9 private, baseline 8/9.

## 3. Regenerate every number in the report

All figures come from receipts, not prose:

```
.venv/bin/python scripts/extractor_report.py runs/extractor-validation-30   # Section 3.1 table
.venv/bin/python - <<'PY'                                                   # Section 3.2 pair
import json
s = json.load(open('runs/development-e2e-check-v1/summary/summary.json'))
for c, v in s['metrics']['all']['conditions'].items():
    print(c, v['mean_official_reward_observed'], v['resources']['duration_seconds']['observed_mean'])
PY
```

## 4. Task IDs

- Extractor validation (30, development partition, frozen split
  `configs/interactive-science.split.json`): 001 002 004 005 006 008 009 010 014 016 019
  024 025 027 028 045 051 058 061 070 073 076 077 078 080 091 099 104 114 119.
- Repair pairs (development-exposed): 009 (completed, reported); 001 058 091 114
  (see receipts at submission time).

## 5. Notes

- Do not commit while a sweep is live; the drift guard aborts queued attempts
  (this happened once; the partial run is preserved as `*-drift8`).
- The 89 locked-evaluation tasks were not accessed.
- Provider outage: DeepSeek completions hung mid-study; later attempts use GLM-5.3-Flash
  with results kept separate. See `docs/AI_DISCLOSURE.md`.
