# Scientific representation extraction before Codex repair

Approved for implementation on 2026-09-10. This replaces the exploratory draft. WORK_LOG.md is the canonical live milestone ledger.

## Research question

Does a bounded preparation stage that aligns scientific context with code, lifts relevant operations into scientific concepts, and propagates supported properties improve Codex repair success under an equal total agent time allowance?

The comparison evaluates the complete procedure. It does not isolate the causal contribution of the graph, a fresh session, or any single analysis component.

## Conditions

- Ordinary Codex baseline: GPT-6 Astra/high, 1800 seconds total agent allowance.
- Treatment: same model and harness; extraction cap 360 seconds including helpers, probes, validation and handoff; fresh repair receives the remaining total allowance.
- Pin Codex 0.153.4 and Pier 0.3.0, prompts/configuration, dependencies, exact task IDs and immutable image digests.
- Develop on 002 and 077, one attempt per condition. Full evaluation targets all 119 tasks after throughput review and explicit restricted-license opt-in.
- Use the Codex subscription. Do not silently fall back to API billing.
- Inputs are only allowed task-visible materials. Exclude private verifiers, answers, this research discussion, personal memory and unrelated tools.

## Combined algorithm

1. Codex proposes relevant quantities, scientific relationships, assumptions, representation conventions and source locations, each with explicit/inferred/unresolved status.
2. A deterministic Python AST helper extracts scoped expressions and source evidence. Other languages remain eligible with mechanical coverage limitations recorded.
3. Match ordered scientific and implementation expression graphs using proposed quantity bindings. Report structure/correspondences, not mathematical-equivalence proofs.
4. Lift recognized conversions, weighted reductions, normalizations and linear transformations into candidate scientific operations under stated assumptions.
5. Propagate supported dimensions, scale factors and explicit shapes. Preserve disagreements between intended requirements and buggy code. Public scratch probes can supply additional observations.
6. Save a canonical JSON graph, valid partial checkpoints and a deterministic text handoff, capped at 12 scientific claims and 64 total nodes.

Expressions are structured data and are never evaluated as generated Python. Matching citations are not scientific proof. A baseline failure does not automatically invalidate a scientific requirement. Repair may challenge an inferred constraint with evidence.

## Execution

Use a custom Pier adapter for both conditions with native Codex tools. Prepare images/harness before the clock; include every agent stage, helper and probe inside one monotonic deadline. Private verification receives the same separate allowance in both conditions.

Extraction may run diagnostics/scratch probes but cannot modify candidate source. Repair starts from the original workspace with only the declared handoff. Graphs, credentials and scratch artifacts remain outside the patch root.

At extraction timeout, use the latest valid checkpoint; without one, continue ordinary repair using remaining time and record extraction failure. No dropped tasks, silent retries or extra unbudgeted inference. Stop the process tree at the total deadline and evaluate the collected patch through the official verifier.

## Verification and evaluation

Test parsing, scope/branch ambiguity, evidence paths/hashes, bindings, unsupported operators/languages, dimension/scale/shape rules, floating-point limitations, invalid checkpoints, timeouts/background processes, fresh context and patch isolation. Verify container permissions and subscription integration before live development runs.

Preserve every pilot outcome. Generate official reward, exact private success, paired task outcomes, token usage, durations, extraction coverage/failures and infrastructure summaries programmatically. Compute Fail2Pass/Pass2Pass only with matching per-test baseline and candidate statuses.

Task 002 private failures were previously inspected. Disclose development exposure and separately identify untouched evaluation tasks. Final verification is a clean install/test run and independently recomputed summaries, with every outcome linked to its configuration, graph, patch and verifier receipt.

Full-benchmark launch remains a subsequent scientific/budget checkpoint.

## Literature basis

AutoMATES/SKEMA motivate text-equation-code alignment; semantic enrichment of dataflow graphs motivates scientific operation mappings; Phys/CamFort motivate semantic anchors plus propagation. SpecRover, DSrepair and SIGA are close precedents. No claim of first-ever scientific-context extraction or guaranteed understanding is made.
