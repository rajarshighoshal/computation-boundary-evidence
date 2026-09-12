# Paired comparison: results

Planned tasks (configuration order): 091, 058, 009, 114, 001. Recorded attempts: 10/10; planned attempts without a run receipt: 0. Schedule status: `completed`.

This is an exploratory comparison, not evidence of a general improvement. Unknown outcomes are not failures or successes; missing cost measurements are not zero. No significance or causal-attribution claim is made.

## Outcomes for the full planned selection

| Task | Arm | Schedule status | Run status | Hidden-test success | Hidden tests passed/collected | Official reward | Agent seconds |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 091 | science | completed | completed | pass | 3/3 | 1 | 254.36 |
| 091 | baseline | completed | completed | pass | 3/3 | 1 | 127.81 |
| 058 | baseline | completed | completed | pass | 9/9 | 1 | 672.61 |
| 058 | science | completed | completed | pass | 9/9 | 1 | 895.70 |
| 009 | science | completed | completed | pass | 9/9 | 1 | 437.15 |
| 009 | baseline | completed | completed | pass | 9/9 | 1 | 393.42 |
| 114 | baseline | completed | completed | fail | 5/15 | 0 | 371.35 |
| 114 | science | completed | completed | fail | 13/15 | 0 | 573.59 |
| 001 | science | completed | completed | fail | 2/3 | 0 | 1170.44 |
| 001 | baseline | completed | completed | pass | 3/3 | 1 | 1369.19 |

| Arm | Planned | Recorded | Exact pass | Exact fail | Unknown recorded | No receipt |
| --- | --- | --- | --- | --- | --- | --- |
| baseline | 5 | 5 | 4 | 1 | 0 | 0 |
| science | 5 | 5 | 3 | 2 | 0 | 0 |

| Paired outcome | Tasks |
| --- | --- |
| both_success | 3 |
| baseline_only | 1 |
| science_only | 0 |
| both_failure | 1 |
| unknown | 0 |
| missing_baseline | 0 |
| missing_science | 0 |
| neither_arm_recorded | 0 |

Exact hidden-test success and official reward are reported separately. Per-test Fail2Pass/Pass2Pass require matching original-baseline test identities; availability and diagnostics remain in the audited summary.

## Time and token accounting

Agent time includes extraction and handoff where applicable, but excludes image pulls, environment preparation and official verification. Token totals require usage from every recorded agent stage; repair-only usage is not reported as a full science-arm total. Observed totals below cover only the stated measured trials, not unrecorded attempts.

| Arm | Quantity | Observed total | Measured trials | Missing recorded trials |
| --- | --- | --- | --- | --- |
| baseline | duration_seconds | 2934.37 | 5 | 0 |
| baseline | input_tokens | 6091794 | 5 | 0 |
| baseline | cached_input_tokens | 5766656 | 5 | 0 |
| baseline | output_tokens | 74964 | 5 | 0 |
| baseline | over_budget_seconds | 0.00 | 5 | 0 |
| science | duration_seconds | 3331.25 | 5 | 0 |
| science | input_tokens | 6812452 | 5 | 0 |
| science | cached_input_tokens | 6321664 | 5 | 0 |
| science | output_tokens | 83139 | 5 | 0 |
| science | over_budget_seconds | 0.00 | 5 | 0 |

### Raw-event token breakdown by task and stage

Input includes cached input; output includes reasoning. Total = input + output, with neither subset added again. Nonreasoning output = output − reasoning; this is not necessarily visible text. These counts are tokens, not monetary cost. Raw `agent/{extract,repair}.jsonl` completed-turn events are cross-checked against stage receipts. Missing reasoning stays unknown. Incomplete stages have unknown full costs; the earlier receipt totals can contain completed turns from an interrupted stage. Trial totals require every expected stage to be present and measured. CLI diagnostic lines are skipped, as in receipt collection.

| Task | Arm | Stage | Status | Input | Cached input | Uncached input | Output | Reasoning output | Nonreasoning output | Total |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 091 | science | extract | completed | 122545 | 91776 | 30769 | 2839 | 235 | 2604 | 125384 |
| 091 | science | repair | completed | 269451 | 235904 | 33547 | 2570 | 171 | 2399 | 272021 |
| 091 | science | trial total | completed | 391996 | 327680 | 64316 | 5409 | 406 | 5003 | 397405 |
| 091 | baseline | repair | completed | 302263 | 273024 | 29239 | 2707 | 332 | 2375 | 304970 |
| 091 | baseline | trial total | completed | 302263 | 273024 | 29239 | 2707 | 332 | 2375 | 304970 |
| 058 | baseline | repair | completed | 1639839 | 1566464 | 73375 | 17259 | 6352 | 10907 | 1657098 |
| 058 | baseline | trial total | completed | 1639839 | 1566464 | 73375 | 17259 | 6352 | 10907 | 1657098 |
| 058 | science | extract | completed | 214707 | 184576 | 30131 | 2623 | 66 | 2557 | 217330 |
| 058 | science | repair | completed | 2035618 | 1956864 | 78754 | 19196 | 6879 | 12317 | 2054814 |
| 058 | science | trial total | completed | 2250325 | 2141440 | 108885 | 21819 | 6945 | 14874 | 2272144 |
| 009 | science | extract | completed | 149863 | 117888 | 31975 | 3190 | 33 | 3157 | 153053 |
| 009 | science | repair | completed | 315649 | 269568 | 46081 | 8289 | 1904 | 6385 | 323938 |
| 009 | science | trial total | completed | 465512 | 387456 | 78056 | 11479 | 1937 | 9542 | 476991 |
| 009 | baseline | repair | completed | 365490 | 316800 | 48690 | 10923 | 3650 | 7273 | 376413 |
| 009 | baseline | trial total | completed | 365490 | 316800 | 48690 | 10923 | 3650 | 7273 | 376413 |
| 114 | baseline | repair | completed | 778299 | 721280 | 57019 | 9480 | 3713 | 5767 | 787779 |
| 114 | baseline | trial total | completed | 778299 | 721280 | 57019 | 9480 | 3713 | 5767 | 787779 |
| 114 | science | extract | completed | 231653 | 201856 | 29797 | 3020 | 198 | 2822 | 234673 |
| 114 | science | repair | completed | 863011 | 791296 | 71715 | 10902 | 4567 | 6335 | 873913 |
| 114 | science | trial total | completed | 1094664 | 993152 | 101512 | 13922 | 4765 | 9157 | 1108586 |
| 001 | science | extract | completed | 185101 | 153728 | 31373 | 2516 | 70 | 2446 | 187617 |
| 001 | science | repair | completed | 2424854 | 2318208 | 106646 | 27994 | 13822 | 14172 | 2452848 |
| 001 | science | trial total | completed | 2609955 | 2471936 | 138019 | 30510 | 13892 | 16618 | 2640465 |
| 001 | baseline | repair | completed | 3005903 | 2889088 | 116815 | 34595 | 17957 | 16638 | 3040498 |
| 001 | baseline | trial total | completed | 3005903 | 2889088 | 116815 | 34595 | 17957 | 16638 | 3040498 |

### Treatment stages versus baseline total

These are raw input-plus-output token counts, not a monetary bill. The percentage compares the full treatment with the full baseline; unknown or incomplete costs remain unknown. Code-owned preparation, assembly and probe execution have no separate model calls; their time is included in extraction, and material read by the model contributes to that stage's input tokens. These tables exclude development-assistant and posthoc-review usage.

| Task | Baseline total | Extraction | Treatment repair | Treatment total | Change vs baseline |
| --- | --- | --- | --- | --- | --- |
| 091 | 304970 | 125384 | 272021 | 397405 | +30.3% |
| 058 | 1657098 | 217330 | 2054814 | 2272144 | +37.1% |
| 009 | 376413 | 153053 | 323938 | 476991 | +26.7% |
| 114 | 787779 | 234673 | 873913 | 1108586 | +40.7% |
| 001 | 3040498 | 187617 | 2452848 | 2640465 | -13.2% |
| All planned tasks | 6166758 | 918057 | 5977534 | 6895591 | +11.8% |

Schedule elapsed seconds (including setup and verification): 7307.87.

## Extraction and graph coverage

### Task 091

Handoff status: `usable_graph`; graph artifact: available.

| Stage/phase | Status | Seconds |
| --- | --- | --- |
| extract | completed | 118.91 |
| interpret | completed | 115.13 |
| prepare | ready | 1.19 |
| assemble_initial | usable_graph | 3.78 |

Graph nodes: claims=3, quantities=8, evidence=16, observations=0.
Recorded mechanical coverage: claims=3, conflicts=0, dimension_resolved=0, expressions=5, lift_supported=0, lift_unknown=3, scale_resolved=0, shape_resolved=0.

code_grounding: source_matched=3.
alignments: unknown=3.

### Task 058

Handoff status: `usable_graph`; graph artifact: available.

| Stage/phase | Status | Seconds |
| --- | --- | --- |
| extract | completed | 122.12 |
| interpret | completed | 121.30 |
| prepare | ready | 1.32 |
| assemble_initial | usable_graph | 0.82 |

Graph nodes: claims=2, quantities=6, evidence=12, observations=0.
Recorded mechanical coverage: claims=2, conflicts=0, dimension_resolved=0, expressions=0, lift_supported=0, lift_unknown=2, scale_resolved=0, shape_resolved=0.

code_grounding: unresolved=2.
alignments: unknown=2.

### Task 009

Handoff status: `usable_graph`; graph artifact: available.

| Stage/phase | Status | Seconds |
| --- | --- | --- |
| extract | completed | 128.43 |
| interpret | completed | 122.47 |
| prepare | ready | 1.70 |
| assemble_initial | usable_graph | 2.14 |
| probes | completed | 1.91 |
| assemble_final | usable_graph | 1.90 |

Graph nodes: claims=3, quantities=8, evidence=25, observations=2.
Recorded mechanical coverage: claims=3, conflicts=0, dimension_resolved=0, expressions=4, lift_supported=0, lift_unknown=3, scale_resolved=0, shape_resolved=0.

code_grounding: source_matched=3.
alignments: match=1, unknown=2.

### Task 114

Handoff status: `usable_graph`; graph artifact: available.

| Stage/phase | Status | Seconds |
| --- | --- | --- |
| extract | completed | 129.09 |
| interpret | completed | 125.46 |
| prepare | ready | 2.11 |
| assemble_initial | usable_graph | 3.63 |

Graph nodes: claims=3, quantities=6, evidence=26, observations=0.
Recorded mechanical coverage: claims=3, conflicts=0, dimension_resolved=0, expressions=3, lift_supported=0, lift_unknown=3, scale_resolved=0, shape_resolved=0.

code_grounding: source_matched=2, unresolved=1.
alignments: unknown=3.

### Task 001

Handoff status: `usable_graph`; graph artifact: available.

| Stage/phase | Status | Seconds |
| --- | --- | --- |
| extract | completed | 111.31 |
| interpret | completed | 109.18 |
| prepare | ready | 1.04 |
| assemble_initial | usable_graph | 2.13 |

Graph nodes: claims=3, quantities=6, evidence=19, observations=0.
Recorded mechanical coverage: claims=3, conflicts=0, dimension_resolved=0, expressions=1, lift_supported=0, lift_unknown=3, scale_resolved=0, shape_resolved=0.

code_grounding: source_matched=1, unresolved=2.
alignments: unknown=3.

Coverage counters measure recoverable representations and supported rules, not scientific correctness. Neither successful extraction nor a passed probe establishes that the supplied guidance caused a repair outcome.

## Measured Docker resources

| Task | Arm | Setup receipt | Docker GiB | Task requested GiB | Docker CPUs | Below requested memory |
| --- | --- | --- | --- | --- | --- | --- |
| 091 | science | available | 3.83 | 8.00 | 4 | True |
| 091 | baseline | available | 3.83 | 8.00 | 4 | True |
| 058 | baseline | available | 3.83 | 8.00 | 4 | True |
| 058 | science | available | 3.83 | 8.00 | 4 | True |
| 009 | science | available | 3.83 | 8.00 | 4 | True |
| 009 | baseline | available | 3.83 | 8.00 | 4 | True |
| 114 | baseline | available | 3.83 | 8.00 | 4 | True |
| 114 | science | available | 3.83 | 8.00 | 4 | True |
| 001 | science | available | 3.83 | 8.00 | 4 | True |
| 001 | baseline | available | 3.83 | 8.00 | 4 | True |

Docker totals are measured daemon allocation, not proof of per-container effective limits or parity with published benchmark resources. Missing setup receipts leave actual allocation unknown; requested resources alone do not establish feasibility.

## Protocol and provenance

Model: gpt-6-astra/medium; Codex 0.153.4; Pier 0.3.0. Total allowance: 1800 seconds; extraction cap: 360 seconds. Attempts per task/arm: 1; concurrency: 1.

Planned order: 091/science → 091/baseline → 058/baseline → 058/science → 009/science → 009/baseline → 114/baseline → 114/science → 001/science → 001/baseline.

| Record | Value |
| --- | --- |
| implementation_revision | bb5f52780e9b7d4203d8ffd7e30620dc58a1df37 |
| implementation_dirty | False |
| config_sha256 | 505bce078cbfe8bbfd7ec27300750d5948bbdc51e5cce551dd3e9e74b9c910c3 |
| selection_sha256 | 409c853fcf71217e5a229024c02c1075f01c7a329361eb2b7e42b5e80578e620 |
| uv_lock_sha256 | c61a78a1c9ba91fe4ebf14ec3f35fd65e9d4e99a567afe06fed77cdac3bc38f4 |
| prompt_sha256 | {'prompts/extract.md': '5050561d731c6ee1048fa3f32ba0a6bb3da0aef48515af48e3e37a28c2c3bc30', 'prompts/repair.md': '9b9bd47560b889414d5b5b4fcb05c0dd6ba406856a6ce7fdee9c59102115066b'} |
| dataset_revision | d8bdbcb4ecb2b565686382459c815d2b6291fd31 |
| release_commit | 42e7e97915ff7d73436a5d37b5cbe6b77e9c2a00 |
| release_receipt | data/random-five-v1-release.json |
| sampling_manifest | configs/random-five-v1.selection.json |
| sampling_manifest_sha256 | 8318fa6f565300af5673360b179706c00ce69d0291b8788d23aa4f2478a3080e |
| allow_restricted_licenses | False |

| Task | Arm | Trial path | Environment image | Verifier image |
| --- | --- | --- | --- | --- |
| 001 | baseline | task-001-baseline/task_001__GGfH99H | docker.io/kevinxulearning/swe-bench-science-environment-python-task-001:v0.1.0@sha256:0b6b41e556cd862f10e9e8c489e9b539eda27d277718e0504de440048c62d3c7 | docker.io/kevinxulearning/swe-bench-science-verifier-python-task-001:v0.1.0@sha256:7af68a1c44876615b0f961abd18e7fb656dae5f117820a35ff8e1d10faa430b0 |
| 001 | science | task-001-science/task_001__nJayhq5 | docker.io/kevinxulearning/swe-bench-science-environment-python-task-001:v0.1.0@sha256:0b6b41e556cd862f10e9e8c489e9b539eda27d277718e0504de440048c62d3c7 | docker.io/kevinxulearning/swe-bench-science-verifier-python-task-001:v0.1.0@sha256:7af68a1c44876615b0f961abd18e7fb656dae5f117820a35ff8e1d10faa430b0 |
| 009 | baseline | task-009-baseline/task_009__4LrQgge | docker.io/kevinxulearning/swe-bench-science-environment-python-task-009:v0.1.2@sha256:f4c314a57e656f4f4b480fa5d4967f476fb36c7aa5eb22e5f95398554d9ec79c | docker.io/kevinxulearning/swe-bench-science-verifier-python-task-009:v0.1.2@sha256:fe483ea0e64c344cc2cce2bd520aadc241558e7a7d2f6f397e18267d5bcbf7bb |
| 009 | science | task-009-science/task_009__FHfaZYz | docker.io/kevinxulearning/swe-bench-science-environment-python-task-009:v0.1.2@sha256:f4c314a57e656f4f4b480fa5d4967f476fb36c7aa5eb22e5f95398554d9ec79c | docker.io/kevinxulearning/swe-bench-science-verifier-python-task-009:v0.1.2@sha256:fe483ea0e64c344cc2cce2bd520aadc241558e7a7d2f6f397e18267d5bcbf7bb |
| 058 | baseline | task-058-baseline/task_058__W3CJj2K | docker.io/kevinxulearning/swe-bench-science-environment-python-cpp-task-058:v0.1.2@sha256:1b7822c1dbae675f2c32a19ec6cee830f93bd8248e459d3836d962805a3e680b | docker.io/kevinxulearning/swe-bench-science-verifier-python-cpp-task-058:v0.1.2@sha256:9be2d158eb93ffa431399c9240b6115f626f47476bc6327268bdc36c6f981744 |
| 058 | science | task-058-science/task_058__eGAKKPX | docker.io/kevinxulearning/swe-bench-science-environment-python-cpp-task-058:v0.1.2@sha256:1b7822c1dbae675f2c32a19ec6cee830f93bd8248e459d3836d962805a3e680b | docker.io/kevinxulearning/swe-bench-science-verifier-python-cpp-task-058:v0.1.2@sha256:9be2d158eb93ffa431399c9240b6115f626f47476bc6327268bdc36c6f981744 |
| 091 | baseline | task-091-baseline/task_091__okeQPcT | docker.io/kevinxulearning/swe-bench-science-environment-python-task-091:v0.1.2@sha256:584de1418e2f75d29b7e9bb725f7effa839f1731fdb450c45476777e4ed328d5 | docker.io/kevinxulearning/swe-bench-science-verifier-python-task-091:v0.1.2@sha256:6de21116ddb0ddafb348136ffa9e07e70c7cb25af6c0d137db73e7ac7673d74f |
| 091 | science | task-091-science/task_091__3JmuMCs | docker.io/kevinxulearning/swe-bench-science-environment-python-task-091:v0.1.2@sha256:584de1418e2f75d29b7e9bb725f7effa839f1731fdb450c45476777e4ed328d5 | docker.io/kevinxulearning/swe-bench-science-verifier-python-task-091:v0.1.2@sha256:6de21116ddb0ddafb348136ffa9e07e70c7cb25af6c0d137db73e7ac7673d74f |
| 114 | baseline | task-114-baseline/task_114__rxKXqVv | docker.io/kevinxulearning/swe-bench-science-environment-python-task-114:v0.1.2@sha256:68c032f628b1aad6432f5bc030537d016dc697778ac57ebfd54595df6b23ab3c | docker.io/kevinxulearning/swe-bench-science-verifier-python-task-114:v0.1.2@sha256:0cfbc99c9056587cebcd3647a2edbfe8550c65d58ba2fbabc8b4e0a242bd24c7 |
| 114 | science | task-114-science/task_114__X86DdXk | docker.io/kevinxulearning/swe-bench-science-environment-python-task-114:v0.1.2@sha256:68c032f628b1aad6432f5bc030537d016dc697778ac57ebfd54595df6b23ab3c | docker.io/kevinxulearning/swe-bench-science-verifier-python-task-114:v0.1.2@sha256:0cfbc99c9056587cebcd3647a2edbfe8550c65d58ba2fbabc8b4e0a242bd24c7 |

Recorded development-task overlap: 091, 058, 009, 114, 001; recorded prior hidden-test exposure: none. These markers are not a claim about other possible exposure.

Independent reconstruction verified 10 recorded trials and 5 recorded task/run pairs. Patch hashes checked: 10; patches missing: 0; patches present without a recorded hash: 0.

This document's quantitative text and tables are generated from durable records. Raw trajectories, patches, verifier receipts and failure diagnostics remain under `runs/task-local-five-v2`. Only receipts beneath this run root are included; earlier development runs are not pooled. Unknowns and incomplete schedules must remain explicit in any downstream claims.
