# Scientific bug repair with a prepared code-derived evidence graph (DRAFT, 4-page target)

Rajarshi Ghoshal — TU Graz PhD research task. Repository: <TO-PUSH-URL> (<N> commits at freeze).
Evaluated model: DeepSeek V4.1 Flash (reasoning: high) for all reported pairs; an earlier
GLM-5.3-Flash (low) attempt was stopped by provider throttling and is disclosed separately.
All runs: single laptop (8 cores, Docker), matched allowances per arm, official verifier.

## 1. Problem and question

SWE-bench Science tasks ask a model to repair scientific code given a public reproducer and
task statement. We study whether a *prepared scientific evidence graph* — built by code,
before any model call — helps a repair agent form a correct scientific understanding and
repair more often under the same allowance.

Narrow, falsifiable question: does interactive access to a connected, execution-derived
representation of the task's science (workflow → implementation computations → dependencies,
conditions and violated constraints, with citable evidence) improve repair by a fixed model
with the same tools, time and instructions — against the same model without it?

## 2. The representation

Construction runs at preparation, no model calls: (1) the public reproducer is executed under
an observer, yielding the executed workflow and script-declared predicates; (2) a static
evidence packet is extracted from public sources (multilingual frontends: Python, C, C++,
Fortran, MATLAB, Cython; Joern on demand, host-side, concurrency-bounded); (3)
execution-derived constraint loci are merged into the object graph; (4) a connected graph
joins workflow, implementation computations, dependency edges and violated-constraint
findings. Represented task-workflow computations are never evicted by the fallback budget;
the overview is paginated. Evidence selection is result/dependency-first: statements that
produce or guard the returned scientific quantity outrank getters, signatures and imports;
bare early exits do not displace model-building effects; partial views are flagged
(`partial: true`) and expand on inspection.

Classification contract: a build/runner failure is recorded as reproduction status, never a
scientific violation; only the reproducer's own failed check yields a constraint finding.
Delivery contract: the graph is served through queries, never force-fed. Node inspection
shows registered source excerpts and entity references; `science_note` (optional, revisable)
rejects citations to content never displayed and prepared evidence whose file changed on
disk; inspecting a partially-grounded node compiles its location on demand and persists the
expansion. Cross-language call edges recovered from workflow references are labelled
`candidate_call` with basis `public_workflow_reference_not_observed_dispatch` — candidate
structure, never claimed dispatch.

## 3. Evaluation

### 3.1 Extractor validation (zero model calls)

Frozen-split preparation succeeded on all 30 development tasks: connected graphs, every
violated locus preserved, scripted in-container self-checks passed at the frozen validation
revision (receipts: `results/computation-coverage.json`, `runs/context-recheck-v10`). A
content audit of ten tasks against immutable pre-repair snapshots (independent reviewer
model, read-only; `results/context-recheck-v10-audit.json`) found the current selection
improved on the initial snapshots in 8/10 (0 regressed); central computations fully visible
on 016/028/073; producer/accumulator/guard statements retained under tight budgets; all
snapshot hashes verified. Known boundary: a fixed 24-file scan ceiling drops some central
files on large repositories (058 physics kernels, 076 task module) — pre-existing, identical
in all iterations, reported as a limitation rather than tuned per task.

### 3.2 Paired repair evidence (official verifier, matched allowance)

Design: both arms receive identical tools, budget, base instructions; the science arm
additionally receives the graph tool. One attempt per arm per task; 1800 s work each;
official verifier decides. Provider transport: DeepSeek V4.1 Flash/high, five retries.

- Single paired check (task 009, development-exposed): baseline 1/1, science 1/1 (reward
  1.0 both); science used less work time (342 s vs 489 s) and fewer output tokens
  (43.6 K vs 74.5 K); zero provider retries. n=1; no causal claim.
- [TO-FILL-40WAY] Thirty-task paired development workload (60 attempts, 40-concurrent):
  per-task outcomes, aggregate success rates both arms, token/work/time accounting,
  retry events. Receipts: `runs/deepseek-development-e2e-40-v1`.
- [TO-FILL-EVAL] Locked-evaluation outcome if reached, or the predeclared-subset framing
  with full disclosure that locked tasks were not run.

Earlier gated design (forced interpretation before inspection) failed and was replaced;
its preserved trajectories remain in the repository as negative evidence.

## 4. What the evidence supports

Supported: the representation is buildable and servable as specified, at zero model cost,
with enforced evidence-citation integrity across languages; selection defects found by
adversarial review (annotation rebinding, early-exit ranking, caller-column ambiguity,
analyzer budget arithmetic) were fixed and regression-tested; independent recomputation
reproduces every reported number from receipts.
Not supported (until the paired workload lands): that the graph *improves repair* at scale.
Prior single pairs are consistent with the hypothesis and prove nothing.

Limitations: development-task exposure of the frozen split is disclosed; single model
family per run; laptop-scale concurrency (one 40-way run sustained, provider stability
under sustained load reported with the workload); 24-file scan ceiling on large repositories;
relevance on compiled languages without execution evidence remains unsolved; partial views
acknowledge truncation rather than hide it.

## 5. Related work and lineage

TraceScore/ABLoTS (Niu et al., MSR 2023) verified that connecting a task to code through
intermediate traceability artifacts beats flat text similarity for bug localization; our
task→workflow→computation→source chain follows that principle, carried from file-level
ranking to role-labelled scientific computations consumed by a repair agent. The same
replication's leakage findings (fix-date cut-offs, undocumented subset filtering) shape our
protocol: predeclared split, locked tasks, disclosed exposure, receipts-only numbers.
TVR (Niu et al.) contributes the role-narrowed correspondence check — which documented
scientific role a computation implements, not whether passages sound alike. Pan & Niu's
coverage-guided minimization inspires coverage-aware evidence selection (distinct relevant
roles before redundant repeats). RAT (Niu et al., ICSE 2023) is the closest traceability-for-
localization ancestor. SKEMA/GroMEt and AutoMATES precede code-derived scientific knowledge
extraction (variable/relationship graphs); we differ in serving a connected task-level view
to a repair agent under a matched allowance. SemAgent-style code-plus-LLM explanation is not
itself our contribution; ours is the pre-repair scientific abstraction and its measured
benefit under an unchanged repair harness.

## References (page 5)

[1] SWE-bench Science: benchmark paper v2, arXiv:2608.19799.
[2] OpenMOSS/SWE-bench-Science official code and dataset.
[3] F. Niu et al. The ABLoTS Approach for Bug Localization: is it replicable and
    generalizable? MSR 2023. DOI 10.1109/MSR59073.2023.00083.
[4] F. Niu et al. TVR: automotive requirement traceability validation and recovery through
    RAG. arXiv:2504.15427.
[5] Pan, F. Niu et al. Requirements coverage-guided minimization. arXiv:2505.20004.
[6] F. Niu et al. RAT: a refactoring-aware traceability model for bug localization. ICSE 2023.
[7] SKEMA/GroMEt; AutoMATES: prior scientific code knowledge extraction.
[8] DeepSeek API; Z.ai GLM API documentation (provider disclosure).
