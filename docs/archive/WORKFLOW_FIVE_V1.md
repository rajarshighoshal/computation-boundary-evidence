# Paired comparison: results

Planned tasks (configuration order): 091, 058, 009, 114, 001. Recorded attempts: 4/10; planned attempts without a run receipt: 6. Schedule status: `runner_failure`.

This is an exploratory comparison, not evidence of a general improvement. Unknown outcomes are not failures or successes; missing cost measurements are not zero. No significance or causal-attribution claim is made.

**The planned comparison is incomplete.** All selected tasks and arms remain listed below; unrun arms are not silently dropped or included as failures in an observed success rate.

Schedule error: RuntimeError: Runner failed; retained runs/workflow-five-v1/task-058-science-runner.log. Remaining schedule has not been executed.

## Outcomes for the full planned selection

| Task | Arm | Schedule status | Run status | Hidden-test success | Hidden tests passed/collected | Official reward | Agent seconds |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 091 | science | completed | completed | fail | 0/3 | 0 | 241.22 |
| 091 | baseline | completed | completed | pass | 3/3 | 1 | 122.00 |
| 058 | baseline | interrupted | interrupted | unknown | unknown/unknown | unknown | 199.75 |
| 058 | science | infrastructure_failure | infrastructure_failure | unknown | unknown/unknown | unknown | 174.98 |
| 009 | science | not_run | no receipt | unknown | unknown/unknown | unknown | unknown |
| 009 | baseline | not_run | no receipt | unknown | unknown/unknown | unknown | unknown |
| 114 | baseline | not_run | no receipt | unknown | unknown/unknown | unknown | unknown |
| 114 | science | not_run | no receipt | unknown | unknown/unknown | unknown | unknown |
| 001 | science | not_run | no receipt | unknown | unknown/unknown | unknown | unknown |
| 001 | baseline | not_run | no receipt | unknown | unknown/unknown | unknown | unknown |

| Arm | Planned | Recorded | Exact pass | Exact fail | Unknown recorded | No receipt |
| --- | --- | --- | --- | --- | --- | --- |
| baseline | 5 | 2 | 1 | 0 | 1 | 3 |
| science | 5 | 2 | 0 | 1 | 1 | 3 |

| Paired outcome | Tasks |
| --- | --- |
| both_success | 0 |
| baseline_only | 1 |
| science_only | 0 |
| both_failure | 0 |
| unknown | 1 |
| missing_baseline | 0 |
| missing_science | 0 |
| neither_arm_recorded | 3 |

Exact hidden-test success and official reward are reported separately. Per-test Fail2Pass/Pass2Pass require matching original-baseline test identities; availability and diagnostics remain in the audited summary.

## Time and token accounting

Agent time includes extraction and handoff where applicable, but excludes image pulls, environment preparation and official verification. Token totals require usage from every recorded agent stage; repair-only usage is not reported as a full science-arm total. Observed totals below cover only the stated measured trials, not unrecorded attempts.

| Arm | Quantity | Observed total | Measured trials | Missing recorded trials |
| --- | --- | --- | --- | --- |
| baseline | duration_seconds | 321.75 | 2 | 0 |
| baseline | input_tokens | 237127 | 1 | 1 |
| baseline | cached_input_tokens | 206976 | 1 | 1 |
| baseline | output_tokens | 2515 | 1 | 1 |
| baseline | over_budget_seconds | 0.00 | 2 | 0 |
| science | duration_seconds | 416.20 | 2 | 0 |
| science | input_tokens | 739322 | 1 | 1 |
| science | cached_input_tokens | 631040 | 1 | 1 |
| science | output_tokens | 4915 | 1 | 1 |
| science | over_budget_seconds | 0.00 | 2 | 0 |

### Raw-event token breakdown by task and stage

Input includes cached input; output includes reasoning. Total = input + output, with neither subset added again. Nonreasoning output = output − reasoning; this is not necessarily visible text. These counts are tokens, not monetary cost. Raw `agent/{extract,repair}.jsonl` completed-turn events are cross-checked against stage receipts. Missing reasoning stays unknown. Incomplete stages have unknown full costs; the earlier receipt totals can contain completed turns from an interrupted stage. Trial totals require every expected stage to be present and measured. CLI diagnostic lines are skipped, as in receipt collection.

Multi-call extraction uses separate `agent/extract_draft.jsonl` and `agent/extract_revision.jsonl` logs. Draft and attempted revision are shown separately; `extract total` sums them once. Trial and treatment totals include this aggregate once. An incomplete attempted call leaves full extraction cost unknown.

| Task | Arm | Stage | Status | Input | Cached input | Uncached input | Output | Reasoning output | Nonreasoning output | Total |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 091 | science | extract_draft | completed | 210541 | 168320 | 42221 | 2690 | 85 | 2605 | 213231 |
| 091 | science | extract total | completed | 210541 | 168320 | 42221 | 2690 | 85 | 2605 | 213231 |
| 091 | science | repair | completed | 528781 | 462720 | 66061 | 2225 | 165 | 2060 | 531006 |
| 091 | science | trial total | completed | 739322 | 631040 | 108282 | 4915 | 250 | 4665 | 744237 |
| 091 | baseline | repair | completed | 237127 | 206976 | 30151 | 2515 | 222 | 2293 | 239642 |
| 091 | baseline | trial total | completed | 237127 | 206976 | 30151 | 2515 | 222 | 2293 | 239642 |
| 058 | baseline | repair | interrupted | unknown | unknown | unknown | unknown | unknown | unknown | unknown |
| 058 | baseline | trial total | interrupted | unknown | unknown | unknown | unknown | unknown | unknown | unknown |
| 058 | science | extract_draft | completed | 463066 | 393088 | 69978 | 3745 | 414 | 3331 | 466811 |
| 058 | science | extract total | completed | 463066 | 393088 | 69978 | 3745 | 414 | 3331 | 466811 |
| 058 | science | repair | failed | unknown | unknown | unknown | unknown | unknown | unknown | unknown |
| 058 | science | trial total | infrastructure_failure | unknown | unknown | unknown | unknown | unknown | unknown | unknown |
| 009 | science | trial total | no receipt | unknown | unknown | unknown | unknown | unknown | unknown | unknown |
| 009 | baseline | trial total | no receipt | unknown | unknown | unknown | unknown | unknown | unknown | unknown |
| 114 | baseline | trial total | no receipt | unknown | unknown | unknown | unknown | unknown | unknown | unknown |
| 114 | science | trial total | no receipt | unknown | unknown | unknown | unknown | unknown | unknown | unknown |
| 001 | science | trial total | no receipt | unknown | unknown | unknown | unknown | unknown | unknown | unknown |
| 001 | baseline | trial total | no receipt | unknown | unknown | unknown | unknown | unknown | unknown | unknown |

### Treatment stages versus baseline total

These are raw input-plus-output token counts, not a monetary bill. The percentage compares the full treatment with the full baseline; unknown or incomplete costs remain unknown. Code-owned preparation, assembly and probe execution have no separate model calls; their time is included in extraction, and material read by the model contributes to that stage's input tokens. These tables exclude development-assistant and posthoc-review usage.

| Task | Baseline total | Extraction | Treatment repair | Treatment total | Change vs baseline |
| --- | --- | --- | --- | --- | --- |
| 091 | 239642 | 213231 | 531006 | 744237 | +210.6% |
| 058 | unknown | 466811 | unknown | unknown | unknown |
| 009 | unknown | unknown | unknown | unknown | unknown |
| 114 | unknown | unknown | unknown | unknown | unknown |
| 001 | unknown | unknown | unknown | unknown | unknown |
| All planned tasks | unknown | unknown | unknown | unknown | unknown |

Schedule elapsed seconds (including setup and verification): 541.59.

## Extraction and graph coverage

### Task 091

Handoff status: `usable_graph`; graph artifact: available.

| Stage/phase | Status | Seconds |
| --- | --- | --- |
| extract | completed | 119.42 |
| prepare | ready | 2.75 |
| extract_draft | completed | 115.93 |
| assemble_initial | scientific_objects | 0.75 |

Graph nodes: objects=123, operations=33, links=143, unsupported=172.
Recorded mechanical coverage: inspected_calls=17, scientific_api_calls=0, scientific_call_fraction=0.0, scientific_operations=0, support_operations=17, uninterpreted_calls=16, unsupported_cases=172.

Interpretation delivery: enriched; annotated objects: 11. These are delivery counts, not scientific correctness.

### Task 058

Handoff status: `usable_graph`; graph artifact: available.

| Stage/phase | Status | Seconds |
| --- | --- | --- |
| extract | completed | 155.31 |
| prepare | ready | 7.72 |
| extract_draft | completed | 145.19 |
| assemble_initial | scientific_objects | 2.39 |

Graph nodes: objects=10892, operations=3609, links=14396, unsupported=3660.
Recorded mechanical coverage: inspected_calls=20, scientific_api_calls=0, scientific_call_fraction=0.0, scientific_operations=0, support_operations=3589, uninterpreted_calls=20, unsupported_cases=3660.

Interpretation delivery: enriched; annotated objects: 12. These are delivery counts, not scientific correctness.

### Task 009

Handoff status: `unknown`; graph artifact: missing.

Extraction timing/status receipt unavailable.

Graph nodes: objects=unknown, operations=unknown, links=unknown, unsupported=unknown.
Recorded mechanical coverage: unknown.

Interpretation delivery: unknown; annotated objects: unknown. These are delivery counts, not scientific correctness.

### Task 114

Handoff status: `unknown`; graph artifact: missing.

Extraction timing/status receipt unavailable.

Graph nodes: objects=unknown, operations=unknown, links=unknown, unsupported=unknown.
Recorded mechanical coverage: unknown.

Interpretation delivery: unknown; annotated objects: unknown. These are delivery counts, not scientific correctness.

### Task 001

Handoff status: `unknown`; graph artifact: missing.

Extraction timing/status receipt unavailable.

Graph nodes: objects=unknown, operations=unknown, links=unknown, unsupported=unknown.
Recorded mechanical coverage: unknown.

Interpretation delivery: unknown; annotated objects: unknown. These are delivery counts, not scientific correctness.

Coverage counters measure recoverable representations and supported rules, not scientific correctness. Neither successful extraction nor a passed probe establishes that the supplied guidance caused a repair outcome.

## Measured Docker resources

| Task | Arm | Setup receipt | Docker GiB | Task requested GiB | Docker CPUs | Below requested memory |
| --- | --- | --- | --- | --- | --- | --- |
| 091 | science | available | 8.72 | 8.00 | 4 | False |
| 091 | baseline | available | 8.72 | 8.00 | 4 | False |
| 058 | baseline | available | 8.72 | 8.00 | 4 | False |
| 058 | science | available | 8.72 | 8.00 | 4 | False |
| 009 | science | missing | unknown | unknown | unknown | unknown |
| 009 | baseline | missing | unknown | unknown | unknown | unknown |
| 114 | baseline | missing | unknown | unknown | unknown | unknown |
| 114 | science | missing | unknown | unknown | unknown | unknown |
| 001 | science | missing | unknown | unknown | unknown | unknown |
| 001 | baseline | missing | unknown | unknown | unknown | unknown |

Docker totals are measured daemon allocation, not proof of per-container effective limits or parity with published benchmark resources. Missing setup receipts leave actual allocation unknown; requested resources alone do not establish feasibility.

## Protocol and provenance

Model: gpt-6-astra/medium; Codex 0.153.4; Pier 0.3.0. Total allowance: 1800 seconds; extraction cap: 600 seconds. Attempts per task/arm: 1; concurrency: 2.

Planned order: 091/science → 091/baseline → 058/baseline → 058/science → 009/science → 009/baseline → 114/baseline → 114/science → 001/science → 001/baseline.

| Record | Value |
| --- | --- |
| implementation_revision | 65742769353e13a93c9561e69ab1d8df2543f9db |
| implementation_dirty | False |
| config_sha256 | d3e1e350c22079a40f292cbd0687d399ad182c3b5eba0924dddd691b5d343a6b |
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
| 058 | baseline | task-058-baseline/task_058__RKRBxfG | docker.io/kevinxulearning/swe-bench-science-environment-python-cpp-task-058:v0.1.2@sha256:1b7822c1dbae675f2c32a19ec6cee830f93bd8248e459d3836d962805a3e680b | docker.io/kevinxulearning/swe-bench-science-verifier-python-cpp-task-058:v0.1.2@sha256:9be2d158eb93ffa431399c9240b6115f626f47476bc6327268bdc36c6f981744 |
| 058 | science | task-058-science/task_058__y56EQiC | docker.io/kevinxulearning/swe-bench-science-environment-python-cpp-task-058:v0.1.2@sha256:1b7822c1dbae675f2c32a19ec6cee830f93bd8248e459d3836d962805a3e680b | docker.io/kevinxulearning/swe-bench-science-verifier-python-cpp-task-058:v0.1.2@sha256:9be2d158eb93ffa431399c9240b6115f626f47476bc6327268bdc36c6f981744 |
| 091 | baseline | task-091-baseline/task_091__aFHRf8T | docker.io/kevinxulearning/swe-bench-science-environment-python-task-091:v0.1.2@sha256:584de1418e2f75d29b7e9bb725f7effa839f1731fdb450c45476777e4ed328d5 | docker.io/kevinxulearning/swe-bench-science-verifier-python-task-091:v0.1.2@sha256:6de21116ddb0ddafb348136ffa9e07e70c7cb25af6c0d137db73e7ac7673d74f |
| 091 | science | task-091-science/task_091__qxNgp3x | docker.io/kevinxulearning/swe-bench-science-environment-python-task-091:v0.1.2@sha256:584de1418e2f75d29b7e9bb725f7effa839f1731fdb450c45476777e4ed328d5 | docker.io/kevinxulearning/swe-bench-science-verifier-python-task-091:v0.1.2@sha256:6de21116ddb0ddafb348136ffa9e07e70c7cb25af6c0d137db73e7ac7673d74f |

Recorded development-task overlap: 091, 058, 009, 114, 001; recorded prior hidden-test exposure: 001. These markers are not a claim about other possible exposure.

Independent reconstruction verified 4 recorded trials and 2 recorded task/run pairs. Patch hashes checked: 2; patches missing: 2; patches present without a recorded hash: 0.

This document's quantitative text and tables are generated from durable records. Raw trajectories, patches, verifier receipts and failure diagnostics remain under `runs/workflow-five-v1`. Only receipts beneath this run root are included; earlier development runs are not pooled. Unknowns and incomplete schedules must remain explicit in any downstream claims.
