# Paired comparison: results

Planned tasks (configuration order): 091, 114. Recorded attempts: 4/4; planned attempts without a run receipt: 0. Schedule status: `completed`.

This is an exploratory comparison, not evidence of a general improvement. Unknown outcomes are not failures or successes; missing cost measurements are not zero. No significance or causal-attribution claim is made.

## Outcomes for the full planned selection

| Task | Arm | Schedule status | Run status | Hidden-test success | Hidden tests passed/collected | Official reward | Agent seconds |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 091 | science | completed | completed | fail | 0/3 | 0 | 357.22 |
| 091 | baseline | completed | completed | pass | 3/3 | 1 | 116.71 |
| 114 | baseline | completed | completed | fail | 13/15 | 0 | 328.41 |
| 114 | science | completed | completed | fail | 13/15 | 0 | 548.10 |

| Arm | Planned | Recorded | Exact pass | Exact fail | Unknown recorded | No receipt |
| --- | --- | --- | --- | --- | --- | --- |
| baseline | 2 | 2 | 1 | 1 | 0 | 0 |
| science | 2 | 2 | 0 | 2 | 0 | 0 |

| Paired outcome | Tasks |
| --- | --- |
| both_success | 0 |
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
| baseline | duration_seconds | 445.12 | 2 | 0 |
| baseline | input_tokens | 1284764 | 2 | 0 |
| baseline | cached_input_tokens | 1191936 | 2 | 0 |
| baseline | output_tokens | 10002 | 2 | 0 |
| baseline | over_budget_seconds | 0.00 | 2 | 0 |
| science | duration_seconds | 905.32 | 2 | 0 |
| science | input_tokens | 1159270 | 1 | 1 |
| science | cached_input_tokens | 1050752 | 1 | 1 |
| science | output_tokens | 13495 | 1 | 1 |
| science | over_budget_seconds | 0.00 | 2 | 0 |

### Raw-event token breakdown by task and stage

Input includes cached input; output includes reasoning. Total = input + output, with neither subset added again. Nonreasoning output = output − reasoning; this is not necessarily visible text. These counts are tokens, not monetary cost. Raw `agent/{extract,repair}.jsonl` completed-turn events are cross-checked against stage receipts. Missing reasoning stays unknown. Incomplete stages have unknown full costs; the earlier receipt totals can contain completed turns from an interrupted stage. Trial totals require every expected stage to be present and measured. CLI diagnostic lines are skipped, as in receipt collection.

Multi-call extraction uses separate `agent/extract_draft.jsonl` and `agent/extract_revision.jsonl` logs. Draft and attempted revision are shown separately; `extract total` sums them once. Trial and treatment totals include this aggregate once. An incomplete attempted call leaves full extraction cost unknown.

| Task | Arm | Stage | Status | Input | Cached input | Uncached input | Output | Reasoning output | Nonreasoning output | Total |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 091 | science | extract_draft | completed | 170294 | 141440 | 28854 | 2781 | 200 | 2581 | 173075 |
| 091 | science | extract_revision | timeout | unknown | unknown | unknown | unknown | unknown | unknown | unknown |
| 091 | science | extract total | completed | unknown | unknown | unknown | unknown | unknown | unknown | unknown |
| 091 | science | repair | completed | 192264 | 165888 | 26376 | 2949 | 149 | 2800 | 195213 |
| 091 | science | trial total | completed | unknown | unknown | unknown | unknown | unknown | unknown | unknown |
| 091 | baseline | repair | completed | 287573 | 255360 | 32213 | 2400 | 143 | 2257 | 289973 |
| 091 | baseline | trial total | completed | 287573 | 255360 | 32213 | 2400 | 143 | 2257 | 289973 |
| 114 | baseline | repair | completed | 997191 | 936576 | 60615 | 7602 | 1481 | 6121 | 1004793 |
| 114 | baseline | trial total | completed | 997191 | 936576 | 60615 | 7602 | 1481 | 6121 | 1004793 |
| 114 | science | extract_draft | completed | 135356 | 110464 | 24892 | 2902 | 314 | 2588 | 138258 |
| 114 | science | extract total | completed | 135356 | 110464 | 24892 | 2902 | 314 | 2588 | 138258 |
| 114 | science | repair | completed | 1023914 | 940288 | 83626 | 10593 | 3821 | 6772 | 1034507 |
| 114 | science | trial total | completed | 1159270 | 1050752 | 108518 | 13495 | 4135 | 9360 | 1172765 |

### Treatment stages versus baseline total

These are raw input-plus-output token counts, not a monetary bill. The percentage compares the full treatment with the full baseline; unknown or incomplete costs remain unknown. Code-owned preparation, assembly and probe execution have no separate model calls; their time is included in extraction, and material read by the model contributes to that stage's input tokens. These tables exclude development-assistant and posthoc-review usage.

| Task | Baseline total | Extraction | Treatment repair | Treatment total | Change vs baseline |
| --- | --- | --- | --- | --- | --- |
| 091 | 289973 | unknown | 195213 | unknown | unknown |
| 114 | 1004793 | 138258 | 1034507 | 1172765 | +16.7% |
| All planned tasks | 1294766 | unknown | 1229720 | unknown | unknown |

Schedule elapsed seconds (including setup and verification): 1052.51.

## Extraction and graph coverage

### Task 091

Handoff status: `usable_graph`; graph artifact: available.

| Stage/phase | Status | Seconds |
| --- | --- | --- |
| extract | completed | 214.60 |
| extract_draft | completed | 114.08 |
| prepare | ready | 1.10 |
| assemble_initial | usable_graph | 4.07 |
| probes | completed | 1.80 |
| assemble_observed | usable_graph | 4.43 |
| extract_revision | timeout | 90.23 |

Graph nodes: claims=1, quantities=2, evidence=11, observations=1.
Recorded mechanical coverage: claims=1, conflicts=0, dimension_resolved=0, expressions=1, lift_supported=0, lift_unknown=1, scale_resolved=0, shape_resolved=0.

code_grounding: source_matched=1.
alignments: unknown=1.

### Task 114

Handoff status: `usable_graph`; graph artifact: available.

| Stage/phase | Status | Seconds |
| --- | --- | --- |
| extract | completed | 120.73 |
| extract_draft | completed | 110.33 |
| prepare | ready | 1.80 |
| assemble_initial | usable_graph | 3.03 |
| probes | completed | 4.42 |
| assemble_observed | usable_graph | 2.95 |
| extract_revision | not_run | 0.00 |

Graph nodes: claims=1, quantities=5, evidence=13, observations=1.
Recorded mechanical coverage: claims=1, conflicts=0, dimension_resolved=0, expressions=1, lift_supported=0, lift_unknown=1, scale_resolved=0, shape_resolved=0.

code_grounding: unresolved=1.
alignments: unknown=1.

Coverage counters measure recoverable representations and supported rules, not scientific correctness. Neither successful extraction nor a passed probe establishes that the supplied guidance caused a repair outcome.

## Measured Docker resources

| Task | Arm | Setup receipt | Docker GiB | Task requested GiB | Docker CPUs | Below requested memory |
| --- | --- | --- | --- | --- | --- | --- |
| 091 | science | available | 8.72 | 8.00 | 4 | False |
| 091 | baseline | available | 8.72 | 8.00 | 4 | False |
| 114 | baseline | available | 8.72 | 8.00 | 4 | False |
| 114 | science | available | 8.72 | 8.00 | 4 | False |

Docker totals are measured daemon allocation, not proof of per-container effective limits or parity with published benchmark resources. Missing setup receipts leave actual allocation unknown; requested resources alone do not establish feasibility.

## Protocol and provenance

Model: gpt-6-astra/medium; Codex 0.153.4; Pier 0.3.0. Total allowance: 1800 seconds; extraction cap: 360 seconds. Attempts per task/arm: 1; concurrency: 2.

Planned order: 091/science → 091/baseline → 114/baseline → 114/science.

| Record | Value |
| --- | --- |
| implementation_revision | a92d3db3e2e5b9ff79669ccd9827cde1f15f9736 |
| implementation_dirty | False |
| config_sha256 | 874d5e3ea8849e4dffc9ac594a00447a9d9be55f70bd72c17ce1d4482c5e5333 |
| selection_sha256 | 409c853fcf71217e5a229024c02c1075f01c7a329361eb2b7e42b5e80578e620 |
| uv_lock_sha256 | c61a78a1c9ba91fe4ebf14ec3f35fd65e9d4e99a567afe06fed77cdac3bc38f4 |
| prompt_sha256 | {'prompts/extract.md': '8391ec931305b71b406c74e7784f66c969e28035b14034c98d9b5628977cdfce', 'prompts/extract_revision.md': '3b726cbd85feaea31f8d08e7af4fdfdda5691cc2177b603d8b73b5be4d0422a2', 'prompts/repair.md': '9b9bd47560b889414d5b5b4fcb05c0dd6ba406856a6ce7fdee9c59102115066b'} |
| dataset_revision | d8bdbcb4ecb2b565686382459c815d2b6291fd31 |
| release_commit | 42e7e97915ff7d73436a5d37b5cbe6b77e9c2a00 |
| release_receipt | data/random-five-v1-release.json |
| sampling_manifest | unknown |
| sampling_manifest_sha256 | unknown |
| allow_restricted_licenses | False |

| Task | Arm | Trial path | Environment image | Verifier image |
| --- | --- | --- | --- | --- |
| 091 | baseline | task-091-baseline/task_091__x5zweVn | docker.io/kevinxulearning/swe-bench-science-environment-python-task-091:v0.1.2@sha256:584de1418e2f75d29b7e9bb725f7effa839f1731fdb450c45476777e4ed328d5 | docker.io/kevinxulearning/swe-bench-science-verifier-python-task-091:v0.1.2@sha256:6de21116ddb0ddafb348136ffa9e07e70c7cb25af6c0d137db73e7ac7673d74f |
| 091 | science | task-091-science/task_091__kHGMADp | docker.io/kevinxulearning/swe-bench-science-environment-python-task-091:v0.1.2@sha256:584de1418e2f75d29b7e9bb725f7effa839f1731fdb450c45476777e4ed328d5 | docker.io/kevinxulearning/swe-bench-science-verifier-python-task-091:v0.1.2@sha256:6de21116ddb0ddafb348136ffa9e07e70c7cb25af6c0d137db73e7ac7673d74f |
| 114 | baseline | task-114-baseline/task_114__vpokiQx | docker.io/kevinxulearning/swe-bench-science-environment-python-task-114:v0.1.2@sha256:68c032f628b1aad6432f5bc030537d016dc697778ac57ebfd54595df6b23ab3c | docker.io/kevinxulearning/swe-bench-science-verifier-python-task-114:v0.1.2@sha256:0cfbc99c9056587cebcd3647a2edbfe8550c65d58ba2fbabc8b4e0a242bd24c7 |
| 114 | science | task-114-science/task_114__Tf6mqHJ | docker.io/kevinxulearning/swe-bench-science-environment-python-task-114:v0.1.2@sha256:68c032f628b1aad6432f5bc030537d016dc697778ac57ebfd54595df6b23ab3c | docker.io/kevinxulearning/swe-bench-science-verifier-python-task-114:v0.1.2@sha256:0cfbc99c9056587cebcd3647a2edbfe8550c65d58ba2fbabc8b4e0a242bd24c7 |

Recorded development-task overlap: 091, 114; recorded prior hidden-test exposure: none. These markers are not a claim about other possible exposure.

Independent reconstruction verified 4 recorded trials and 2 recorded task/run pairs. Patch hashes checked: 4; patches missing: 0; patches present without a recorded hash: 0.

This document's quantitative text and tables are generated from durable records. Raw trajectories, patches, verifier receipts and failure diagnostics remain under `runs/probe-first-pairs-v1`. Only receipts beneath this run root are included; earlier development runs are not pooled. Unknowns and incomplete schedules must remain explicit in any downstream claims.
