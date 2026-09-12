# Semantic extraction: runtime and incomplete usage

Schedule elapsed (including setup and cleanup): 270.52 seconds.

Execution policy: `{"admission": "two_task_extraction_groups", "concurrency": 2, "pier_concurrency_per_process": 1, "shared_resources": true}`.

| Task | Extraction stage | Handoff | Cap seconds | Elapsed seconds | Unused allowance seconds |
| --- | --- | --- | --- | --- | --- |
| 091 | completed | usable_graph | 360.00 | 222.17 | 137.83 |
| 114 | timeout | no_valid_graph | 360.00 | 140.90 | 219.10 |

| Task | Call | Status | GNU command allowance seconds | Interpretation elapsed seconds |
| --- | --- | --- | --- | --- |
| 091 | extract_draft | completed | 120.69 | 92.94 |
| 091 | extract_revision | completed | 150.65 | 89.21 |
| 114 | extract_draft | timeout | 120.68 | 124.73 |

## Partial counters—not full costs

These are the last observed cumulative session counters before a timeout. Later or in-flight usage may be absent. Do not substitute these values for the unknown full-stage cost, combine them into a complete-trial total, or add cached/reasoning subsets twice.

| Task | Call | Counter timestamp | Input | Cached input | Output | Reasoning output | Observed total |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 114 | extract_draft | 2026-09-10T19:33:04.274Z | 137826 | 106368 | 719 | 30 | 138545 |

## Resource samples

| Time | Current-trial containers | Approx. summed reported MiB |
| --- | --- | --- |
| 2026-09-10T19:33:51.458784+00:00 | 8 | 839.98 |
| 2026-09-10T19:36:46.004343+00:00 | 0 | 0.00 |

Summing Docker's rounded CLI values gives approximate container-reported memory, not VM-wide memory pressure or a guaranteed peak. These sparse samples cannot rule out an unobserved spike or measure parallel speedup against a matched serial run.
