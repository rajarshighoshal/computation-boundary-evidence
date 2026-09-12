# Semantic extraction: runtime and incomplete usage

Schedule elapsed (including setup and cleanup): 275.89 seconds.

Execution policy: `{"admission": "two_task_extraction_groups", "concurrency": 2, "pier_concurrency_per_process": 1, "shared_resources": true}`.

| Task | Extraction stage | Handoff | Cap seconds | Elapsed seconds | Unused allowance seconds |
| --- | --- | --- | --- | --- | --- |
| 091 | completed | usable_graph | 360.00 | 230.51 | 129.49 |
| 114 | completed | usable_graph | 360.00 | 134.13 | 225.87 |

| Task | Call | Status | GNU command allowance seconds | Interpretation elapsed seconds |
| --- | --- | --- | --- | --- |
| 091 | extract_draft | completed | 210.65 | 102.76 |
| 091 | extract_revision | timeout | 71.00 | 75.15 |
| 114 | extract_draft | completed | 210.64 | 105.56 |

## Partial counters—not full costs

These are the last observed cumulative session counters before a timeout. Later or in-flight usage may be absent. Do not substitute these values for the unknown full-stage cost, combine them into a complete-trial total, or add cached/reasoning subsets twice.

| Task | Call | Counter timestamp | Input | Cached input | Output | Reasoning output | Observed total |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 091 | extract_revision | 2026-09-10T20:56:08.225Z | 80576 | 46208 | 438 | 31 | 81014 |

## Resource samples

| Time | Current-trial containers | Approx. summed reported MiB |
| --- | --- | --- |

Summing Docker's rounded CLI values gives approximate container-reported memory, not VM-wide memory pressure or a guaranteed peak. These sparse samples cannot rule out an unobserved spike or measure parallel speedup against a matched serial run.
