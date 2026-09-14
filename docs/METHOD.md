# Task-specific scientific context for repair

## Research question and current status

Does a compact task-specific scientific representation, grounded in public code and documentation,
help an otherwise unchanged agent repair scientific software under a matched total allowance?
Rajarshi owns this question and the scientific choices. Better repair is not established.

The intended context explains the computation's purpose, the relevant quantities or structures,
their relationships, and the conditions/conventions that matter to this task. It is not an
inventory of suspicious lines or a paraphrase of the reproducer. Scientific meaning can come
from LLM interpretation; the useful claim is about the resulting grounded representation,
not that static analysis independently understands physics.

This file replaces stale claims about the mathematical representation removed at 6624ac6.
That implementation and its historical results remain in Git and preserved run artifacts.
They are not current functionality.

## Focused literature check — 14 September 2026

The following are mechanisms to borrow, not evidence that our method works.

- **Niu et al., TVR, v1, §§2.2–3:** narrow traceability to the specific message/signal and
  condition a requirement covers. Retrieve labelled requirement-pair examples, then validate
  that correspondence. The lesson for us is to ask which documented scientific role a
  computation implements, not whether two passages sound related. Their automotive templates
  and private labelled pairs do not transfer automatically.
  [Paper](https://arxiv.org/html/2504.15427v1),
  [official prompts](https://github.com/feifeiniu-se/TVR/blob/main/Prompts.md).

- **Pan, Niu et al., requirements coverage-guided minimization, v1, §§2–3:** select a
  fixed-size test subset while preserving supplied requirement coverage and reducing redundancy.
  Borrow coverage-aware selection: retain evidence for distinct task-relevant roles and conditions
  before more examples of an already-covered role. Their requirement mappings are given;
  our mappings must be recovered. Their guarantee does not transfer to our selected context.
  [Paper](https://arxiv.org/html/2505.20004v1).

- **AutoMATES, v1, §§3–6:** connect variables and functional relationships to definitions
  from code comments, equations and text; use shared variable identities and the paths connecting
  them to compare models. This is much closer to the intended compactness than file grouping.
  The paper reports a Fortran subset and initial results; its richly enriched opening example
  is explicitly hand-crafted/aspirational.
  [Paper](https://arxiv.org/html/2001.07295v1).

- **SKEMA/GroMEt:** function definitions are stored separately from invocation bindings, ports
  and wires. Its structural alignment uses seeded graph matching on operator-labelled graphs;
  candidate correspondences are not scientific or algebraic equality. The inspected equation–code
  path seeds from names; definition-based matching exists in another path. Do not import the
  whole platform or introduce this extra matcher until we have a concrete alignment input.
  Official source inspected at fe8f41f704e8802a6d1d30cc7107062d338489b0:
  [function definitions](https://github.com/ml4ai/skema/blob/fe8f41f704e8802a6d1d30cc7107062d338489b0/skema/gromet/fn/gromet_box_function.py),
  [alignment](https://github.com/ml4ai/skema/blob/fe8f41f704e8802a6d1d30cc7107062d338489b0/skema/isa/lib.py).

- **SemAgent, v1, §4.2:** already abstracts issue intent, constructs semantic execution flows,
  and maps their steps to code using an LLM, then refines an existing patch. Its inspected
  implementation is Python/single-file, and additional semantic edits sometimes hurt.
  Therefore “code structure plus LLM explanation” is not itself a new contribution.
  Our possible distinction is the pre-repair scientific abstraction and its measured benefit
  under an unchanged repair harness—not a new multi-agent repair workflow.
  [Paper](https://arxiv.org/html/2506.16650v1).

- **Variable Extraction for Model Recovery, v1:** evaluates extracting names, descriptions and
  values from scientific text, including a hybrid where rule-derived candidates aid an LLM.
  Results are imperfect and gains depend on the model. Borrow explicit definition/value
  correspondences with textual evidence, not an assumption that one model call understands
  everything. Its dataset is scientific text, not repository repair.
  [Paper](https://arxiv.org/html/2411.14569v1).

- **GROUNDING.md:** proposes field-scoped, community-governed scientific constraints and
  convention parameters for coding agents. This closely relates to Rajarshi's manually
  authored project guidance, but does not solve automatic task-level extraction or establish
  our repair effect. This observation is based on the publisher's abstract, not a full-paper audit.
  [NIST publication record](https://www.nist.gov/publications/agentic-ai-assisted-coding-offers-unique-opportunity-instill-epistemic-grounding-during).

## Implemented pipeline; scientific quality remains to be evaluated

1. **Recover the task's computational core.** Start from public task references and workflow
   entry/output points. Retain the relevant implementation computations, operand relationships
   and controlling conditions using the existing analyzers. An available source file is not
   automatically a relevant computation. External calls remain interfaces unless their bodies
   are the repair target.

2. **Connect scientific definitions to that core.** Present the relevant definitions,
   parameter/return documentation and scientific passages beside the code-owned relationships.
   The LLM explains what the quantities and transformations mean and identifies the supporting
   passages. Keep intended behaviour, observed execution and interpretive assumptions distinct.
   An existing object ID proves an anchor exists; it does not prove the explanation is true.

3. **Compact by shared identity and retained distinctions.** A known function definition can be
   represented once with separate call bindings. Repeated references to the same documented
   quantity can share its definition while retaining different uses. Do not merge quantities
   just because their names or embeddings are similar. Keep conditions, operand roles, units,
   coordinate frames and normalization attached to the relationship they qualify.
   Missing identities stay separate rather than becoming invented equivalences.

   The implemented sharing includes ordered source-expression templates with distinct bindings.
   Operators, indices, coefficients, updates and conditions remain per source occurrence. This
   identifies common computational structure, not equality of values or scientific concepts.

4. **Deliver one small connected working model.** Explain the task objective and the relevant
   input → computation → output relationships with scientific interpretations and source pointers.
   The durable artifact retains details for targeted lookup. Do not force repair to mine a
   whole-repository JSON graph. Render the retained relationships, not merely the first eight
   individually annotated objects.

For the user's clique-counting example, the core would describe what is counted, how work is
partitioned and combined, and any documented correctness/performance requirements. Network
contention is a diagnosis only if supported by evidence. A target such as x/N + c remains a
stated performance model with assumptions, not a universal scientific law.

This is an adaptation of existing ideas to a particular repair question. Novelty and usefulness
must be established through the actual representation and comparison; neither is assumed.

## What currently exists

- Public-source readers, Python/native syntax backends, workflow/task-reference retrieval,
  code objects and candidate relationships, execution observations and an anchored LLM schema.
- Joern now exports selected enclosing-method ASTs and direct boundary facts, using its own
  dataflow/control-flow overlays. The query reads the CPG without persistence and visits incident
  edges rather than copying every edge. Parsing/loading still scales with the staged source graph;
  export budgets are not a bound on the analyzer's total working memory.
- One-hop local document links now enter scientific-mode selection. Exact local Python imports
  can survive discovery limits. Both retrievers' references now affect file selection/allocation.
  These changes improve source delivery; per-file limits can still truncate computations.
- The input retains structured argument/branch roles and summarizes ambiguous boundary dispatch
  as alternative target sets with counts and artifact lookups. It does not turn hundreds of static
  candidates into hundreds of presumed executions or choose an arbitrary target. All candidates
  remain in the selected analysis artifact. Duplicate code text and artificial source locations
  on edge records were removed. Whole-method omissions remain explicit when analyzer export limits
  bind. The raw evidence is no longer pruned by the interpreter's transport allowance.
- A source-level projection replaces the low-level graph dump. Task regions and explicit
  definition/guard dependencies select statements; parser-backed templates share ordered syntax
  while preserving separate bindings. Large tables become data records, not thousands of operations.
  One readable input and one repair guide are views of the same structured representation.
- The 2.0 interpreter returns task purpose and selected computation meanings, quantity meanings,
  conventions and assumptions. Claims cite supplied source IDs. Code joins these interpretations
  to recorded member/boundary entities and relationships; it does not accept LLM-authored edges.
- The connected model is delivered as scientific-model.json. Its guide presents the scientific
  explanation with selected source expressions, references and code predicates, preserving a displayed computation's
  conditions and assumptions. The real collection/controller path delivers it once. The deleted
  SymPy/computation layer has not been restored. See [the current contract](OBJECT_ENRICHMENT.md).

The repair model, tools and configured allowances remain unchanged. No new paid experiment,
compiler-IR pipeline, API-rule catalogue or platform dependency was introduced by this checkpoint.
The context format/prompt is a method revision. Host and guest now both use frozen code, and missing
scientific context cannot silently fall back to an unassisted repair labelled as science.

Offline receipts: [source selection](../results/source-selection-review-2026-09-14.json) and
[selected analyzer export](../results/selected-export-review-2026-09-14.json). The latter checks
two preserved real-task CPGs and existing Python/C++/JavaScript fixtures. Task 091's selected
from_cube computation reaches the assembled input; other method omissions remain in the receipt.
Task 058 replays its old, workflow-heavy selection, not newly recovered OpenMC science. These
checks establish source/relationship delivery, not scientific correctness or model-provider fit.
The [connected-model receipt](../results/connected-science-review-2026-09-14.json) additionally records
compilation of all five archived development inputs and a source-grounded rendering fixture for 091.
The fixture's interpretation is manually supplied, not an automatic extraction result.

The subsequent live five-task check at50000be delivered zero usable models: four responses were
rejected by the hidden purpose-length limit and091 exhausted reasoning output. Its very large
inputs and unsupported058 diagnosis motivated this source-level revision. These are implementation
failures, not evidence against the research hypothesis. Old annotation fallback, renderer, probe-first
replay scripts and unused SymPy dependencies are now removed; historical run data is preserved.

## Verification required before another live run

First establish that source selection retains the actual scientific computations and their
documented conventions on development cases. Preserve contrary cases: identical vocabulary
with different conditions, repeated calls with different bindings, and incidental numeric code.
Inspect the assembled model input and repair guide, not just intermediate graphs.

Then verify the bounded analyzer-to-context path with existing real source artifacts and an
independent reviewer. Synthetic annotations can test plumbing, not scientific interpretation.
A separately approved live extraction must show accurate, useful scientific content before
another repair comparison. Paired verifier outcomes, total tokens and time remain the eventual
repair measures. Broken delivery is not a clean negative test of the research question.

Current milestone status and receipts are recorded only in [WORK_LOG.md](../WORK_LOG.md).
