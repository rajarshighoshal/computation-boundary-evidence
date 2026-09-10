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

1. Code builds a bounded source index and document catalog while Codex reads the task/scientific context. Other languages remain eligible with mechanical coverage limitations recorded.
2. Codex saves compact annotations: a small set of relevant quantities, scientific relationships, assumptions and source/implementation references, each with explicit/inferred/unresolved status. Code resolves references and supplies actual expressions, source quotes and hashes; the LLM does not assemble the final graph.
3. Match ordered scientific and implementation expression graphs using proposed quantity bindings. Report structure/correspondences, not mathematical-equivalence proofs.
4. Lift recognized conversions, weighted reductions, normalizations and linear transformations into candidate scientific operations under stated assumptions.
5. Propagate supported dimensions, scale factors and explicit shapes. Preserve disagreements between intended requirements and buggy code. Code runs declared independent Python probes under shared deadlines and adds actual execution/output receipts, without equating exit zero with scientific proof.
6. Code saves a canonical JSON graph and deterministic handoff. Compact annotations are capped at five claims, twelve quantities and two probes; the existing internal graph bound remains. The LLM returns only the annotation filename, not a duplicate graph. No open-ended refinement loop is added.

Expressions are structured data and are never evaluated as generated Python. Matching citations are not scientific proof. A baseline failure does not automatically invalidate a scientific requirement. Repair may challenge an inferred constraint with evidence.

## Execution

Use upstream Pier Codex execution for both conditions, with a thin adapter for extraction and handoff. Per Rajarshi's explicit simplification request, Docker supplies isolation; no custom nested sandbox or process supervisor is added. Prepare images/harness before the clock; include every agent stage, helper and probe inside one monotonic deadline. Private verification receives the same separate allowance in both conditions.

Extraction may run diagnostics/scratch probes on its disposable copy. It is instructed not to edit source; detected source changes invalidate its handoff. It cannot modify the separate repair candidate. Repair starts from the original workspace with only the declared handoff. Graphs, temporary credentials and scratch artifacts remain outside the patch root. Standard container mode does not hide credentials from commands inside that container.

At extraction timeout, use the latest valid code-assembled checkpoint; without one, continue ordinary repair using remaining time and record extraction failure. The interpretation sub-deadline is before the probe/assembly sub-deadline, leaving an explicit collection/shutdown reserve. Finish early when sufficient annotations are saved. No dropped tasks, silent model retries or extra unbudgeted inference. Use GNU timeout for normal foreground groups and bounded Pier lifecycle calls; do not claim exhaustive detached-child supervision. Evaluate the collected patch through the official verifier.

The implemented phase and annotation contracts are in `docs/EXTRACTION_V2.md`. The previous paired pilot used the earlier full-graph extraction workflow; the new revision has separate extraction-only verification, not new repair-success results.

## Verification and evaluation

Test parsing, scope/branch ambiguity, evidence paths/hashes, bindings, unsupported operators/languages, dimension/scale/shape rules, floating-point limitations, invalid checkpoints, time budgets, upstream launch/auth reuse, fresh context and patch isolation. Verify public scientific execution through Codex before live development runs.

Preserve every pilot outcome. Generate official reward, exact private success, paired task outcomes, token usage, durations, extraction coverage/failures and infrastructure summaries programmatically. Compute Fail2Pass/Pass2Pass only with matching per-test baseline and candidate statuses.

Task 002 private failures were previously inspected. Disclose development exposure and separately identify untouched evaluation tasks. Final verification is a clean install/test run and independently recomputed summaries, with every outcome linked to its configuration, graph, patch and verifier receipt.

Full-benchmark launch remains a subsequent scientific/budget checkpoint.

## Literature basis

AutoMATES/SKEMA motivate text-equation-code alignment; semantic enrichment of dataflow graphs motivates scientific operation mappings; Phys/CamFort motivate semantic anchors plus propagation. SpecRover, DSrepair and SIGA are close precedents. No claim of first-ever scientific-context extraction or guaranteed understanding is made.
