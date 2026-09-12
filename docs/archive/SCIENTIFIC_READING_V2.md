# Scientific-reading development checks

Full public task workspaces; one scientific-reading call per task. No repair or verifier runs. Annotation counts measure delivery and anchoring, not scientific correctness or repair benefit.

Schedule: completed. Implementation: `084718bac5c430a20958ff171d1cf361da37eeab`.

Schedule wall time, including preparation: 469.91 seconds.

| Task | Call status | Interpretation | Objects | Annotated | Interfaces | Annotated interfaces | Total seconds |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 051 | completed | enriched | 552 | 27 | 34 | 4 | 200.68 |
| 025 | completed | enriched | 809 | 19 | 44 | 14 | 213.95 |
| 016 | completed | enriched | 490 | 16 | 70 | 7 | 166.34 |


## Token accounting

| Task | Input | Cached input (subset) | Output | Reasoning (output subset) | Total |
| --- | --- | --- | --- | --- | --- |
| 051 | 356525 | 295296 | 5032 | 135 | 361557 |
| 025 | 402671 | 329344 | 5058 | 158 | 407729 |
| 016 | 283117 | 228864 | 3876 | 67 | 286993 |
| All tasks | 1042313 | 853504 | 13966 | 360 | 1056279 |


Total is input plus output. Cached input and reasoning are already included. Missing or incomplete call costs remain unknown; no subscription-to-dollar estimate is made.

## Task 051

Interpreted source paths: `fixtures/mars_field_study.f95`, `reproduce.py`, `source/src/MakeMagGradGridDH.f95`, `source/src/MakeMagGridDH.f95`.

| Phase | Status | Allowance seconds | Elapsed seconds |
| --- | --- | --- | --- |
| prepare | ready | 30.00 | 1.69 |
| extract_draft | completed | 463.31 | 181.89 |
| assemble_initial | scientific_objects | 356.41 | 0.82 |

| Call | Status | Model cap seconds | Call elapsed seconds |
| --- | --- | --- | --- |
| extract_draft | completed | 360.00 | 181.89 |

Raw trial: `jobs/task-051-science/task_051__3hWAHCW`.

## Task 025

Interpreted source paths: `source/fit/OspreyFit.m`, `source/fit/osp_fitHERCULES.m`, `source/fit/osp_fitHERMES.m`, `source/fit/osp_fitMEGA.m`, `source/libraries/FID-A/fitTools/fitModels/Osprey/osp_addDiffMMPeaks.m`, `source/quantify/OspreyQuantify.m`, `source/utilities/RunOspreyJob.m`.

| Phase | Status | Allowance seconds | Elapsed seconds |
| --- | --- | --- | --- |
| prepare | ready | 30.00 | 8.17 |
| extract_draft | completed | 456.83 | 188.51 |
| assemble_initial | scientific_objects | 343.32 | 0.92 |

| Call | Status | Model cap seconds | Call elapsed seconds |
| --- | --- | --- | --- |
| extract_draft | completed | 360.00 | 188.51 |

Raw trial: `jobs/task-025-science/task_025__dEaRLiP`.

## Task 016

Interpreted source paths: `reproduce.py`, `source/MACS3/IO/PeakIO.py`, `source/MACS3/Signal/BedGraph.py`.

| Phase | Status | Allowance seconds | Elapsed seconds |
| --- | --- | --- | --- |
| prepare | ready | 30.00 | 3.78 |
| extract_draft | completed | 461.22 | 146.02 |
| assemble_initial | scientific_objects | 390.20 | 0.87 |

| Call | Status | Model cap seconds | Call elapsed seconds |
| --- | --- | --- | --- |
| extract_draft | completed | 360.00 | 146.02 |

Raw trial: `jobs/task-016-science/task_016__94f98Yj`.
