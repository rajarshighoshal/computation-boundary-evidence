# Evidence packet — CBE vs baseline on SWE-bench Science

Everything a plot needs for the reported experiment. Two arms: 'baseline' uses only shell tools; 'cbe' adds science_find / science_inspect / science_note over a prepared evidence store. A solve is the official verifier reward for one attempt. 'verified' counts attempts that produced a verifier verdict; a few attempts were lost to provider or container failures and are excluded rather than counted as failures.

Model DeepSeek V4.1 Flash; budget 1800s per attempt; 89 held-out tasks x 2 arms x 3 runs and 30 development tasks x 2 arms x 4 runs.

## Headline (held out)

| arm | solved | verified | solve rate | output tokens | mean output/attempt | private tests |
|---|---|---|---|---|---|---|
| baseline | 60 | 262 | 22.9% | 12.01M | 45.8k | 2315/3167 (73.1%) |
| cbe | 60 | 260 | 23.1% | 10.36M | 39.8k | 2226/3148 (70.7%) |

## By scientific domain (held out, k=3)

| domain | tasks | baseline | CBE | delta pp |
|---|---|---|---|---|
| Mechanics | 3 | 0/9 | 2/9 | +22.2 |
| Astronomy | 5 | 2/14 | 4/15 | +12.4 |
| Materials Science and Engineering | 15 | 8/44 | 12/43 | +9.7 |
| Civil Engineering | 5 | 6/15 | 7/15 | +6.7 |
| Atmospheric Science | 5 | 3/15 | 3/14 | +1.4 |
| Chemistry | 19 | 12/56 | 12/56 | +0.0 |
| Computer Science and Technology | 1 | 0/3 | 0/3 | +0.0 |
| Electrical Engineering | 1 | 0/3 | 0/3 | +0.0 |
| Geography | 1 | 0/3 | 0/3 | +0.0 |
| Geophysics | 2 | 0/5 | 0/5 | +0.0 |
| Information and Communication Engineering | 1 | 0/3 | 0/3 | +0.0 |
| Marine Science | 1 | 0/3 | 0/3 | +0.0 |
| Mathematics | 5 | 1/14 | 1/14 | +0.0 |
| Physics | 7 | 3/21 | 3/21 | +0.0 |
| Biology | 6 | 7/18 | 5/17 | -9.5 |
| Biomedical Engineering | 10 | 13/30 | 8/30 | -16.7 |
| Aeronautical and Astronautical Science and Technology | 1 | 3/3 | 2/3 | -33.3 |
| Surveying and Mapping Science and Technology | 1 | 2/3 | 1/3 | -33.3 |

## By scientific domain (development, k=4)

| domain | tasks | baseline | CBE | delta pp |
|---|---|---|---|---|
| Mathematics | 2 | 0/8 | 3/8 | +37.5 |
| Statistics | 1 | 2/4 | 3/4 | +25.0 |
| Astronomy | 2 | 4/8 | 4/8 | +0.0 |
| Biomedical Engineering | 2 | 4/8 | 4/8 | +0.0 |
| Electrical Engineering | 1 | 0/3 | 0/3 | +0.0 |
| Geophysics | 1 | 0/4 | 0/4 | +0.0 |
| Marine Science | 1 | 4/4 | 4/4 | +0.0 |
| Materials Science and Engineering | 1 | 3/4 | 3/4 | +0.0 |
| Nuclear Science and Technology | 1 | 0/4 | 0/4 | +0.0 |
| Physics | 4 | 7/16 | 7/16 | +0.0 |
| Surveying and Mapping Science and Technology | 2 | 0/6 | 0/7 | +0.0 |
| Biology | 7 | 12/28 | 11/28 | -3.6 |
| Chemistry | 5 | 7/20 | 5/20 | -10.0 |

## Replicate structure (held out)

| solves out of 3 | baseline tasks | CBE tasks |
|---|---|---|
| 0 | 60 | 61 |
| 1 | 9 | 6 |
| 2 | 9 | 12 |
| 3 | 11 | 10 |

## Reasoning effort

| cell | baseline | CBE |
|---|---|---|
| high_effort | 12/30 (40.0%) | 11/30 (36.7%) |
| low_effort | 12/30 (40.0%) | 13/30 (43.3%) |

Per-task rows for both partitions are in `evidence-packet.json` under `by_task` (solved and verified attempts for every task and arm), together with the domain of each task.
