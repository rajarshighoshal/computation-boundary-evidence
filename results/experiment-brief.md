# Experiment brief: computation-and-boundary evidence (CBE) for scientific repair

This file is the complete record behind the accompanying report. It states what was done and
gives every number used, so no other data is required to check or plot it.

## 1. Question

Does giving a repository-level repair agent a prepared, queryable account of a task's
scientific structure change repair, at the same model, tools and time budget?

## 2. What CBE is

Preparation runs once per task, with no model call and no code execution. Files are ranked so
that execution evidence and boundary callers precede shallow entry points; Python is parsed
with Tree-sitter and C, C++, Fortran and Cython with Joern code property graphs, with explicit
fallback when a frontend is unavailable. The store holds four things:

1. computations: name, path, the source span that anchors the result, expressions;
2. conditions and findings that guard those computations;
3. documented public definitions;
4. call boundaries, each labelled internal, external with a named provider, or unknown.

The agent queries the store through `science_find` (targets and excerpts), `science_inspect`
(relationships, definitions, source, contracts) and an optional `science_note`. External
providers are treated as assumed-correct interfaces; unresolved callees are labelled rather
than guessed. Both arms get identical shell tools; the endpoints add no budget.

## 3. Protocol

- Benchmark: SWE-bench Science, all 119 tasks; 89 held-out tasks and 30 development tasks.
- Model: DeepSeek V4.1 Flash; temperature 0.0, PYTHONHASHSEED=0, provider seed ignored per provider check.
- Budget: 1800 s per attempt for the agent, 1800 s for the verifier; none in agent or verifier container.
- Verifier: runs only after the repair stops; private tests never visible to the agent.
- Replicates: 3 runs on the held-out partition, 4 on development; both arms in every run.
- A solve is the official verifier reward of one attempt. `verified` counts attempts that
  produced a verdict; the few attempts lost to provider or container failures are excluded,
  not counted as failures. Rates always carry their denominator.
- Development tasks were used for iteration; the held-out partition is the only basis for
  the headline claim.

## 4. Headline result

| partition | baseline | CBE | contrast |
|---|---|---|---|
| held-out 89, k=3 | 60/262 (22.9%) | 60/260 (23.1%) | 7 tasks better, 8 worse, 74 tied |
| development 30, k=4 | 43/117 (36.8%) | 44/118 (37.3%) | --- |

Paired test over the 89 held-out tasks: sign test p = 1.00, bootstrap 95% interval for the mean per-task difference -3.4 to +4.9 percentage points. Parity is the finding, not a null we hid.

## 5. Cost and partial credit (held-out, 522 verified attempts)

| measure | baseline | CBE | change |
|---|---|---|---|
| output tokens | 12.01M | 10.36M | -13.7% |
| input tokens | 837.95M | 878.31M | +4.8% |
| mean output per attempt | 45.8k | 39.8k | -13.0% |
| agent work per attempt | 1237 s | 1307 s | +70 s |
| private tests passed | 2315/3167 (73.1%) | 2226/3148 (70.7%) | -2.4 pp |

## 6. By scientific discipline (held-out)

| discipline | tasks | baseline | CBE | delta pp |
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

Development partition, same columns:

| discipline | tasks | baseline | CBE | delta pp |
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

## 7. Replicate structure (held-out)

| solves out of 3 runs | baseline tasks | CBE tasks |
|---|---|---|
| 0 | 60 | 61 |
| 1 | 9 | 6 |
| 2 | 9 | 12 |
| 3 | 11 | 10 |

Across arms: 15 tasks differ, 18 flip within an arm. A single run cannot resolve a
difference of a few points on this benchmark.

## 8. Reasoning effort (development tasks)

| cells | baseline | CBE |
|---|---|---|
| high effort (30 tasks) | 12/30 (40.0%) | 11/30 (36.7%) |
| low effort (30 tasks) | 12/30 (40.0%) | 13/30 (43.3%) |
| high effort (matched 20) | 10/20 (50.0%) | 8/20 (40.0%) |
| low effort (matched 20) | 10/20 (50.0%) | 10/20 (50.0%) |

The two tasks the CBE arm gains under low effort (002, 009) are the two it lost at high
effort, which is what external evidence substituting for deliberation looks like.

## 9. Which tasks move, and the per-task data

CBE gains on: 020, 042, 067, 074, 084, 103, 116. It loses on: 022, 029, 053, 056, 063, 087, 093, 098.

Task 103 (pyNastran, stiffness matrices of a symmetric composite laminate) is solved 2 of 3
times with CBE and 0 of 3 without; the recorded trajectory inspects the ply-angle computation
and its library boundaries before editing. Task 022 (nilearn, volume-to-surface projection) is
the mirror image: 2 of 3 with the baseline, 0 of 3 with CBE, where the trajectory reasoned
about projection mathematics before touching the atlas label mapping the instruction describes.

Complete per-task outcomes, held out (task, discipline, baseline solved/verified, CBE
solved/verified). Every held-out task appears; runs = 3 per arm.

| task | discipline | baseline | CBE |
|---|---|---|---|
| 003 | Materials Science and Engineering | 0/3 | 0/3 |
| 007 | Biomedical Engineering | 2/3 | 2/3 |
| 011 | Physics | 0/3 | 0/3 |
| 012 | Physics | 0/3 | 0/3 |
| 013 | Physics | 3/3 | 3/3 |
| 015 | Biomedical Engineering | 3/3 | 3/3 |
| 017 | Astronomy | 2/3 | 2/3 |
| 018 | Biology | 0/3 | 0/3 |
| 020 | Materials Science and Engineering | 0/3 | 1/3 |
| 021 | Chemistry | 0/3 | 0/3 |
| 022 | Biomedical Engineering | 2/3 | 0/3 |
| 023 | Chemistry | 3/3 | 3/3 |
| 026 | Atmospheric Science | 1/3 | 1/3 |
| 029 | Biology | 1/3 | 0/3 |
| 030 | Materials Science and Engineering | 3/3 | 3/3 |
| 031 | Biomedical Engineering | 3/3 | 3/3 |
| 032 | Chemistry | 3/3 | 3/3 |
| 033 | Materials Science and Engineering | 0/3 | 0/3 |
| 034 | Mathematics | 0/2 | 0/2 |
| 035 | Mathematics | 0/3 | 0/3 |
| 036 | Marine Science | 0/3 | 0/3 |
| 037 | Biomedical Engineering | 0/3 | 0/3 |
| 038 | Materials Science and Engineering | 2/3 | 2/3 |
| 039 | Geography | 0/3 | 0/3 |
| 040 | Geophysics | 0/2 | 0/2 |
| 041 | Geophysics | 0/3 | 0/3 |
| 042 | Astronomy | 0/3 | 2/3 |
| 043 | Materials Science and Engineering | 0/3 | 0/3 |
| 044 | Chemistry | 0/3 | 0/3 |
| 046 | Astronomy | 0/3 | 0/3 |
| 047 | Information and Communication Engineering | 0/3 | 0/3 |
| 048 | Chemistry | 0/3 | 0/3 |
| 049 | Mathematics | 0/3 | 0/3 |
| 050 | Physics | 0/3 | 0/3 |
| 052 | Materials Science and Engineering | 0/2 | 0/2 |
| 053 | Biomedical Engineering | 1/3 | 0/3 |
| 054 | Chemistry | 0/2 | 0/3 |
| 055 | Astronomy | 0/2 | 0/3 |
| 056 | Aeronautical and Astronautical Science and Technology | 3/3 | 2/3 |
| 057 | Chemistry | 2/3 | 2/3 |
| 059 | Computer Science and Technology | 0/3 | 0/3 |
| 060 | Biomedical Engineering | 0/3 | 0/3 |
| 062 | Materials Science and Engineering | 2/3 | 2/3 |
| 063 | Biology | 1/3 | 0/2 |
| 064 | Chemistry | 0/3 | 0/3 |
| 065 | Astronomy | 0/3 | 0/3 |
| 066 | Atmospheric Science | 0/3 | 0/3 |
| 067 | Atmospheric Science | 2/3 | 2/2 |
| 068 | Biology | 0/3 | 0/3 |
| 069 | Biology | 2/3 | 2/3 |
| 071 | Physics | 0/3 | 0/3 |
| 072 | Biomedical Engineering | 0/3 | 0/3 |
| 074 | Materials Science and Engineering | 0/3 | 2/2 |
| 075 | Materials Science and Engineering | 0/3 | 0/3 |
| 079 | Chemistry | 0/3 | 0/3 |
| 081 | Biology | 3/3 | 3/3 |
| 082 | Materials Science and Engineering | 0/3 | 0/3 |
| 083 | Chemistry | 0/3 | 0/3 |
| 084 | Materials Science and Engineering | 1/3 | 2/3 |
| 085 | Chemistry | 0/3 | 0/3 |
| 086 | Materials Science and Engineering | 0/3 | 0/3 |
| 087 | Biomedical Engineering | 1/3 | 0/3 |
| 088 | Atmospheric Science | 0/3 | 0/3 |
| 089 | Chemistry | 0/3 | 0/3 |
| 090 | Chemistry | 0/3 | 0/3 |
| 092 | Chemistry | 0/3 | 0/3 |
| 093 | Biomedical Engineering | 1/3 | 0/3 |
| 094 | Physics | 0/3 | 0/3 |
| 095 | Materials Science and Engineering | 0/3 | 0/3 |
| 096 | Atmospheric Science | 0/3 | 0/3 |
| 097 | Physics | 0/3 | 0/3 |
| 098 | Surveying and Mapping Science and Technology | 2/3 | 1/3 |
| 100 | Chemistry | 1/3 | 1/3 |
| 101 | Chemistry | 0/3 | 0/2 |
| 102 | Materials Science and Engineering | 0/3 | 0/3 |
| 103 | Mechanics | 0/3 | 2/3 |
| 105 | Chemistry | 0/3 | 0/3 |
| 106 | Chemistry | 3/3 | 3/3 |
| 107 | Mathematics | 0/3 | 0/3 |
| 108 | Mathematics | 1/3 | 1/3 |
| 109 | Mechanics | 0/3 | 0/3 |
| 110 | Civil Engineering | 0/3 | 0/3 |
| 111 | Mechanics | 0/3 | 0/3 |
| 112 | Civil Engineering | 3/3 | 3/3 |
| 113 | Electrical Engineering | 0/3 | 0/3 |
| 115 | Civil Engineering | 3/3 | 3/3 |
| 116 | Civil Engineering | 0/3 | 1/3 |
| 117 | Civil Engineering | 0/3 | 0/3 |
| 118 | Chemistry | 0/3 | 0/3 |

Development tasks (4 runs per arm):

| task | baseline | CBE |
|---|---|---|
| 001 | 0/4 | 0/4 |
| 002 | 3/4 | 1/4 |
| 004 | 0/4 | 0/4 |
| 005 | 0/4 | 0/4 |
| 006 | 0/4 | 0/4 |
| 008 | 0/4 | 0/4 |
| 009 | 3/4 | 3/4 |
| 010 | 4/4 | 4/4 |
| 014 | 0/4 | 0/4 |
| 016 | 4/4 | 4/4 |
| 019 | 4/4 | 3/4 |
| 024 | 2/4 | 3/4 |
| 025 | 4/4 | 4/4 |
| 027 | 4/4 | 4/4 |
| 028 | 4/4 | 4/4 |
| 045 | 4/4 | 4/4 |
| 051 | 0/4 | 0/4 |
| 058 | 0/4 | 0/4 |
| 061 | 0/4 | 0/4 |
| 070 | 0/4 | 0/4 |
| 073 | 0/4 | 0/4 |
| 076 | 0/4 | 0/4 |
| 077 | 0/4 | 3/4 |
| 078 | 4/4 | 4/4 |
| 080 | 0/3 | 0/3 |
| 091 | 3/4 | 3/4 |
| 099 | 0/3 | 0/4 |
| 104 | 0/4 | 0/4 |
| 114 | 0/3 | 0/3 |
| 119 | 0/4 | 0/4 |

## 10. What the figures must and must not do

- Do **not** draw confidence intervals or error bars: with 2-3 attempts per task they are
  decoration. Annotate counts (`0/3 -> 2/3`) or percentage-point differences instead.
- Keep the encoding fixed paper-wide: baseline arm = circle; CBE arm = square; blue for the
  baseline, teal when CBE improves something, rust when it worsens something.
- One figure = one claim, stated in the caption's first sentence.
- Type: serif, nothing below 6 pt at design size; design at 5.5 in wide and let the report
  place it at 6.5 in, or design at 6.5 in and place at natural size. Never shrink a figure.
- No number may be typed into plot code: read it from this file or the receipts.

