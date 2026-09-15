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

- **Niu et al., ABLoTS replication (MSR 2023), DOI 10.1109/MSR59073.2023.00083:** two debts.
  Design inspiration: TraceScore's verified thesis — connecting a new task to code through
  intermediate traceability artifacts (their linked resolved/non-bug reports and commits; our
  observed public workflow, executed callees and public documents) localizes relevant code
  better than flat text similarity. Our task→workflow→computation→source chain follows that
  principle, carried from file-level ranking to role-labelled scientific computations consumed
  by a repair agent. (TVR separately contributes the role-narrowed correspondence check.)
  Methodological alignment: the replication showed headline bug-localization results collapsing
  under a correct protocol — a reused component cut off at the bug's fix date, leaking fix
  commits into scored evidence, plus undocumented evaluation-subset filtering. Accordingly we
  predeclare the split (configs/interactive-science.split.json) before outcomes, keep locked
  tasks separate from development, disclose prior exposure, and generate every reported number
  from receipts via scripts/recompute_results.py rather than from selected subsets.

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

## Current method: interactive scientific understanding

Preparation indexes public files and supplies a small task map. It does not run the reproducer,
build the project, call an interpretation model, or analyze the whole repository. One continuous
repair agent constructs and uses its scientific working model through three tool actions:

1. `find` discovers scientific terms, symbols and source locations across public text, without a
   language whitelist. `inspect` returns targeted source, definitions or computational relationships.
   Queries can be expanded rather than replaced by a whole-graph prompt.
2. Existing parsers supply quantities, ordered source-expression templates, separate call/operand
   bindings and controlling conditions. Joern runs on demand for an installed matching frontend.
   Its selected method AST and data/control-flow facts enter the same representation. External
   dispatch candidates remain candidates; library implementations are not recursively expanded.
3. The agent interprets those relationships using source and public definitions. `record_model`
   saves the scientific object/goal, governing relationships, code correspondence, expected change
   and behaviour to preserve. Claims cite inspected sources; unresolved questions remain explicit.
   A valid record unlocks ordinary repair tools in the same conversation and task container.
4. The agent repairs, checks the result and can query evidence or revise the model. All preparation,
   queries, reasoning and repair share the same total allowance as the ordinary baseline.

Compactness comes from shared expression structure and source identities, with distinct bindings,
indices, coefficients, evaluation order and conditions retained. Paging controls presentation;
raw evidence remains retrievable. Similar names or observed statistics never establish equality.
The working model is a source-linked interpretation, not a proven scientific specification.
Reference validation does not judge the truth of its scientific claims.

### Language support

The common representation and query interface are language-independent; analysis depth is not.
Python uses its AST, and C/C++, Fortran, MATLAB and Cython use the existing native frontends.
Joern adds structural analysis for supported installed frontends, including languages beyond
that local parser set. Other readable source remains discoverable and inspectable as source,
with unsupported structural analysis recorded explicitly. This is not full dataflow coverage
for every language. Joern's capabilities are described in its [official documentation](https://docs.joern.io/).

For the clique-counting example, a useful model would state what is counted, how work is partitioned
and combined, and documented correctness/performance requirements. Network contention needs evidence;
the target x/N + c is a stated performance model with assumptions, not a universal law.

### Comparison and checks

The ordinary baseline has no added model-building gate. This comparison tests the complete added
workflow, not the isolated effect of its representation or planning requirement. The split and
approved five-task pilot are fixed in [RESEARCH_PLAN.md](../RESEARCH_PLAN.md).

Unit tests and no-model checks establish source/relationship delivery, paging, saved-model identity
and tool ordering. Real repair trials must establish scientific correctness/usefulness and actual
use. Inspect the pre-edit models and trajectories before interpreting paired verifier outcomes,
total tokens and runtime. Broken delivery is not a clean negative test of the research question.

The retired separate-interpreter, probe-first and graph-dump experiments remain historical records,
not results of this method. Novelty and repair benefit are not established. Current progress and
verification receipts are recorded only in [WORK_LOG.md](../WORK_LOG.md).
