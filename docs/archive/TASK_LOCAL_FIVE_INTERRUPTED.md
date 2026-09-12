# Paired comparison: results

Planned tasks (configuration order): 091, 058, 009, 114, 001. Recorded attempts: 3/10; planned attempts without a run receipt: 7. Schedule status: `interrupted`.

This is an exploratory comparison, not evidence of a general improvement. Unknown outcomes are not failures or successes; missing cost measurements are not zero. No significance or causal-attribution claim is made.

**The planned comparison is incomplete.** All selected tasks and arms remain listed below; unrun arms are not silently dropped or included as failures in an observed success rate.

Schedule error: KeyboardInterrupt: Received signal 15

Operator-requested stop: User explicitly requested stopping all benchmark runs before fixing the assembly sub-limit.
Active at stop request: 058/baseline during pier. A pre-inference image-pull interruption is not a model repair failure.

## Outcomes for the full planned selection

| Task | Arm | Schedule status | Run status | Hidden-test success | Hidden tests passed/collected | Official reward | Agent seconds |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 091 | science | completed | completed | pass | 3/3 | 1 | 255.88 |
| 091 | baseline | completed | completed | pass | 3/3 | 1 | 100.16 |
| 058 | baseline | interrupted | interrupted | unknown | unknown/unknown | unknown | 48.54 |
| 058 | science | not_run | no receipt | unknown | unknown/unknown | unknown | unknown |
| 009 | science | not_run | no receipt | unknown | unknown/unknown | unknown | unknown |
| 009 | baseline | not_run | no receipt | unknown | unknown/unknown | unknown | unknown |
| 114 | baseline | not_run | no receipt | unknown | unknown/unknown | unknown | unknown |
| 114 | science | not_run | no receipt | unknown | unknown/unknown | unknown | unknown |
| 001 | science | not_run | no receipt | unknown | unknown/unknown | unknown | unknown |
| 001 | baseline | not_run | no receipt | unknown | unknown/unknown | unknown | unknown |

| Arm | Planned | Recorded | Exact pass | Exact fail | Unknown recorded | No receipt |
| --- | --- | --- | --- | --- | --- | --- |
| baseline | 5 | 2 | 1 | 0 | 1 | 3 |
| science | 5 | 1 | 1 | 0 | 0 | 4 |

| Paired outcome | Tasks |
| --- | --- |
| both_success | 1 |
| baseline_only | 0 |
| science_only | 0 |
| both_failure | 0 |
| unknown | 0 |
| missing_baseline | 0 |
| missing_science | 1 |
| neither_arm_recorded | 3 |

Exact hidden-test success and official reward are reported separately. Per-test Fail2Pass/Pass2Pass require matching original-baseline test identities; availability and diagnostics remain in the audited summary.

## Time and token accounting

Agent time includes extraction and handoff where applicable, but excludes image pulls, environment preparation and official verification. Token totals require usage from every recorded agent stage; repair-only usage is not reported as a full science-arm total. Observed totals below cover only the stated measured trials, not unrecorded attempts.

| Arm | Quantity | Observed total | Measured trials | Missing recorded trials |
| --- | --- | --- | --- | --- |
| baseline | duration_seconds | 148.70 | 2 | 0 |
| baseline | input_tokens | 191650 | 1 | 1 |
| baseline | cached_input_tokens | 152320 | 1 | 1 |
| baseline | output_tokens | 1949 | 1 | 1 |
| baseline | over_budget_seconds | 0.00 | 2 | 0 |
| science | duration_seconds | 255.88 | 1 | 0 |
| science | input_tokens | 364225 | 1 | 0 |
| science | cached_input_tokens | 297088 | 1 | 0 |
| science | output_tokens | 5114 | 1 | 0 |
| science | over_budget_seconds | 0.00 | 1 | 0 |

### Raw-event token breakdown by task and stage

Input includes cached input; output includes reasoning. Total = input + output, with neither subset added again. Nonreasoning output = output − reasoning; this is not necessarily visible text. These counts are tokens, not monetary cost. Raw `agent/{extract,repair}.jsonl` completed-turn events are cross-checked against stage receipts. Missing reasoning stays unknown. Incomplete stages have unknown full costs; the earlier receipt totals can contain completed turns from an interrupted stage. Trial totals require every expected stage to be present and measured. CLI diagnostic lines are skipped, as in receipt collection.

| Task | Arm | Stage | Status | Input | Cached input | Uncached input | Output | Reasoning output | Nonreasoning output | Total |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 091 | science | extract | completed | 128606 | 100992 | 27614 | 2735 | 239 | 2496 | 131341 |
| 091 | science | repair | completed | 235619 | 196096 | 39523 | 2379 | 182 | 2197 | 237998 |
| 091 | science | trial total | completed | 364225 | 297088 | 67137 | 5114 | 421 | 4693 | 369339 |
| 091 | baseline | repair | completed | 191650 | 152320 | 39330 | 1949 | 65 | 1884 | 193599 |
| 091 | baseline | trial total | completed | 191650 | 152320 | 39330 | 1949 | 65 | 1884 | 193599 |
| 058 | baseline | repair | interrupted | unknown | unknown | unknown | unknown | unknown | unknown | unknown |
| 058 | baseline | trial total | interrupted | unknown | unknown | unknown | unknown | unknown | unknown | unknown |
| 058 | science | trial total | no receipt | unknown | unknown | unknown | unknown | unknown | unknown | unknown |
| 009 | science | trial total | no receipt | unknown | unknown | unknown | unknown | unknown | unknown | unknown |
| 009 | baseline | trial total | no receipt | unknown | unknown | unknown | unknown | unknown | unknown | unknown |
| 114 | baseline | trial total | no receipt | unknown | unknown | unknown | unknown | unknown | unknown | unknown |
| 114 | science | trial total | no receipt | unknown | unknown | unknown | unknown | unknown | unknown | unknown |
| 001 | science | trial total | no receipt | unknown | unknown | unknown | unknown | unknown | unknown | unknown |
| 001 | baseline | trial total | no receipt | unknown | unknown | unknown | unknown | unknown | unknown | unknown |

Schedule elapsed seconds (including setup and verification): 543.88.

## Extraction and graph coverage

### Task 091

Handoff status: `no_valid_graph`; graph artifact: missing.

| Stage/phase | Status | Seconds |
| --- | --- | --- |
| extract | completed | 123.95 |
| interpret | completed | 111.59 |
| prepare | ready | 1.24 |
| assemble_initial | failed | 12.36 |

Graph nodes: claims=unknown, quantities=unknown, evidence=unknown, observations=unknown.
Recorded mechanical coverage: unknown.

code_grounding: unknown.
alignments: unknown.

### Task 058

Handoff status: `unknown`; graph artifact: missing.

Extraction timing/status receipt unavailable.

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
| 058 | science | missing | unknown | unknown | unknown | unknown |
| 009 | science | missing | unknown | unknown | unknown | unknown |
| 009 | baseline | missing | unknown | unknown | unknown | unknown |
| 114 | baseline | missing | unknown | unknown | unknown | unknown |
| 114 | science | missing | unknown | unknown | unknown | unknown |
| 001 | science | missing | unknown | unknown | unknown | unknown |
| 001 | baseline | missing | unknown | unknown | unknown | unknown |

Docker totals are measured daemon allocation, not proof of per-container effective limits or parity with published benchmark resources. Missing setup receipts leave actual allocation unknown; requested resources alone do not establish feasibility.

## Protocol and provenance

Model: gpt-6-astra/medium; Codex 0.153.4; Pier 0.3.0. Total allowance: 1800 seconds; extraction cap: 360 seconds. Attempts per task/arm: 1; concurrency: 1.

Planned order: 091/science → 091/baseline → 058/baseline → 058/science → 009/science → 009/baseline → 114/baseline → 114/science → 001/science → 001/baseline.

| Record | Value |
| --- | --- |
| implementation_revision | 444ab96360141e6dc57dadf5ea1f8f164a9f353a |
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
| 058 | baseline | task-058-baseline/task_058__WBKBsmo | docker.io/kevinxulearning/swe-bench-science-environment-python-cpp-task-058:v0.1.2@sha256:1b7822c1dbae675f2c32a19ec6cee830f93bd8248e459d3836d962805a3e680b | docker.io/kevinxulearning/swe-bench-science-verifier-python-cpp-task-058:v0.1.2@sha256:9be2d158eb93ffa431399c9240b6115f626f47476bc6327268bdc36c6f981744 |
| 091 | baseline | task-091-baseline/task_091__u7wVZCm | docker.io/kevinxulearning/swe-bench-science-environment-python-task-091:v0.1.2@sha256:584de1418e2f75d29b7e9bb725f7effa839f1731fdb450c45476777e4ed328d5 | docker.io/kevinxulearning/swe-bench-science-verifier-python-task-091:v0.1.2@sha256:6de21116ddb0ddafb348136ffa9e07e70c7cb25af6c0d137db73e7ac7673d74f |
| 091 | science | task-091-science/task_091__RZKBABL | docker.io/kevinxulearning/swe-bench-science-environment-python-task-091:v0.1.2@sha256:584de1418e2f75d29b7e9bb725f7effa839f1731fdb450c45476777e4ed328d5 | docker.io/kevinxulearning/swe-bench-science-verifier-python-task-091:v0.1.2@sha256:6de21116ddb0ddafb348136ffa9e07e70c7cb25af6c0d137db73e7ac7673d74f |

Recorded development-task overlap: 091, 058, 009, 114, 001; recorded prior hidden-test exposure: none. These markers are not a claim about other possible exposure.

Independent reconstruction verified 3 recorded trials and 2 recorded task/run pairs. Patch hashes checked: 2; patches missing: 1; patches present without a recorded hash: 0.

This document's quantitative text and tables are generated from durable records. Raw trajectories, patches, verifier receipts and failure diagnostics remain under `runs/task-local-five-v1`. Only receipts beneath this run root are included; earlier development runs are not pooled. Unknowns and incomplete schedules must remain explicit in any downstream claims.
