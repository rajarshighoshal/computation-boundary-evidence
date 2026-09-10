# Paired comparison: results

Planned tasks (configuration order): 009, 114, 001. Recorded attempts: 3/6; planned attempts without a run receipt: 3. Schedule status: `runner_failure`.

This is an exploratory comparison, not evidence of a general improvement. Unknown outcomes are not failures or successes; missing cost measurements are not zero. No significance or causal-attribution claim is made.

**The planned comparison is incomplete.** All selected tasks and arms remain listed below; unrun arms are not silently dropped or included as failures in an observed success rate.

Schedule error: RuntimeError: Runner failed; retained runs/random-five-medium-v1/task-114-baseline-runner.log. Remaining schedule has not been executed.

## Outcomes for the full planned selection

| Task | Arm | Schedule status | Run status | Hidden-test success | Hidden tests passed/collected | Official reward | Agent seconds |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 009 | science | completed | completed | pass | 9/9 | 1 | 550.57 |
| 009 | baseline | completed | completed | pass | 9/9 | 1 | 534.28 |
| 114 | baseline | infrastructure_failure | infrastructure_failure | unknown | unknown/unknown | unknown | 15.46 |
| 114 | science | not_run | no receipt | unknown | unknown/unknown | unknown | unknown |
| 001 | science | not_run | no receipt | unknown | unknown/unknown | unknown | unknown |
| 001 | baseline | not_run | no receipt | unknown | unknown/unknown | unknown | unknown |

| Arm | Planned | Recorded | Exact pass | Exact fail | Unknown recorded | No receipt |
| --- | --- | --- | --- | --- | --- | --- |
| baseline | 3 | 2 | 1 | 0 | 1 | 1 |
| science | 3 | 1 | 1 | 0 | 0 | 2 |

| Paired outcome | Tasks |
| --- | --- |
| both_success | 1 |
| baseline_only | 0 |
| science_only | 0 |
| both_failure | 0 |
| unknown | 0 |
| missing_baseline | 0 |
| missing_science | 1 |
| neither_arm_recorded | 1 |

Exact hidden-test success and official reward are reported separately. Per-test Fail2Pass/Pass2Pass require matching original-baseline test identities; availability and diagnostics remain in the audited summary.

## Time and token accounting

Agent time includes extraction and handoff where applicable, but excludes image pulls, environment preparation and official verification. Token totals require usage from every recorded agent stage; repair-only usage is not reported as a full science-arm total. Observed totals below cover only the stated measured trials, not unrecorded attempts.

| Arm | Quantity | Observed total | Measured trials | Missing recorded trials |
| --- | --- | --- | --- | --- |
| baseline | duration_seconds | 549.74 | 2 | 0 |
| baseline | input_tokens | 527301 | 1 | 1 |
| baseline | cached_input_tokens | 474112 | 1 | 1 |
| baseline | output_tokens | 15049 | 1 | 1 |
| baseline | over_budget_seconds | 0.00 | 2 | 0 |
| science | duration_seconds | 550.57 | 1 | 0 |
| science | input_tokens | 628986 | 1 | 0 |
| science | cached_input_tokens | 556160 | 1 | 0 |
| science | output_tokens | 15059 | 1 | 0 |
| science | over_budget_seconds | 0.00 | 1 | 0 |

### Raw-event token breakdown by task and stage

Input includes cached input; output includes reasoning. Total = input + output, with neither subset added again. Nonreasoning output = output − reasoning; this is not necessarily visible text. These counts are tokens, not monetary cost. Raw `agent/{extract,repair}.jsonl` completed-turn events are cross-checked against stage receipts. Missing reasoning stays unknown. Incomplete stages have unknown full costs; the earlier receipt totals can contain completed turns from an interrupted stage. Trial totals require every expected stage to be present and measured. CLI diagnostic lines are skipped, as in receipt collection.

| Task | Arm | Stage | Status | Input | Cached input | Uncached input | Output | Reasoning output | Nonreasoning output | Total |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 009 | science | extract | completed | 168989 | 137088 | 31901 | 2436 | 221 | 2215 | 171425 |
| 009 | science | repair | completed | 459997 | 419072 | 40925 | 12623 | 4351 | 8272 | 472620 |
| 009 | science | trial total | completed | 628986 | 556160 | 72826 | 15059 | 4572 | 10487 | 644045 |
| 009 | baseline | repair | completed | 527301 | 474112 | 53189 | 15049 | 5956 | 9093 | 542350 |
| 009 | baseline | trial total | completed | 527301 | 474112 | 53189 | 15049 | 5956 | 9093 | 542350 |
| 114 | baseline | repair | failed | unknown | unknown | unknown | unknown | unknown | unknown | unknown |
| 114 | baseline | trial total | infrastructure_failure | unknown | unknown | unknown | unknown | unknown | unknown | unknown |
| 114 | science | trial total | no receipt | unknown | unknown | unknown | unknown | unknown | unknown | unknown |
| 001 | science | trial total | no receipt | unknown | unknown | unknown | unknown | unknown | unknown | unknown |
| 001 | baseline | trial total | no receipt | unknown | unknown | unknown | unknown | unknown | unknown | unknown |

Schedule elapsed seconds (including setup and verification): 1300.56.

## Extraction and graph coverage

### Task 009

Handoff status: `usable_graph`; graph artifact: available.

| Stage/phase | Status | Seconds |
| --- | --- | --- |
| extract | completed | 102.35 |
| interpret | completed | 100.90 |
| prepare | ready | 1.44 |
| assemble_initial | usable_graph | 1.44 |

Graph nodes: claims=3, quantities=6, evidence=25, observations=0.
Recorded mechanical coverage: claims=3, conflicts=0, dimension_resolved=0, expressions=2, lift_supported=0, lift_unknown=3, scale_resolved=0, shape_resolved=0.

code_grounding: source_matched=1, unresolved=2.
alignments: unknown=3.

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
| 009 | science | available | 3.83 | 8.00 | 4 | True |
| 009 | baseline | available | 3.83 | 8.00 | 4 | True |
| 114 | baseline | available | 3.83 | 8.00 | 4 | True |
| 114 | science | missing | unknown | unknown | unknown | unknown |
| 001 | science | missing | unknown | unknown | unknown | unknown |
| 001 | baseline | missing | unknown | unknown | unknown | unknown |

Docker totals are measured daemon allocation, not proof of per-container effective limits or parity with published benchmark resources. Missing setup receipts leave actual allocation unknown; requested resources alone do not establish feasibility.

## Protocol and provenance

Model: gpt-6-astra/medium; Codex 0.153.4; Pier 0.3.0. Total allowance: 1800 seconds; extraction cap: 360 seconds. Attempts per task/arm: 1; concurrency: 1.

Planned order: 009/science → 009/baseline → 114/baseline → 114/science → 001/science → 001/baseline.

| Record | Value |
| --- | --- |
| implementation_revision | 826f347d8b7425f932207969db65ce655e9842d4 |
| implementation_dirty | False |
| config_sha256 | 620180ddf85e36edece8be3d0b7227f65326476d8ae584105ec84bf43cadad48 |
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
| 009 | baseline | task-009-baseline/task_009__NTZLvQJ | docker.io/kevinxulearning/swe-bench-science-environment-python-task-009:v0.1.2@sha256:f4c314a57e656f4f4b480fa5d4967f476fb36c7aa5eb22e5f95398554d9ec79c | docker.io/kevinxulearning/swe-bench-science-verifier-python-task-009:v0.1.2@sha256:fe483ea0e64c344cc2cce2bd520aadc241558e7a7d2f6f397e18267d5bcbf7bb |
| 009 | science | task-009-science/task_009__hedEtB2 | docker.io/kevinxulearning/swe-bench-science-environment-python-task-009:v0.1.2@sha256:f4c314a57e656f4f4b480fa5d4967f476fb36c7aa5eb22e5f95398554d9ec79c | docker.io/kevinxulearning/swe-bench-science-verifier-python-task-009:v0.1.2@sha256:fe483ea0e64c344cc2cce2bd520aadc241558e7a7d2f6f397e18267d5bcbf7bb |
| 114 | baseline | task-114-baseline/task_114__aZ4unEJ | docker.io/kevinxulearning/swe-bench-science-environment-python-task-114:v0.1.2@sha256:68c032f628b1aad6432f5bc030537d016dc697778ac57ebfd54595df6b23ab3c | docker.io/kevinxulearning/swe-bench-science-verifier-python-task-114:v0.1.2@sha256:0cfbc99c9056587cebcd3647a2edbfe8550c65d58ba2fbabc8b4e0a242bd24c7 |

Recorded development-task overlap: none; recorded prior hidden-test exposure: none. These markers are not a claim about other possible exposure.

Independent reconstruction verified 3 recorded trials and 2 recorded task/run pairs. Patch hashes checked: 2; patches missing: 1; patches present without a recorded hash: 0.

This document's quantitative text and tables are generated from durable records. Raw trajectories, patches, verifier receipts and failure diagnostics remain under `runs/random-five-medium-v1`. Only receipts beneath this run root are included; earlier development runs are not pooled. Unknowns and incomplete schedules must remain explicit in any downstream claims.
