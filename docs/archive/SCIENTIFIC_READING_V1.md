# Scientific-reading development checks

Full public task workspaces; one scientific-reading call per task. No repair or verifier runs. Annotation counts measure delivery and anchoring, not scientific correctness or repair benefit.

Schedule: completed. Implementation: `2aafb202c5d1aba9619af005c453dab11b88603b`.

Schedule wall time, including preparation: 466.94 seconds.

| Task | Call status | Interpretation | Objects | Annotated | Interfaces | Annotated interfaces | Total seconds |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 051 | completed | enriched | 913 | 26 | 123 | 5 | 204.06 |
| 025 | completed | enriched | 1353 | 12 | 51 | 7 | 185.94 |
| 016 | completed | enriched | 425 | 14 | 73 | 5 | 173.67 |


## Token accounting

| Task | Input | Cached input (subset) | Output | Reasoning (output subset) | Total |
| --- | --- | --- | --- | --- | --- |
| 051 | 337216 | 257024 | 4915 | 60 | 342131 |
| 025 | 526076 | 463616 | 4191 | 97 | 530267 |
| 016 | 433592 | 375808 | 3965 | 52 | 437557 |
| All tasks | 1296884 | 1096448 | 13071 | 209 | 1309955 |


Total is input plus output. Cached input and reasoning are already included. Missing or incomplete call costs remain unknown; no subscription-to-dollar estimate is made.

## Task 051

Interpreted source paths: `fixtures/mars_field_study.f95`, `reproduce.py`, `source/include/shtools.h`.

| Phase | Status | Allowance seconds | Elapsed seconds |
| --- | --- | --- | --- |
| prepare | ready | 30.00 | 1.56 |
| extract_draft | completed | 463.44 | 185.73 |
| assemble_initial | scientific_objects | 352.71 | 0.82 |

| Call | Status | Model cap seconds | Call elapsed seconds |
| --- | --- | --- | --- |
| extract_draft | completed | 360.00 | 185.73 |

Raw trial: `jobs/task-051-science/task_051__h2ztc76`.

## Task 025

Interpreted source paths: `reproduce.py`.

| Phase | Status | Allowance seconds | Elapsed seconds |
| --- | --- | --- | --- |
| prepare | ready | 30.00 | 2.00 |
| extract_draft | completed | 463.00 | 167.64 |
| assemble_initial | scientific_objects | 370.35 | 0.88 |

| Call | Status | Model cap seconds | Call elapsed seconds |
| --- | --- | --- | --- |
| extract_draft | completed | 360.00 | 167.64 |

Raw trial: `jobs/task-025-science/task_025__J7fW9jb`.

## Task 016

Interpreted source paths: `reproduce.py`, `source/MACS3/IO/PeakIO.py`.

| Phase | Status | Allowance seconds | Elapsed seconds |
| --- | --- | --- | --- |
| prepare | ready | 30.00 | 3.03 |
| extract_draft | completed | 461.97 | 154.73 |
| assemble_initial | scientific_objects | 382.23 | 0.79 |

| Call | Status | Model cap seconds | Call elapsed seconds |
| --- | --- | --- | --- |
| extract_draft | completed | 360.00 | 154.73 |

Raw trial: `jobs/task-016-science/task_016__Wr2FozG`.
