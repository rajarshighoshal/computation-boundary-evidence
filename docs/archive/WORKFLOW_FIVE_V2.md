# Paired comparison: results

Planned tasks (configuration order): 091, 058, 009, 114, 001. Recorded attempts: 2/10; planned attempts without a run receipt: 8. Schedule status: `interrupted`.

This is an exploratory comparison, not evidence of a general improvement. Unknown outcomes are not failures or successes; missing cost measurements are not zero. No significance or causal-attribution claim is made.

**The planned comparison is incomplete.** All selected tasks and arms remain listed below; unrun arms are not silently dropped or included as failures in an observed success rate.

Schedule error: KeyboardInterrupt: Received signal 15

Operator-requested stop: User requested stop of Astra work and fresh original-five comparison using gpt-5.6-luna at xhigh; preserve all existing attempts without pooling or retrying..
Active at stop request: 091/science during pier. A pre-inference image-pull interruption is not a model repair failure.

## Outcomes for the full planned selection

| Task | Arm | Schedule status | Run status | Hidden-test success | Hidden tests passed/collected | Official reward | Agent seconds |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 091 | science | interrupted | interrupted | unknown | unknown/unknown | unknown | 254.14 |
| 091 | baseline | completed | completed | pass | 3/3 | 1 | 108.05 |
| 058 | baseline | not_run | no receipt | unknown | unknown/unknown | unknown | unknown |
| 058 | science | not_run | no receipt | unknown | unknown/unknown | unknown | unknown |
| 009 | science | not_run | no receipt | unknown | unknown/unknown | unknown | unknown |
| 009 | baseline | not_run | no receipt | unknown | unknown/unknown | unknown | unknown |
| 114 | baseline | not_run | no receipt | unknown | unknown/unknown | unknown | unknown |
| 114 | science | not_run | no receipt | unknown | unknown/unknown | unknown | unknown |
| 001 | science | not_run | no receipt | unknown | unknown/unknown | unknown | unknown |
| 001 | baseline | not_run | no receipt | unknown | unknown/unknown | unknown | unknown |

| Arm | Planned | Recorded | Exact pass | Exact fail | Unknown recorded | No receipt |
| --- | --- | --- | --- | --- | --- | --- |
| baseline | 5 | 1 | 1 | 0 | 0 | 4 |
| science | 5 | 1 | 0 | 0 | 1 | 4 |

| Paired outcome | Tasks |
| --- | --- |
| both_success | 0 |
| baseline_only | 0 |
| science_only | 0 |
| both_failure | 0 |
| unknown | 1 |
| missing_baseline | 0 |
| missing_science | 0 |
| neither_arm_recorded | 4 |

Exact hidden-test success and official reward are reported separately. Per-test Fail2Pass/Pass2Pass require matching original-baseline test identities; availability and diagnostics remain in the audited summary.

## Time and token accounting

Agent time includes extraction and handoff where applicable, but excludes image pulls, environment preparation and official verification. Token totals require usage from every recorded agent stage; repair-only usage is not reported as a full science-arm total. Observed totals below cover only the stated measured trials, not unrecorded attempts.

| Arm | Quantity | Observed total | Measured trials | Missing recorded trials |
| --- | --- | --- | --- | --- |
| baseline | duration_seconds | 108.05 | 1 | 0 |
| baseline | input_tokens | 212226 | 1 | 0 |
| baseline | cached_input_tokens | 179840 | 1 | 0 |
| baseline | output_tokens | 2110 | 1 | 0 |
| baseline | over_budget_seconds | 0.00 | 1 | 0 |
| science | duration_seconds | 254.14 | 1 | 0 |
| science | input_tokens | unknown | 0 | 1 |
| science | cached_input_tokens | unknown | 0 | 1 |
| science | output_tokens | unknown | 0 | 1 |
| science | over_budget_seconds | 0.00 | 1 | 0 |

### Raw-event token breakdown by task and stage

Input includes cached input; output includes reasoning. Total = input + output, with neither subset added again. Nonreasoning output = output − reasoning; this is not necessarily visible text. These counts are tokens, not monetary cost. Raw `agent/{extract,repair}.jsonl` completed-turn events are cross-checked against stage receipts. Missing reasoning stays unknown. Incomplete stages have unknown full costs; the earlier receipt totals can contain completed turns from an interrupted stage. Trial totals require every expected stage to be present and measured. CLI diagnostic lines are skipped, as in receipt collection.

Multi-call extraction uses separate `agent/extract_draft.jsonl` and `agent/extract_revision.jsonl` logs. Draft and attempted revision are shown separately; `extract total` sums them once. Trial and treatment totals include this aggregate once. An incomplete attempted call leaves full extraction cost unknown.

| Task | Arm | Stage | Status | Input | Cached input | Uncached input | Output | Reasoning output | Nonreasoning output | Total |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 091 | science | extract_draft | completed | 247791 | 206720 | 41071 | 2729 | 75 | 2654 | 250520 |
| 091 | science | extract total | completed | 247791 | 206720 | 41071 | 2729 | 75 | 2654 | 250520 |
| 091 | science | repair | interrupted | unknown | unknown | unknown | unknown | unknown | unknown | unknown |
| 091 | science | trial total | interrupted | unknown | unknown | unknown | unknown | unknown | unknown | unknown |
| 091 | baseline | repair | completed | 212226 | 179840 | 32386 | 2110 | 57 | 2053 | 214336 |
| 091 | baseline | trial total | completed | 212226 | 179840 | 32386 | 2110 | 57 | 2053 | 214336 |
| 058 | baseline | trial total | no receipt | unknown | unknown | unknown | unknown | unknown | unknown | unknown |
| 058 | science | trial total | no receipt | unknown | unknown | unknown | unknown | unknown | unknown | unknown |
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
| 091 | 214336 | 250520 | unknown | unknown | unknown |
| 058 | unknown | unknown | unknown | unknown | unknown |
| 009 | unknown | unknown | unknown | unknown | unknown |
| 114 | unknown | unknown | unknown | unknown | unknown |
| 001 | unknown | unknown | unknown | unknown | unknown |
| All planned tasks | unknown | unknown | unknown | unknown | unknown |

Schedule elapsed seconds (including setup and verification): 297.04.

## Extraction and graph coverage

### Task 091

Handoff status: `usable_graph`; graph artifact: available.

| Stage/phase | Status | Seconds |
| --- | --- | --- |
| extract | completed | 118.74 |
| prepare | ready | 2.94 |
| extract_draft | completed | 114.98 |
| assemble_initial | scientific_objects | 0.82 |

Graph nodes: objects=123, operations=33, links=143, unsupported=172.
Recorded mechanical coverage: inspected_calls=17, scientific_api_calls=0, scientific_call_fraction=0.0, scientific_operations=0, support_operations=17, uninterpreted_calls=16, unsupported_cases=172.

Interpretation delivery: enriched; annotated objects: 9. These are delivery counts, not scientific correctness.

### Task 058

Handoff status: `unknown`; graph artifact: missing.

Extraction timing/status receipt unavailable.

Graph nodes: objects=unknown, operations=unknown, links=unknown, unsupported=unknown.
Recorded mechanical coverage: unknown.

Interpretation delivery: unknown; annotated objects: unknown. These are delivery counts, not scientific correctness.

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
| 058 | baseline | missing | unknown | unknown | unknown | unknown |
| 058 | science | missing | unknown | unknown | unknown | unknown |
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
| implementation_revision | 2da4587e9f9a949eb9916f28c62289a1c4f903cd |
| implementation_dirty | False |
| config_sha256 | ef78ee3f52c10108e28eadf97fcf70e61852d7f4b03883138a5a525000ef4f10 |
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
| 091 | baseline | task-091-baseline/task_091__JfmpBig | docker.io/kevinxulearning/swe-bench-science-environment-python-task-091:v0.1.2@sha256:584de1418e2f75d29b7e9bb725f7effa839f1731fdb450c45476777e4ed328d5 | docker.io/kevinxulearning/swe-bench-science-verifier-python-task-091:v0.1.2@sha256:6de21116ddb0ddafb348136ffa9e07e70c7cb25af6c0d137db73e7ac7673d74f |
| 091 | science | task-091-science/task_091__ef5B5fJ | docker.io/kevinxulearning/swe-bench-science-environment-python-task-091:v0.1.2@sha256:584de1418e2f75d29b7e9bb725f7effa839f1731fdb450c45476777e4ed328d5 | docker.io/kevinxulearning/swe-bench-science-verifier-python-task-091:v0.1.2@sha256:6de21116ddb0ddafb348136ffa9e07e70c7cb25af6c0d137db73e7ac7673d74f |

Recorded development-task overlap: 091, 058, 009, 114, 001; recorded prior hidden-test exposure: 001. These markers are not a claim about other possible exposure.

Independent reconstruction verified 2 recorded trials and 1 recorded task/run pairs. Patch hashes checked: 1; patches missing: 1; patches present without a recorded hash: 0.

This document's quantitative text and tables are generated from durable records. Raw trajectories, patches, verifier receipts and failure diagnostics remain under `runs/workflow-five-v2`. Only receipts beneath this run root are included; earlier development runs are not pooled. Unknowns and incomplete schedules must remain explicit in any downstream claims.
