# Task-local extraction checks

Development extraction quality only: these checks do not measure repair gains. No repair or hidden-test artifacts are included. Source matches and quantity bindings establish traceability, not scientific correctness. Unknown alignments remain unresolved.

Schedule: completed. Summary audit: verified.

| Task | Run status | Extraction stage | Handoff status | Completed | Usable graph | Graph receipt | Seconds | Accepted claims | Source-matched implementations | Matched quantity bindings | Unknown alignments |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 091 | completed | completed | usable_graph | True | True | verified | 222.17 | 2 | 0 | 3 | 2 |
| 114 | completed | timeout | no_valid_graph | False | unknown | missing | 140.90 | unknown | unknown | unknown | unknown |

| Task | Input | Cached input (subset) | Output | Reasoning (output subset) | Total |
| --- | --- | --- | --- | --- | --- |
| 091 | 321199 | 250496 | 4219 | 130 | 325418 |
| 114 | unknown | unknown | unknown | unknown | unknown |

Total = input + output. Cached input and reasoning are already included. Missing usage and incomplete-stage costs remain unknown. Missing graphs and incomplete stages do not produce zero quality counts.

Attempted extraction calls are shown below. The task totals above include each call once.

| Task | Call | Status | Input | Cached input (subset) | Output | Reasoning (output subset) | Total |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 091 | extract_draft | completed | 142186 | 111872 | 2158 | 61 | 144344 |
| 091 | extract_revision | completed | 179013 | 138624 | 2061 | 69 | 181074 |
| 114 | extract_draft | timeout | unknown | unknown | unknown | unknown | unknown |

Task 091 probe results: none declared.
Task 114 probe results: unknown.

A completed run means the scheduled workflow returned; its extraction stage can still time out without delivering a handoff. The stage and handoff columns above distinguish these outcomes.

## Task 091 phase timing

| Phase | Status | Allowance seconds | Elapsed seconds |
| --- | --- | --- | --- |
| extract_draft | completed | 135.00 | 92.94 |
| prepare | ready | 30.00 | 1.17 |
| assemble_initial | usable_graph | 72.06 | 12.06 |
| extract_revision | completed | 165.00 | 89.21 |
| assemble_final | usable_graph | 105.79 | 12.38 |

| Call | GNU command allowance seconds | Interpretation elapsed seconds |
| --- | --- | --- |
| extract_draft | 120.69 | 92.94 |
| extract_revision | 150.65 | 89.21 |

## Task 114 phase timing

| Phase | Status | Allowance seconds | Elapsed seconds |
| --- | --- | --- | --- |
| extract_draft | timeout | 135.00 | 124.73 |
| prepare | ready | 30.00 | 1.95 |
| assemble_initial | invalid_or_missing_annotations | 40.27 | 0.77 |

| Call | GNU command allowance seconds | Interpretation elapsed seconds |
| --- | --- | --- |
| extract_draft | 120.68 | 124.73 |


Probe outcomes describe execution on the original implementation; they are not scientific proof. The JSON report preserves phases, assembly relations and dependency links when recorded, analysis coverage, source selection, setup, available session headers, and protocol provenance.
