# Luna pilot: compact results

Elapsed wall time including setup/verification: 85.40 minutes.
Source-version differences exist across task groups; see the full report. These are descriptive outcomes.

| Task | Arm | Result | Private passed | Private failed | Public passed/collected | Agent minutes |
| --- | --- | --- | --- | --- | --- | --- |
| 091 | baseline | pass | 3 | 0 | 1/1 | 7.88 |
| 091 | science | pass | 3 | 0 | 1/1 | 12.91 |
| 058 | baseline | pass | 9 | 0 | 1/1 | 11.82 |
| 058 | science | fail | 6 | 3 | 1/1 | 19.20 |
| 009 | baseline | pass | 9 | 0 | 1/1 | 8.55 |
| 009 | science | pass | 9 | 0 | 1/1 | 11.38 |
| 114 | baseline | fail | 10 | 5 | 0/1 | 9.80 |
| 114 | science | fail | 13 | 2 | 1/1 | 12.72 |
| 001 | baseline | fail | 1 | 2 | 1/1 | 9.95 |
| 001 | science | fail | 1 | 2 | 1/1 | 19.46 |

Agent time includes extraction/handoff for science, but excludes setup and official verification.

## Stage time and token usage

Input includes cached input; output includes reasoning. Do not add subsets twice. Counts include repeated input across model calls, not unique prompt size. No per-run dollar or credit bill was recorded.

| Task | Stage | Seconds | Input | Cached input | Output | Reasoning output |
| --- | --- | --- | --- | --- | --- | --- |
| 091 | baseline/repair | 473.01 | 2,483,400 | 2,344,448 | 20,896 | 11,415 |
| 091 | science/extract | 294.18 | 1,238,254 | 1,138,176 | 13,224 | 7,886 |
| 091 | science/repair | 463.35 | 2,105,388 | 1,934,848 | 22,269 | 12,187 |
| 058 | baseline/repair | 709.13 | 5,225,950 | 5,056,000 | 17,563 | 10,680 |
| 058 | science/extract | 373.17 | unknown | unknown | unknown | unknown |
| 058 | science/repair | 761.78 | 4,720,323 | 4,541,952 | 17,215 | 8,361 |
| 009 | baseline/repair | 512.73 | 1,158,536 | 1,035,264 | 25,234 | 15,870 |
| 009 | science/extract | 251.42 | 686,867 | 563,200 | 12,022 | 2,452 |
| 009 | science/repair | 415.13 | 1,708,305 | 1,579,776 | 19,999 | 14,270 |
| 114 | baseline/repair | 587.91 | 3,124,910 | 2,972,160 | 23,892 | 15,427 |
| 114 | science/extract | 362.20 | 733,230 | 654,848 | 17,326 | 7,594 |
| 114 | science/repair | 385.23 | 2,141,489 | 2,014,976 | 15,377 | 7,194 |
| 001 | baseline/repair | 597.25 | 2,575,756 | 2,444,800 | 23,965 | 16,144 |
| 001 | science/extract | 296.73 | 951,350 | 864,512 | 12,936 | 6,416 |
| 001 | science/repair | 854.70 | 3,431,829 | 3,224,064 | 31,972 | 15,923 |

OpenMC extraction timed out without completed-turn usage: its full extraction/treatment cost remains unknown, not zero. Its repair cost is separately measured. Extraction seconds include static preparation and assembly.
