# Paired comparison: results

Planned tasks (configuration order): 091, 058, 009, 114, 001. Recorded attempts: 10/10; planned attempts without a run receipt: 0. Schedule status: `completed`.

This is an exploratory comparison, not evidence of a general improvement. Unknown outcomes are not failures or successes; missing cost measurements are not zero. No significance or causal-attribution claim is made.

**Helper-source drift was recorded across attempts.** These are descriptive results, not a uniform frozen-method comparison. The commit label alone does not establish identical executed source. Preserve the actual input artifacts and available code snapshots; the recorded hashes do not identify who changed the file.

| Helper file | Recorded SHA-256 | Attempts |
| --- | --- | --- |
| object_context.py | fa2a1156140cd3ac36337870e7bec374db7c2d92b909255b48b283693cc59296 | 091/science, 091/baseline, 058/baseline, 058/science |
| object_context.py | 9294be48829147205272ed78e4352d52c8b16bbb74f1f53aa9ac2f8dfba7166f | 009/science, 009/baseline |
| object_context.py | 4e0c07b6dd019e185388b2c0f537f31ce0895473f920bc6b20e138b33163afae | 114/baseline, 114/science, 001/science, 001/baseline |

## Outcomes for the full planned selection

| Task | Arm | Schedule status | Run status | Hidden-test success | Hidden tests passed/collected | Official reward | Agent seconds |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 091 | science | completed | completed | pass | 3/3 | 1 | 774.42 |
| 091 | baseline | completed | completed | pass | 3/3 | 1 | 473.01 |
| 058 | baseline | completed | completed | pass | 9/9 | 1 | 709.14 |
| 058 | science | completed | completed | fail | 6/9 | 0 | 1152.01 |
| 009 | science | completed | completed | pass | 9/9 | 1 | 682.96 |
| 009 | baseline | completed | completed | pass | 9/9 | 1 | 512.73 |
| 114 | baseline | completed | completed | fail | 10/15 | 0 | 587.91 |
| 114 | science | completed | completed | fail | 13/15 | 0 | 763.37 |
| 001 | science | completed | completed | fail | 1/3 | 0 | 1167.78 |
| 001 | baseline | completed | completed | fail | 1/3 | 0 | 597.26 |

| Arm | Planned | Recorded | Exact pass | Exact fail | Unknown recorded | No receipt |
| --- | --- | --- | --- | --- | --- | --- |
| baseline | 5 | 5 | 3 | 2 | 0 | 0 |
| science | 5 | 5 | 2 | 3 | 0 | 0 |

| Paired outcome | Tasks |
| --- | --- |
| both_success | 2 |
| baseline_only | 1 |
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
| baseline | duration_seconds | 2880.05 | 5 | 0 |
| baseline | input_tokens | 14568552 | 5 | 0 |
| baseline | cached_input_tokens | 13852672 | 5 | 0 |
| baseline | output_tokens | 111550 | 5 | 0 |
| baseline | over_budget_seconds | 0.00 | 5 | 0 |
| science | duration_seconds | 4540.54 | 5 | 0 |
| science | input_tokens | 12996712 | 4 | 1 |
| science | cached_input_tokens | 11974400 | 4 | 1 |
| science | output_tokens | 145125 | 4 | 1 |
| science | over_budget_seconds | 0.00 | 5 | 0 |

### Raw-event token breakdown by task and stage

Input includes cached input; output includes reasoning. Total = input + output, with neither subset added again. Nonreasoning output = output − reasoning; this is not necessarily visible text. These counts are tokens, not monetary cost. Raw `agent/{extract,repair}.jsonl` completed-turn events are cross-checked against stage receipts. Missing reasoning stays unknown. Incomplete stages have unknown full costs; the earlier receipt totals can contain completed turns from an interrupted stage. Trial totals require every expected stage to be present and measured. CLI diagnostic lines are skipped, as in receipt collection.

Multi-call extraction uses separate `agent/extract_draft.jsonl` and `agent/extract_revision.jsonl` logs. Draft and attempted revision are shown separately; `extract total` sums them once. Trial and treatment totals include this aggregate once. An incomplete attempted call leaves full extraction cost unknown.

| Task | Arm | Stage | Status | Input | Cached input | Uncached input | Output | Reasoning output | Nonreasoning output | Total |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 091 | science | extract_draft | completed | 1238254 | 1138176 | 100078 | 13224 | 7886 | 5338 | 1251478 |
| 091 | science | extract total | completed | 1238254 | 1138176 | 100078 | 13224 | 7886 | 5338 | 1251478 |
| 091 | science | repair | completed | 2105388 | 1934848 | 170540 | 22269 | 12187 | 10082 | 2127657 |
| 091 | science | trial total | completed | 3343642 | 3073024 | 270618 | 35493 | 20073 | 15420 | 3379135 |
| 091 | baseline | repair | completed | 2483400 | 2344448 | 138952 | 20896 | 11415 | 9481 | 2504296 |
| 091 | baseline | trial total | completed | 2483400 | 2344448 | 138952 | 20896 | 11415 | 9481 | 2504296 |
| 058 | baseline | repair | completed | 5225950 | 5056000 | 169950 | 17563 | 10680 | 6883 | 5243513 |
| 058 | baseline | trial total | completed | 5225950 | 5056000 | 169950 | 17563 | 10680 | 6883 | 5243513 |
| 058 | science | extract_draft | timeout | unknown | unknown | unknown | unknown | unknown | unknown | unknown |
| 058 | science | extract total | timeout | unknown | unknown | unknown | unknown | unknown | unknown | unknown |
| 058 | science | repair | completed | 4720323 | 4541952 | 178371 | 17215 | 8361 | 8854 | 4737538 |
| 058 | science | trial total | completed | unknown | unknown | unknown | unknown | unknown | unknown | unknown |
| 009 | science | extract_draft | completed | 686867 | 563200 | 123667 | 12022 | 2452 | 9570 | 698889 |
| 009 | science | extract total | completed | 686867 | 563200 | 123667 | 12022 | 2452 | 9570 | 698889 |
| 009 | science | repair | completed | 1708305 | 1579776 | 128529 | 19999 | 14270 | 5729 | 1728304 |
| 009 | science | trial total | completed | 2395172 | 2142976 | 252196 | 32021 | 16722 | 15299 | 2427193 |
| 009 | baseline | repair | completed | 1158536 | 1035264 | 123272 | 25234 | 15870 | 9364 | 1183770 |
| 009 | baseline | trial total | completed | 1158536 | 1035264 | 123272 | 25234 | 15870 | 9364 | 1183770 |
| 114 | baseline | repair | completed | 3124910 | 2972160 | 152750 | 23892 | 15427 | 8465 | 3148802 |
| 114 | baseline | trial total | completed | 3124910 | 2972160 | 152750 | 23892 | 15427 | 8465 | 3148802 |
| 114 | science | extract_draft | completed | 733230 | 654848 | 78382 | 17326 | 7594 | 9732 | 750556 |
| 114 | science | extract total | completed | 733230 | 654848 | 78382 | 17326 | 7594 | 9732 | 750556 |
| 114 | science | repair | completed | 2141489 | 2014976 | 126513 | 15377 | 7194 | 8183 | 2156866 |
| 114 | science | trial total | completed | 2874719 | 2669824 | 204895 | 32703 | 14788 | 17915 | 2907422 |
| 001 | science | extract_draft | completed | 951350 | 864512 | 86838 | 12936 | 6416 | 6520 | 964286 |
| 001 | science | extract total | completed | 951350 | 864512 | 86838 | 12936 | 6416 | 6520 | 964286 |
| 001 | science | repair | completed | 3431829 | 3224064 | 207765 | 31972 | 15923 | 16049 | 3463801 |
| 001 | science | trial total | completed | 4383179 | 4088576 | 294603 | 44908 | 22339 | 22569 | 4428087 |
| 001 | baseline | repair | completed | 2575756 | 2444800 | 130956 | 23965 | 16144 | 7821 | 2599721 |
| 001 | baseline | trial total | completed | 2575756 | 2444800 | 130956 | 23965 | 16144 | 7821 | 2599721 |

### Treatment stages versus baseline total

These are raw input-plus-output token counts, not a monetary bill. The percentage compares the full treatment with the full baseline; unknown or incomplete costs remain unknown. Code-owned preparation, assembly and probe execution have no separate model calls; their time is included in extraction, and material read by the model contributes to that stage's input tokens. These tables exclude development-assistant and posthoc-review usage.

| Task | Baseline total | Extraction | Treatment repair | Treatment total | Change vs baseline |
| --- | --- | --- | --- | --- | --- |
| 091 | 2504296 | 1251478 | 2127657 | 3379135 | +34.9% |
| 058 | 5243513 | unknown | 4737538 | unknown | unknown |
| 009 | 1183770 | 698889 | 1728304 | 2427193 | +105.0% |
| 114 | 3148802 | 750556 | 2156866 | 2907422 | -7.7% |
| 001 | 2599721 | 964286 | 3463801 | 4428087 | +70.3% |
| All planned tasks | 14680102 | unknown | 14214166 | unknown | unknown |

Schedule elapsed seconds (including setup and verification): 5123.73.

## Extraction and graph coverage

### Task 091

Handoff status: `usable_graph`; graph artifact: available.

| Stage/phase | Status | Seconds |
| --- | --- | --- |
| extract | completed | 294.18 |
| prepare | ready | 2.84 |
| extract_draft | completed | 290.54 |
| assemble_initial | scientific_objects | 0.79 |

Graph nodes: objects=123, operations=33, links=143, unsupported=172.
Recorded mechanical coverage: inspected_calls=17, scientific_api_calls=0, scientific_call_fraction=0.0, scientific_operations=0, support_operations=17, uninterpreted_calls=16, unsupported_cases=172.

Interpretation delivery: enriched; annotated objects: 11. These are delivery counts, not scientific correctness.

### Task 058

Handoff status: `usable_graph`; graph artifact: available.

| Stage/phase | Status | Seconds |
| --- | --- | --- |
| extract | timeout | 373.17 |
| prepare | ready | 6.92 |
| extract_draft | timeout | 364.01 |
| assemble_initial | scientific_objects | 2.23 |

Graph nodes: objects=10892, operations=3609, links=14396, unsupported=3660.
Recorded mechanical coverage: inspected_calls=20, scientific_api_calls=0, scientific_call_fraction=0.0, scientific_operations=0, support_operations=3589, uninterpreted_calls=20, unsupported_cases=3660.

Interpretation delivery: code_only; annotated objects: 0. These are delivery counts, not scientific correctness.

### Task 009

Handoff status: `usable_graph`; graph artifact: available.

| Stage/phase | Status | Seconds |
| --- | --- | --- |
| extract | completed | 251.42 |
| prepare | ready | 1.28 |
| extract_draft | completed | 249.39 |
| assemble_initial | scientific_objects | 0.75 |

Graph nodes: objects=305, operations=97, links=513, unsupported=133.
Recorded mechanical coverage: inspected_calls=65, scientific_api_calls=0, scientific_call_fraction=0.0, scientific_operations=0, support_operations=36, uninterpreted_calls=61, unsupported_cases=133.

Interpretation delivery: enriched; annotated objects: 17. These are delivery counts, not scientific correctness.

### Task 114

Handoff status: `usable_graph`; graph artifact: available.

| Stage/phase | Status | Seconds |
| --- | --- | --- |
| extract | completed | 362.20 |
| prepare | ready | 2.10 |
| extract_draft | completed | 359.35 |
| assemble_initial | scientific_objects | 0.75 |

Graph nodes: objects=220, operations=60, links=324, unsupported=81.
Recorded mechanical coverage: inspected_calls=43, scientific_api_calls=0, scientific_call_fraction=0.0, scientific_operations=0, support_operations=19, uninterpreted_calls=41, unsupported_cases=81.

Interpretation delivery: enriched; annotated objects: 15. These are delivery counts, not scientific correctness.

### Task 001

Handoff status: `usable_graph`; graph artifact: available.

| Stage/phase | Status | Seconds |
| --- | --- | --- |
| extract | completed | 296.73 |
| prepare | ready | 0.99 |
| extract_draft | completed | 294.96 |
| assemble_initial | scientific_objects | 0.77 |

Graph nodes: objects=176, operations=44, links=211, unsupported=69.
Recorded mechanical coverage: inspected_calls=34, scientific_api_calls=0, scientific_call_fraction=0.0, scientific_operations=0, support_operations=10, uninterpreted_calls=34, unsupported_cases=69.

Interpretation delivery: enriched; annotated objects: 11. These are delivery counts, not scientific correctness.

Coverage counters measure recoverable representations and supported rules, not scientific correctness. Neither successful extraction nor a passed probe establishes that the supplied guidance caused a repair outcome.

## Measured Docker resources

| Task | Arm | Setup receipt | Docker GiB | Task requested GiB | Docker CPUs | Below requested memory |
| --- | --- | --- | --- | --- | --- | --- |
| 091 | science | available | 8.72 | 8.00 | 4 | False |
| 091 | baseline | available | 8.72 | 8.00 | 4 | False |
| 058 | baseline | available | 8.72 | 8.00 | 4 | False |
| 058 | science | available | 8.72 | 8.00 | 4 | False |
| 009 | science | available | 8.72 | 8.00 | 4 | False |
| 009 | baseline | available | 8.72 | 8.00 | 4 | False |
| 114 | baseline | available | 8.72 | 8.00 | 4 | False |
| 114 | science | available | 8.72 | 8.00 | 4 | False |
| 001 | science | available | 8.72 | 8.00 | 4 | False |
| 001 | baseline | available | 8.72 | 8.00 | 4 | False |

Docker totals are measured daemon allocation, not proof of per-container effective limits or parity with published benchmark resources. Missing setup receipts leave actual allocation unknown; requested resources alone do not establish feasibility.

## Protocol and provenance

Model: gpt-5.6-luna/xhigh; Codex 0.153.4; Pier 0.3.0. Total allowance: 1800 seconds; extraction cap: 600 seconds. Attempts per task/arm: 1; concurrency: 2.

Planned order: 091/science → 091/baseline → 058/baseline → 058/science → 009/science → 009/baseline → 114/baseline → 114/science → 001/science → 001/baseline.

| Record | Value |
| --- | --- |
| implementation_revision | 972722fa5d94e8afede5b2632ad2b4f1a5cd278f |
| implementation_dirty | False |
| config_sha256 | 5f19150dd92b714758e05291c588e5dfc3bd4460421c683becefb5a261a8a644 |
| selection_sha256 | 409c853fcf71217e5a229024c02c1075f01c7a329361eb2b7e42b5e80578e620 |
| uv_lock_sha256 | d54b54352b038f3237f140916e33f447d9fb01d1f26547e70746c580ff17973f |
| prompt_sha256 | {'prompts/enrich_objects.md': '9818342f007556db278fd178e4fb8ff0d61d3bd4675e227e1a8ff1bf7c43811b', 'prompts/extract.md': '8391ec931305b71b406c74e7784f66c969e28035b14034c98d9b5628977cdfce', 'prompts/extract_revision.md': '3b726cbd85feaea31f8d08e7af4fdfdda5691cc2177b603d8b73b5be4d0422a2', 'prompts/repair.md': '9b9bd47560b889414d5b5b4fcb05c0dd6ba406856a6ce7fdee9c59102115066b'} |
| dataset_revision | d8bdbcb4ecb2b565686382459c815d2b6291fd31 |
| release_commit | 42e7e97915ff7d73436a5d37b5cbe6b77e9c2a00 |
| release_receipt | data/random-five-v1-release.json |
| sampling_manifest | configs/random-five-v1.selection.json |
| sampling_manifest_sha256 | 8318fa6f565300af5673360b179706c00ce69d0291b8788d23aa4f2478a3080e |
| allow_restricted_licenses | False |

| Task | Arm | Trial path | Environment image | Verifier image |
| --- | --- | --- | --- | --- |
| 001 | baseline | task-001-baseline/task_001__UegkNMu | docker.io/kevinxulearning/swe-bench-science-environment-python-task-001:v0.1.0@sha256:0b6b41e556cd862f10e9e8c489e9b539eda27d277718e0504de440048c62d3c7 | docker.io/kevinxulearning/swe-bench-science-verifier-python-task-001:v0.1.0@sha256:7af68a1c44876615b0f961abd18e7fb656dae5f117820a35ff8e1d10faa430b0 |
| 001 | science | task-001-science/task_001__rxJHtFM | docker.io/kevinxulearning/swe-bench-science-environment-python-task-001:v0.1.0@sha256:0b6b41e556cd862f10e9e8c489e9b539eda27d277718e0504de440048c62d3c7 | docker.io/kevinxulearning/swe-bench-science-verifier-python-task-001:v0.1.0@sha256:7af68a1c44876615b0f961abd18e7fb656dae5f117820a35ff8e1d10faa430b0 |
| 009 | baseline | task-009-baseline/task_009__DN6gUf3 | docker.io/kevinxulearning/swe-bench-science-environment-python-task-009:v0.1.2@sha256:f4c314a57e656f4f4b480fa5d4967f476fb36c7aa5eb22e5f95398554d9ec79c | docker.io/kevinxulearning/swe-bench-science-verifier-python-task-009:v0.1.2@sha256:fe483ea0e64c344cc2cce2bd520aadc241558e7a7d2f6f397e18267d5bcbf7bb |
| 009 | science | task-009-science/task_009__NQgBc9X | docker.io/kevinxulearning/swe-bench-science-environment-python-task-009:v0.1.2@sha256:f4c314a57e656f4f4b480fa5d4967f476fb36c7aa5eb22e5f95398554d9ec79c | docker.io/kevinxulearning/swe-bench-science-verifier-python-task-009:v0.1.2@sha256:fe483ea0e64c344cc2cce2bd520aadc241558e7a7d2f6f397e18267d5bcbf7bb |
| 058 | baseline | task-058-baseline/task_058__zudmxwQ | docker.io/kevinxulearning/swe-bench-science-environment-python-cpp-task-058:v0.1.2@sha256:1b7822c1dbae675f2c32a19ec6cee830f93bd8248e459d3836d962805a3e680b | docker.io/kevinxulearning/swe-bench-science-verifier-python-cpp-task-058:v0.1.2@sha256:9be2d158eb93ffa431399c9240b6115f626f47476bc6327268bdc36c6f981744 |
| 058 | science | task-058-science/task_058__nrvUsTR | docker.io/kevinxulearning/swe-bench-science-environment-python-cpp-task-058:v0.1.2@sha256:1b7822c1dbae675f2c32a19ec6cee830f93bd8248e459d3836d962805a3e680b | docker.io/kevinxulearning/swe-bench-science-verifier-python-cpp-task-058:v0.1.2@sha256:9be2d158eb93ffa431399c9240b6115f626f47476bc6327268bdc36c6f981744 |
| 091 | baseline | task-091-baseline/task_091__vAJWaLT | docker.io/kevinxulearning/swe-bench-science-environment-python-task-091:v0.1.2@sha256:584de1418e2f75d29b7e9bb725f7effa839f1731fdb450c45476777e4ed328d5 | docker.io/kevinxulearning/swe-bench-science-verifier-python-task-091:v0.1.2@sha256:6de21116ddb0ddafb348136ffa9e07e70c7cb25af6c0d137db73e7ac7673d74f |
| 091 | science | task-091-science/task_091__Lzsen2s | docker.io/kevinxulearning/swe-bench-science-environment-python-task-091:v0.1.2@sha256:584de1418e2f75d29b7e9bb725f7effa839f1731fdb450c45476777e4ed328d5 | docker.io/kevinxulearning/swe-bench-science-verifier-python-task-091:v0.1.2@sha256:6de21116ddb0ddafb348136ffa9e07e70c7cb25af6c0d137db73e7ac7673d74f |
| 114 | baseline | task-114-baseline/task_114__AsdTg4B | docker.io/kevinxulearning/swe-bench-science-environment-python-task-114:v0.1.2@sha256:68c032f628b1aad6432f5bc030537d016dc697778ac57ebfd54595df6b23ab3c | docker.io/kevinxulearning/swe-bench-science-verifier-python-task-114:v0.1.2@sha256:0cfbc99c9056587cebcd3647a2edbfe8550c65d58ba2fbabc8b4e0a242bd24c7 |
| 114 | science | task-114-science/task_114__7Dmkndc | docker.io/kevinxulearning/swe-bench-science-environment-python-task-114:v0.1.2@sha256:68c032f628b1aad6432f5bc030537d016dc697778ac57ebfd54595df6b23ab3c | docker.io/kevinxulearning/swe-bench-science-verifier-python-task-114:v0.1.2@sha256:0cfbc99c9056587cebcd3647a2edbfe8550c65d58ba2fbabc8b4e0a242bd24c7 |

Recorded development-task overlap: 091, 058, 009, 114, 001; recorded prior hidden-test exposure: 001. These markers are not a claim about other possible exposure.

Independent reconstruction verified 10 recorded trials and 5 recorded task/run pairs. Patch hashes checked: 10; patches missing: 0; patches present without a recorded hash: 0.

This document's quantitative text and tables are generated from durable records. Raw trajectories, patches, verifier receipts and failure diagnostics remain under `runs/workflow-five-luna-v1`. Only receipts beneath this run root are included; earlier development runs are not pooled. Unknowns and incomplete schedules must remain explicit in any downstream claims.
