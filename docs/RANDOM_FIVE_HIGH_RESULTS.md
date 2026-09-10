# Paired comparison: results

Planned tasks (configuration order): 091, 058, 009, 114, 001. Recorded attempts: 5/10; planned attempts without a run receipt: 5. Schedule status: `interrupted`.

This is an exploratory comparison, not evidence of a general improvement. Unknown outcomes are not failures or successes; missing cost measurements are not zero. No significance or causal-attribution claim is made.

**The planned comparison is incomplete.** All selected tasks and arms remain listed below; unrun arms are not silently dropped or included as failures in an observed success rate.

Schedule error: KeyboardInterrupt: Received signal 15

Operator-requested stop: User requested medium effort and simplified extraction for subsequent initial checks; finish current 058 pair first.
Active at stop request: 009/science during pulling_images. A pre-inference image-pull interruption is not a model repair failure.

## Outcomes for the full planned selection

| Task | Arm | Schedule status | Run status | Exact private | Private passed/collected | Official reward | Agent seconds |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 091 | science | completed | completed | pass | 3/3 | 1 | 315.15 |
| 091 | baseline | completed | completed | pass | 3/3 | 1 | 143.08 |
| 058 | baseline | completed | completed | pass | 9/9 | 1 | 518.65 |
| 058 | science | completed | completed | pass | 9/9 | 1 | 843.82 |
| 009 | science | interrupted | interrupted | unknown | unknown/unknown | unknown | unknown |
| 009 | baseline | not_run | no receipt | unknown | unknown/unknown | unknown | unknown |
| 114 | baseline | not_run | no receipt | unknown | unknown/unknown | unknown | unknown |
| 114 | science | not_run | no receipt | unknown | unknown/unknown | unknown | unknown |
| 001 | science | not_run | no receipt | unknown | unknown/unknown | unknown | unknown |
| 001 | baseline | not_run | no receipt | unknown | unknown/unknown | unknown | unknown |

| Arm | Planned | Recorded | Exact pass | Exact fail | Unknown recorded | No receipt |
| --- | --- | --- | --- | --- | --- | --- |
| baseline | 5 | 2 | 2 | 0 | 0 | 3 |
| science | 5 | 3 | 2 | 0 | 1 | 2 |

| Paired outcome | Tasks |
| --- | --- |
| both_success | 2 |
| baseline_only | 0 |
| science_only | 0 |
| both_failure | 0 |
| unknown | 0 |
| missing_baseline | 1 |
| missing_science | 0 |
| neither_arm_recorded | 2 |

Exact private success and official reward are reported separately. Per-test Fail2Pass/Pass2Pass require matching original-baseline test identities; availability and diagnostics remain in the audited summary.

## Time and token accounting

Agent time includes extraction and handoff where applicable, but excludes image pulls, environment preparation and official verification. Token totals require usage from every recorded agent stage; repair-only usage is not reported as a full science-arm total. Observed totals below cover only the stated measured trials, not unrecorded attempts.

| Arm | Quantity | Observed total | Measured trials | Missing recorded trials |
| --- | --- | --- | --- | --- |
| baseline | duration_seconds | 661.72 | 2 | 0 |
| baseline | input_tokens | 2126129 | 2 | 0 |
| baseline | cached_input_tokens | 1984896 | 2 | 0 |
| baseline | output_tokens | 16389 | 2 | 0 |
| baseline | over_budget_seconds | 0.00 | 2 | 0 |
| science | duration_seconds | 1158.97 | 2 | 1 |
| science | input_tokens | 2353381 | 2 | 1 |
| science | cached_input_tokens | 2157312 | 2 | 1 |
| science | output_tokens | 28253 | 2 | 1 |
| science | over_budget_seconds | 0.00 | 2 | 1 |

Schedule elapsed seconds (including setup and verification): 2529.41.

## Extraction and graph coverage

### Task 091

Handoff status: `usable_graph`; graph artifact: available.

| Stage/phase | Status | Seconds |
| --- | --- | --- |
| extract | completed | 136.46 |
| interpret | completed | 126.99 |
| prepare | ready | 1.14 |
| assemble_initial | usable_graph | 3.74 |
| probes | completed | 1.86 |
| assemble_final | usable_graph | 3.87 |

Graph nodes: claims=3, quantities=7, evidence=16, observations=2.
Recorded mechanical coverage: claims=3, conflicts=0, dimension_resolved=0, expressions=2, lift_supported=0, lift_unknown=3, scale_resolved=0, shape_resolved=0.

code_grounding: unresolved=3.
alignments: unknown=3.

### Task 058

Handoff status: `no_valid_graph`; graph artifact: missing.

| Stage/phase | Status | Seconds |
| --- | --- | --- |
| extract | completed | 136.27 |
| interpret | completed | 135.49 |
| prepare | ready | 1.31 |
| assemble_initial | usable_graph | 0.78 |

Graph nodes: claims=unknown, quantities=unknown, evidence=unknown, observations=unknown.
Recorded mechanical coverage: unknown.

code_grounding: unknown.
alignments: unknown.

### Task 009

Handoff status: `unknown`; graph artifact: missing.

Extraction timing/status receipt unavailable.

Graph nodes: claims=unknown, quantities=unknown, evidence=unknown, observations=unknown.
Recorded mechanical coverage: unknown.

code_grounding: unknown.
alignments: unknown.

### Task 114

Handoff status: `unknown`; graph artifact: missing.

Extraction timing/status receipt unavailable.

Graph nodes: claims=unknown, quantities=unknown, evidence=unknown, observations=unknown.
Recorded mechanical coverage: unknown.

code_grounding: unknown.
alignments: unknown.

### Task 001

Handoff status: `unknown`; graph artifact: missing.

Extraction timing/status receipt unavailable.

Graph nodes: claims=unknown, quantities=unknown, evidence=unknown, observations=unknown.
Recorded mechanical coverage: unknown.

code_grounding: unknown.
alignments: unknown.

Coverage counters measure recoverable representations and supported rules, not scientific correctness. Neither successful extraction nor a passed probe establishes that the supplied guidance caused a repair outcome.

## Measured Docker resources

| Task | Arm | Setup receipt | Docker GiB | Task requested GiB | Docker CPUs | Below requested memory |
| --- | --- | --- | --- | --- | --- | --- |
| 091 | science | available | 3.83 | 8.00 | 4 | True |
| 091 | baseline | available | 3.83 | 8.00 | 4 | True |
| 058 | baseline | available | 3.83 | 8.00 | 4 | True |
| 058 | science | available | 3.83 | 8.00 | 4 | True |
| 009 | science | missing | unknown | unknown | unknown | unknown |
| 009 | baseline | missing | unknown | unknown | unknown | unknown |
| 114 | baseline | missing | unknown | unknown | unknown | unknown |
| 114 | science | missing | unknown | unknown | unknown | unknown |
| 001 | science | missing | unknown | unknown | unknown | unknown |
| 001 | baseline | missing | unknown | unknown | unknown | unknown |

Docker totals are measured daemon allocation, not proof of per-container effective limits or parity with published benchmark resources. Missing setup receipts leave actual allocation unknown; requested resources alone do not establish feasibility.

## Protocol and provenance

Model: gpt-6-astra/high; Codex 0.153.4; Pier 0.3.0. Total allowance: 1800 seconds; extraction cap: 360 seconds. Attempts per task/arm: 1; concurrency: 1.

Planned order: 091/science → 091/baseline → 058/baseline → 058/science → 009/science → 009/baseline → 114/baseline → 114/science → 001/science → 001/baseline.

| Record | Value |
| --- | --- |
| implementation_revision | 6e2427218a37f19b97569e23f0b8007f0f4a6955 |
| implementation_dirty | False |
| config_sha256 | 1e7a0630113ef95970ab7720a5390a65f4c906ac7d1ce069b8c855826448d3f3 |
| selection_sha256 | 409c853fcf71217e5a229024c02c1075f01c7a329361eb2b7e42b5e80578e620 |
| uv_lock_sha256 | c61a78a1c9ba91fe4ebf14ec3f35fd65e9d4e99a567afe06fed77cdac3bc38f4 |
| prompt_sha256 | {'prompts/extract.md': '71cf775c976f3144933f25b27b2b858a9c728683f9ffaccd51acbcfb50a33348', 'prompts/repair.md': '9b9bd47560b889414d5b5b4fcb05c0dd6ba406856a6ce7fdee9c59102115066b'} |
| dataset_revision | d8bdbcb4ecb2b565686382459c815d2b6291fd31 |
| release_commit | 42e7e97915ff7d73436a5d37b5cbe6b77e9c2a00 |
| release_receipt | data/random-five-v1-release.json |
| sampling_manifest | configs/random-five-v1.selection.json |
| sampling_manifest_sha256 | 8318fa6f565300af5673360b179706c00ce69d0291b8788d23aa4f2478a3080e |
| allow_restricted_licenses | False |

| Task | Arm | Trial path | Environment image | Verifier image |
| --- | --- | --- | --- | --- |
| 009 | science | task-009-science/setup-failure | docker.io/kevinxulearning/swe-bench-science-environment-python-task-009:v0.1.2@sha256:f4c314a57e656f4f4b480fa5d4967f476fb36c7aa5eb22e5f95398554d9ec79c | docker.io/kevinxulearning/swe-bench-science-verifier-python-task-009:v0.1.2@sha256:fe483ea0e64c344cc2cce2bd520aadc241558e7a7d2f6f397e18267d5bcbf7bb |
| 058 | baseline | task-058-baseline/task_058__XPkaL4J | docker.io/kevinxulearning/swe-bench-science-environment-python-cpp-task-058:v0.1.2@sha256:1b7822c1dbae675f2c32a19ec6cee830f93bd8248e459d3836d962805a3e680b | docker.io/kevinxulearning/swe-bench-science-verifier-python-cpp-task-058:v0.1.2@sha256:9be2d158eb93ffa431399c9240b6115f626f47476bc6327268bdc36c6f981744 |
| 058 | science | task-058-science/task_058__euvFCm3 | docker.io/kevinxulearning/swe-bench-science-environment-python-cpp-task-058:v0.1.2@sha256:1b7822c1dbae675f2c32a19ec6cee830f93bd8248e459d3836d962805a3e680b | docker.io/kevinxulearning/swe-bench-science-verifier-python-cpp-task-058:v0.1.2@sha256:9be2d158eb93ffa431399c9240b6115f626f47476bc6327268bdc36c6f981744 |
| 091 | baseline | task-091-baseline/task_091__LrKVPML | docker.io/kevinxulearning/swe-bench-science-environment-python-task-091:v0.1.2@sha256:584de1418e2f75d29b7e9bb725f7effa839f1731fdb450c45476777e4ed328d5 | docker.io/kevinxulearning/swe-bench-science-verifier-python-task-091:v0.1.2@sha256:6de21116ddb0ddafb348136ffa9e07e70c7cb25af6c0d137db73e7ac7673d74f |
| 091 | science | task-091-science/task_091__Pf5SuUn | docker.io/kevinxulearning/swe-bench-science-environment-python-task-091:v0.1.2@sha256:584de1418e2f75d29b7e9bb725f7effa839f1731fdb450c45476777e4ed328d5 | docker.io/kevinxulearning/swe-bench-science-verifier-python-task-091:v0.1.2@sha256:6de21116ddb0ddafb348136ffa9e07e70c7cb25af6c0d137db73e7ac7673d74f |

Recorded development-task overlap: none; recorded prior private-test exposure: none. These markers are not a claim about other possible exposure.

Independent reconstruction verified 5 recorded trials and 3 recorded task/run pairs. Patch hashes checked: 4; patches missing: 1; patches present without a recorded hash: 0.

This document's quantitative text and tables are generated from durable records. Raw trajectories, patches, verifier receipts and failure diagnostics remain under `runs/random-five-v1`. Only receipts beneath this run root are included; earlier development runs are not pooled. Unknowns and incomplete schedules must remain explicit in any downstream claims.
