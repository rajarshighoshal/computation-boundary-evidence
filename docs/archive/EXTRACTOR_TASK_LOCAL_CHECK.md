# Task-local extraction checks

Development extraction quality only: these checks do not measure repair gains. No repair or hidden-test artifacts are included. Source matches and quantity bindings establish traceability, not scientific correctness. Unknown alignments remain unresolved.

Schedule: completed. Summary audit: verified.

| Task | Status | Completed | Usable graph | Graph receipt | Seconds | Accepted claims | Source-matched implementations | Matched quantity bindings | Unknown alignments |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 091 | completed | True | True | verified | 145.85 | 3 | 3 | 3 | 3 |
| 009 | completed | True | True | verified | 140.64 | 3 | 3 | 5 | 2 |

| Task | Input | Cached input (subset) | Output | Reasoning (output subset) | Total |
| --- | --- | --- | --- | --- | --- |
| 091 | 130704 | 106624 | 2933 | 193 | 133637 |
| 009 | 117345 | 83328 | 2990 | 24 | 120335 |

Total = input + output. Cached input and reasoning are already included. Missing usage and incomplete-stage costs remain unknown. Missing graphs and incomplete stages do not produce zero quality counts.

Task 091 probe results: none declared.
Task 009 probe results: {"failed": 1}.

Probe outcomes describe execution on the original implementation; they are not scientific proof. The JSON report preserves phases, assembly relations and dependency links when recorded, analysis coverage, source selection, setup, available session headers, and protocol provenance.
