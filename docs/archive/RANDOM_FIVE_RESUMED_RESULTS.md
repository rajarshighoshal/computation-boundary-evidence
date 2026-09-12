# Paired comparison: results

Planned tasks (configuration order): 114, 001. Recorded attempts: 4/4; planned attempts without a run receipt: 0. Schedule status: `completed`.

This is an exploratory comparison, not evidence of a general improvement. Unknown outcomes are not failures or successes; missing cost measurements are not zero. No significance or causal-attribution claim is made.

## Outcomes for the full planned selection

| Task | Arm | Schedule status | Run status | Hidden-test success | Hidden tests passed/collected | Official reward | Agent seconds |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 114 | baseline | completed | completed | fail | 5/15 | 0 | 630.09 |
| 114 | science | completed | completed | fail | 5/15 | 0 | 520.08 |
| 001 | science | completed | completed | fail | 1/3 | 0 | 950.91 |
| 001 | baseline | completed | completed | fail | 1/3 | 0 | 1471.71 |

| Arm | Planned | Recorded | Exact pass | Exact fail | Unknown recorded | No receipt |
| --- | --- | --- | --- | --- | --- | --- |
| baseline | 2 | 2 | 0 | 2 | 0 | 0 |
| science | 2 | 2 | 0 | 2 | 0 | 0 |

| Paired outcome | Tasks |
| --- | --- |
| both_success | 0 |
| baseline_only | 0 |
| science_only | 0 |
| both_failure | 2 |
| unknown | 0 |
| missing_baseline | 0 |
| missing_science | 0 |
| neither_arm_recorded | 0 |

Exact hidden-test success and official reward are reported separately. Per-test Fail2Pass/Pass2Pass require matching original-baseline test identities; availability and diagnostics remain in the audited summary.

## Time and token accounting

Agent time includes extraction and handoff where applicable, but excludes image pulls, environment preparation and official verification. Token totals require usage from every recorded agent stage; repair-only usage is not reported as a full science-arm total. Observed totals below cover only the stated measured trials, not unrecorded attempts.

| Arm | Quantity | Observed total | Measured trials | Missing recorded trials |
| --- | --- | --- | --- | --- |
| baseline | duration_seconds | 2101.80 | 2 | 0 |
| baseline | input_tokens | 6323736 | 2 | 0 |
| baseline | cached_input_tokens | 6118784 | 2 | 0 |
| baseline | output_tokens | 43819 | 2 | 0 |
| baseline | over_budget_seconds | 0.00 | 2 | 0 |
| science | duration_seconds | 1470.99 | 2 | 0 |
| science | input_tokens | 3068636 | 2 | 0 |
| science | cached_input_tokens | 2859264 | 2 | 0 |
| science | output_tokens | 34368 | 2 | 0 |
| science | over_budget_seconds | 0.00 | 2 | 0 |

### Raw-event token breakdown by task and stage

Input includes cached input; output includes reasoning. Total = input + output, with neither subset added again. Nonreasoning output = output − reasoning; this is not necessarily visible text. These counts are tokens, not monetary cost. Raw `agent/{extract,repair}.jsonl` completed-turn events are cross-checked against stage receipts. Missing reasoning stays unknown. Incomplete stages have unknown full costs; the earlier receipt totals can contain completed turns from an interrupted stage. Trial totals require every expected stage to be present and measured. CLI diagnostic lines are skipped, as in receipt collection.

| Task | Arm | Stage | Status | Input | Cached input | Uncached input | Output | Reasoning output | Nonreasoning output | Total |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 114 | baseline | repair | completed | 2061246 | 1967744 | 93502 | 14672 | 5766 | 8906 | 2075918 |
| 114 | baseline | trial total | completed | 2061246 | 1967744 | 93502 | 14672 | 5766 | 8906 | 2075918 |
| 114 | science | extract | completed | 130887 | 106496 | 24391 | 2293 | 132 | 2161 | 133180 |
| 114 | science | repair | completed | 933760 | 866176 | 67584 | 10000 | 2908 | 7092 | 943760 |
| 114 | science | trial total | completed | 1064647 | 972672 | 91975 | 12293 | 3040 | 9253 | 1076940 |
| 001 | science | extract | completed | 171515 | 138752 | 32763 | 1780 | 17 | 1763 | 173295 |
| 001 | science | repair | completed | 1832474 | 1747840 | 84634 | 20295 | 9967 | 10328 | 1852769 |
| 001 | science | trial total | completed | 2003989 | 1886592 | 117397 | 22075 | 9984 | 12091 | 2026064 |
| 001 | baseline | repair | completed | 4262490 | 4151040 | 111450 | 29147 | 16231 | 12916 | 4291637 |
| 001 | baseline | trial total | completed | 4262490 | 4151040 | 111450 | 29147 | 16231 | 12916 | 4291637 |

Schedule elapsed seconds (including setup and verification): 3880.89.

## Extraction and graph coverage

### Task 114

Handoff status: `usable_graph`; graph artifact: available.

| Stage/phase | Status | Seconds |
| --- | --- | --- |
| extract | completed | 101.84 |
| interpret | completed | 99.44 |
| prepare | ready | 1.18 |
| assemble_initial | usable_graph | 2.40 |

Graph nodes: claims=3, quantities=5, evidence=18, observations=0.
Recorded mechanical coverage: claims=3, conflicts=0, dimension_resolved=0, expressions=1, lift_supported=0, lift_unknown=3, scale_resolved=0, shape_resolved=0.

code_grounding: unresolved=3.
alignments: unknown=3.

### Task 001

Handoff status: `usable_graph`; graph artifact: available.

| Stage/phase | Status | Seconds |
| --- | --- | --- |
| extract | completed | 83.82 |
| interpret | completed | 82.87 |
| prepare | ready | 0.97 |
| assemble_initial | usable_graph | 0.95 |

Graph nodes: claims=3, quantities=2, evidence=14, observations=0.
Recorded mechanical coverage: claims=3, conflicts=0, dimension_resolved=0, expressions=0, lift_supported=0, lift_unknown=3, scale_resolved=0, shape_resolved=0.

code_grounding: unresolved=3.
alignments: unknown=3.

Coverage counters measure recoverable representations and supported rules, not scientific correctness. Neither successful extraction nor a passed probe establishes that the supplied guidance caused a repair outcome.

## Measured Docker resources

| Task | Arm | Setup receipt | Docker GiB | Task requested GiB | Docker CPUs | Below requested memory |
| --- | --- | --- | --- | --- | --- | --- |
| 114 | baseline | available | 3.83 | 8.00 | 4 | True |
| 114 | science | available | 3.83 | 8.00 | 4 | True |
| 001 | science | available | 3.83 | 8.00 | 4 | True |
| 001 | baseline | available | 3.83 | 8.00 | 4 | True |

Docker totals are measured daemon allocation, not proof of per-container effective limits or parity with published benchmark resources. Missing setup receipts leave actual allocation unknown; requested resources alone do not establish feasibility.

## Protocol and provenance

Model: gpt-6-astra/medium; Codex 0.153.4; Pier 0.3.0. Total allowance: 1800 seconds; extraction cap: 360 seconds. Attempts per task/arm: 1; concurrency: 1.

Planned order: 114/baseline → 114/science → 001/science → 001/baseline.

| Record | Value |
| --- | --- |
| implementation_revision | bb00ca56bb7aae4ca67a3af6d526e5109d3f07ab |
| implementation_dirty | False |
| config_sha256 | f7e55f2c27025ce480d06537e5bdbdba862c9685b7dc97bfc76126effb7ef9dd |
| selection_sha256 | 409c853fcf71217e5a229024c02c1075f01c7a329361eb2b7e42b5e80578e620 |
| uv_lock_sha256 | c61a78a1c9ba91fe4ebf14ec3f35fd65e9d4e99a567afe06fed77cdac3bc38f4 |
| prompt_sha256 | {'prompts/extract.md': '42eb03717c9ea53146ae133bfb9fa6c7d131ce0c9d7a5c8f027ea8a61b6976f5', 'prompts/repair.md': '9b9bd47560b889414d5b5b4fcb05c0dd6ba406856a6ce7fdee9c59102115066b'} |
| dataset_revision | d8bdbcb4ecb2b565686382459c815d2b6291fd31 |
| release_commit | 42e7e97915ff7d73436a5d37b5cbe6b77e9c2a00 |
| release_receipt | data/random-five-v1-release.json |
| sampling_manifest | unknown |
| sampling_manifest_sha256 | unknown |
| allow_restricted_licenses | False |

| Task | Arm | Trial path | Environment image | Verifier image |
| --- | --- | --- | --- | --- |
| 001 | baseline | task-001-baseline/task_001__z479mQA | docker.io/kevinxulearning/swe-bench-science-environment-python-task-001:v0.1.0@sha256:0b6b41e556cd862f10e9e8c489e9b539eda27d277718e0504de440048c62d3c7 | docker.io/kevinxulearning/swe-bench-science-verifier-python-task-001:v0.1.0@sha256:7af68a1c44876615b0f961abd18e7fb656dae5f117820a35ff8e1d10faa430b0 |
| 001 | science | task-001-science/task_001__FkFvEPb | docker.io/kevinxulearning/swe-bench-science-environment-python-task-001:v0.1.0@sha256:0b6b41e556cd862f10e9e8c489e9b539eda27d277718e0504de440048c62d3c7 | docker.io/kevinxulearning/swe-bench-science-verifier-python-task-001:v0.1.0@sha256:7af68a1c44876615b0f961abd18e7fb656dae5f117820a35ff8e1d10faa430b0 |
| 114 | baseline | task-114-baseline/task_114__dyyMFxV | docker.io/kevinxulearning/swe-bench-science-environment-python-task-114:v0.1.2@sha256:68c032f628b1aad6432f5bc030537d016dc697778ac57ebfd54595df6b23ab3c | docker.io/kevinxulearning/swe-bench-science-verifier-python-task-114:v0.1.2@sha256:0cfbc99c9056587cebcd3647a2edbfe8550c65d58ba2fbabc8b4e0a242bd24c7 |
| 114 | science | task-114-science/task_114__oUT5HVU | docker.io/kevinxulearning/swe-bench-science-environment-python-task-114:v0.1.2@sha256:68c032f628b1aad6432f5bc030537d016dc697778ac57ebfd54595df6b23ab3c | docker.io/kevinxulearning/swe-bench-science-verifier-python-task-114:v0.1.2@sha256:0cfbc99c9056587cebcd3647a2edbfe8550c65d58ba2fbabc8b4e0a242bd24c7 |

Recorded development-task overlap: none; recorded prior hidden-test exposure: none. These markers are not a claim about other possible exposure.

Independent reconstruction verified 4 recorded trials and 2 recorded task/run pairs. Patch hashes checked: 4; patches missing: 0; patches present without a recorded hash: 0.

This document's quantitative text and tables are generated from durable records. Raw trajectories, patches, verifier receipts and failure diagnostics remain under `runs/random-five-medium-resume-v1`. Only receipts beneath this run root are included; earlier development runs are not pooled. Unknowns and incomplete schedules must remain explicit in any downstream claims.
