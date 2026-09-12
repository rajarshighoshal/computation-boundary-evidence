# Initial five-task checks

Baseline solved 3/5; context-assisted repair solved 3/5. Baseline-only successes: 0; context-only successes: 0.

These exploratory checks used different effort/method revisions and predate the task-local redesign. They are not a uniform locked experiment or evidence of a general effect. The original draw was retained.

| Task | Effort | Baseline hidden tests | Context hidden tests | Baseline seconds | Context seconds | Context handoff |
| --- | --- | --- | --- | --- | --- | --- |
| 091 | high | 3/3 | 3/3 | 143.08 | 315.15 | usable_graph |
| 058 | high | 9/9 | 9/9 | 518.65 | 843.82 | no_valid_graph |
| 009 | medium | 9/9 | 9/9 | 534.28 | 550.57 | usable_graph |
| 114 | medium | 5/15 | 5/15 | 630.09 | 520.08 | usable_graph |
| 001 | medium | 1/3 | 1/3 | 1471.71 | 950.91 | usable_graph |

| Task | Arm | Input | Cached input | Output | Reasoning (subset) | Total |
| --- | --- | --- | --- | --- | --- | --- |
| 091 | baseline | 296679 | 252416 | 3360 | 505 | 300039 |
| 091 | science | 553628 | 470016 | 6833 | 655 | 560461 |
| 058 | baseline | 1829450 | 1732480 | 13029 | 3263 | 1842479 |
| 058 | science | 1799753 | 1687296 | 21420 | 6005 | 1821173 |
| 009 | baseline | 527301 | 474112 | 15049 | 5956 | 542350 |
| 009 | science | 628986 | 556160 | 15059 | 4572 | 644045 |
| 114 | baseline | 2061246 | 1967744 | 14672 | 5766 | 2075918 |
| 114 | science | 1064647 | 972672 | 12293 | 3040 | 1076940 |
| 001 | baseline | 4262490 | 4151040 | 29147 | 16231 | 4291637 |
| 001 | science | 2003989 | 1886592 | 22075 | 9984 | 2026064 |

Input includes cached input; output includes reasoning. Total = input + output. Times include extraction/handoff but exclude setup and hidden tests. These cost rows cover completed attempts only.

Preserved non-completed receipts: 2. The operator stop occurred during an image pull; the subscription-quota failure preceded repair. They remain in the JSON and original reports, with missing usage unknown rather than zero.

Task 058's earlier Git-warning rejection led to repair without its graph. Later checks used native read-only extraction. The task-local redesign has separate extraction-only tests, not repair results in this table.

Reproduce: `python scripts/report_initial_five.py`. Source runs: `runs/random-five-v1`, `runs/random-five-medium-v1`, `runs/random-five-medium-resume-v1`.
