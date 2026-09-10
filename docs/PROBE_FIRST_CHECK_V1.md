# Task-local extraction checks

Development extraction quality only: these checks do not measure repair gains. No repair or hidden-test artifacts are included. Source matches and quantity bindings establish traceability, not scientific correctness. Unknown alignments remain unresolved.

Schedule: completed. Summary audit: verified.

| Task | Run status | Extraction stage | Handoff status | Completed | Usable graph | Graph receipt | Seconds | Accepted claims | Source-matched implementations | Matched quantity bindings | Unknown alignments |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 091 | completed | completed | usable_graph | True | True | verified | 230.51 | 1 | 0 | 2 | 1 |
| 114 | completed | completed | usable_graph | True | True | verified | 134.13 | 1 | 1 | 3 | 1 |

| Task | Input | Cached input (subset) | Output | Reasoning (output subset) | Total |
| --- | --- | --- | --- | --- | --- |
| 091 | unknown | unknown | unknown | unknown | unknown |
| 114 | 173485 | 136704 | 2638 | 110 | 176123 |

Total = input + output. Cached input and reasoning are already included. Missing usage and incomplete-stage costs remain unknown. Missing graphs and incomplete stages do not produce zero quality counts.

Attempted extraction calls are shown below. The task totals above include each call once.

| Task | Call | Status | Input | Cached input (subset) | Output | Reasoning (output subset) | Total |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 091 | extract_draft | completed | 135512 | 108672 | 2567 | 327 | 138079 |
| 091 | extract_revision | timeout | unknown | unknown | unknown | unknown | unknown |
| 114 | extract_draft | completed | 173485 | 136704 | 2638 | 110 | 176123 |

Task 091 final-selected probe results: {"failed": 1}.
Final probes without a completed execution receipt: none.
Task 091 attempted probe round history (may include superseded interpretations):
| Round | Phase | Declared IDs | Recorded result statuses |
| --- | --- | --- | --- |
| 1 | probes | p1 | {"failed": 1} |

Task 114 final-selected probe results: {"failed": 1}.
Final probes without a completed execution receipt: none.
Task 114 attempted probe round history (may include superseded interpretations):
| Round | Phase | Declared IDs | Recorded result statuses |
| --- | --- | --- | --- |
| 1 | probes | p1 | {"failed": 1} |


A completed run means the scheduled workflow returned; its extraction stage can still time out without delivering a handoff. The stage and handoff columns above distinguish these outcomes.

## Task 091 phase timing

| Phase | Status | Allowance seconds | Elapsed seconds |
| --- | --- | --- | --- |
| extract_draft | completed | 225.00 | 102.76 |
| prepare | ready | 30.00 | 1.17 |
| assemble_initial | usable_graph | 197.24 | 17.41 |
| probes | completed | 50.00 | 2.06 |
| assemble_observed | usable_graph | 177.77 | 17.41 |
| extract_revision | timeout | 85.36 | 75.15 |

| Call | GNU command allowance seconds | Interpretation elapsed seconds |
| --- | --- | --- |
| extract_draft | 210.65 | 102.76 |
| extract_revision | 71.00 | 75.15 |

## Task 114 phase timing

| Phase | Status | Allowance seconds | Elapsed seconds |
| --- | --- | --- | --- |
| extract_draft | completed | 225.00 | 105.56 |
| prepare | ready | 30.00 | 1.90 |
| assemble_initial | usable_graph | 194.44 | 3.46 |
| probes | completed | 50.00 | 6.12 |
| assemble_observed | usable_graph | 184.86 | 3.28 |
| extract_revision | not_run | 106.58 | 0.00 |

| Call | GNU command allowance seconds | Interpretation elapsed seconds |
| --- | --- | --- |
| extract_draft | 210.64 | 105.56 |


Probe outcomes describe execution on the original implementation; they are not scientific proof. The JSON report preserves phases, assembly relations and dependency links when recorded, analysis coverage, source selection, setup, available session headers, and protocol provenance.
