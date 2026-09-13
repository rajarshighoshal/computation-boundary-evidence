# Hybrid scientific working model

This describes the current scientific-object method, not the retired probe-first experiments.
It is a research prototype; state-of-the-art performance and repair improvement are not established.

## Current core: shared computational representation (13 September)

The reuse-first backend integration adds Joern, SymPy and fortls to the common representation.
Joern is invoked by the extractor's `interpret` path on the host, after downloading the exact
public files referenced by the input. `joern-parse` and `joern-export` produce analyzer-owned
data/control-flow facts; `source_backends.py` normalizes and binds them by source location. Only
selected source regions and direct boundary endpoints enter the model input. The complete export
is retained in `source-analysis.json` and delivered alongside the repair artifacts. A missing Joern
executable or failed frontend is recorded as a capability gap, not silently called successful analysis.

SymPy 1.14 constructs formal symbolic expressions and runs common-subexpression elimination.
Unspecified quantity types use noncommutative symbols. This is a symbolic projection, not a proof
that algebraic rewriting preserves floating-point execution. Original ordered source templates
remain the source record; unsupported symbolic operators are listed explicitly. SymPy does not
infer a physical meaning from variable names. The source-to-representation adapter is still custom;
this integration does not claim to have removed every custom scope/quantity abstraction.

fortls 3.2.2 supplies Fortran symbols and typed interface hovers through its own LSP handlers.
It does not supply Joern-equivalent dataflow. MATLAB/Cython retain the existing syntax frontends.
The shared representation is language-independent, while analysis depth remains backend-dependent.
No new compiler IR pipeline is introduced. The archived indexed entries contain Python, C/C++,
Fortran, MATLAB and Cython; skipped-file metadata also includes JavaScript/shell, an R documentation
renderer and CUDA files. That bounded inventory is not proof of exhaustive source-language coverage.

Connected extraction now constructs `scientific-computation-1.0` before interpretation. This is
an implemented code-side abstraction, not an LLM-generated graph. The older API-object layer below
is retained for compatibility and provenance; it is no longer the main interpretation target in
connected mode. `src/scicontext/computation.py` owns this representation.

- **Quantity identities** distinguish scoped inputs, assignments, versions and indexed fields.
  Field reads retain their container dependency. Units, axes and coordinate frames remain unknown
  unless supported by other source/interpretation evidence; the algorithm does not invent them.
- **Mathematical templates** share ordered expression structure up to renaming quantity operands.
  Repeated operands, constants, indexing structure and operator order survive. For example,
  `a*x+b*y+c*z` has one template and distinct bindings at each occurrence, rather than one
  description per function. Native language identity remains explicit because similarly spelled
  operators need not share semantics. This is structural abstraction, not algebraic equivalence.
- **Transformation occurrences** bind a template to quantities and a source location. Local pure
  intermediates are expanded under an explicit size bound while original dependency edges remain.
  Branches, loops, early returns and validation continuations carry source conditions; shared
  condition sets are stored once. Indexed archived expressions use the existing dependency evidence.
- **Interprocedural edges** retain statically supported argument and return candidates from helper
  retrieval. Variadic, dynamic, decorated and unresolved calls are not silently substituted.
- **Scientific-source links** identify explicit symbol references in public documents. These are
  candidate meaning correspondences, not proof that a passage defines a quantity. The LLM annotates
  existing computational-relation IDs with meanings/conventions/assumptions; it cannot manufacture
  dataflow links or alter the code-owned representation. Source validation guards remain distinct
  from physical requirements.

The compact interpreter input uses relation IDs plus the shared representation and source evidence,
not duplicate legacy object/operation indexes. Assembly attaches those relation objects to the
durable scientific graph and joins annotations with the existing schema. The repair guide renders
shared mathematical forms, concrete bindings and retained conditions, with interpretations when
available. Whole omitted display groups remain in the graph; a display bound never cuts a condition
off its occurrence. This does not guarantee the complete serialized evidence input is smaller:
recovering relationships adds information as well as sharing repeated structure.

### Verification and remaining gaps

`results/computation-coverage.json` records a deterministic offline check over all 119 previously
materialized public packets, selected without inspecting repair outcomes. It measures recoverable
arithmetic/template structure, not scientific correctness, whole-repository coverage or success.
The verified scan found arithmetic in all 119 packets and shared templates in 116, but arithmetic
outside reproducer files in only 98. The other 21 saved slices must not be reported as recovered
implementation-level science: 015, 018, 020, 023, 024, 027, 042, 052, 053, 065, 066, 069, 070, 072,
077, 092, 100, 105, 106, 115, 119. This may reflect retrieval/entry limits or computation outside the
supported arithmetic forms; this scan does not distinguish those causes. It took 2.89 seconds for
representation construction from archived packets, excluding retrieval, agents and verification.
Tests cover cross-domain renaming, operand identity/order/constants, local intermediates, branch
merges, early returns, possible mutation, array-field dependencies, source-document links, helper
calls and the existing C/C++/Fortran/MATLAB/Cython frontends. Production assembly/guide tests use
mock annotations, not a hidden model call. The connected source replay and code-only handoff are
preserved in `runs/computation-connected-verified/`.

Remaining gaps are explicit, not claimed as completed work:

1. Templates do not establish physical meaning, operator types, floating-point equivalence, tensor
   shapes or alias correctness. A weighted expression is not automatically a particular physical law.
2. Interprocedural binding is partial; `*args`/`**kwargs`, indirect calls, mutation and language-specific
   dispatch can remain opaque. Native function/array-call ambiguity is preserved. Native intermediate
   expansion and complete loop-carried dependence analysis are not implemented.
3. Local expression expansion is conservative, not whole-program SSA/symbolic execution. Unsupported
   control regions and missing indexed expressions are recorded in `gaps`. Retrieval omissions remain
   in source-selection receipts. Conditions from an indexed snippet are not a complete path predicate.
4. Scientific interpretation with this new representation has not been live-tested. The earlier
   one-call test used a different input and output contract; its result cannot establish this revision's
   quality. No repair comparison has evaluated the shared-template revision.

The existing harness/model route is unchanged. No new retries, agent framework, compiler IR or
paid experiments were introduced by this core implementation.

## Representation and division of work

Code identifies values, operations, source bindings, interface parameters and dependency links.
Recognised API rules supply scientific computational roles: a linear system's coefficient operator,
right-hand side and solution; sampled integration's field and coordinates; graph topology and
component partitions; or unit-bearing quantities and their arithmetic. These are documented API
contracts and source facts, not a recovered scientific specification.

Custom computations are retained even when no API rule applies. They have source-backed objects
and operations but no invented scientific meaning. Scoped shadowing, uncertain dataflow and
unsupported operations stay visible. Wrapper links identify indexed lexical targets/bodies; they
do not prove argument/parameter or return-value equivalence across functions.

Pint supplies offline unit parsing and registry-based dimensionality/scales. Prefixes and compound
units no longer depend on a hand-maintained vocabulary. Only multiplicative scales are propagated;
offset/logarithmic or unresolved unit cases stay unsupported. Registry precision and the candidate
library's runtime behaviour are not mathematical-equivalence guarantees.

The LLM reads the public task and scientific passages alongside the objects and code/interface
excerpts. It explains scientific meaning, conventions and assumptions on exact existing object IDs.
It cannot create graph structure, overwrite units/shapes, supply probes, or declare a hypothesis a
required patch. Code joins accepted annotations separately from intrinsic properties and records
unanchored/malformed output as omitted. See [the contract](OBJECT_ENRICHMENT.md).

## Scientific context, not an API catalogue

An operator's numerical role and its scientific role are different. Recognising a linear solve does
not establish whether its matrix represents stiffness, a transition process or something else.
That connection must come from the scientific material and task context. Similarly, dimensional
consistency cannot decide whether the correct coordinate frame or boundary condition was selected.

The delivered representation combines meanings with actual code relationships and unresolved cases.
Repair uses it as a working model, not as a list of mandatory invariants. Its usefulness remains an
empirical question, especially when documentation is incomplete or inferred meaning is wrong.

## Task-directed source retrieval

Scientific mode now follows literal public workflow evidence: imported function/class uses,
receiver-method candidates, native calls and filename-matched functions, and call spellings inside
embedded MATLAB driver text. Generated definitions are not treated as calls; import/local shadowing
and absent targets do not produce an invented binding. These are retrieval candidates, not runtime
dispatch proofs. There are no benchmark-specific names in the retrieval implementation.

Function documentation is ranked against the public task and scientific passages with TF-IDF
cosine similarity. Workflow references precede language-balancing fallbacks; the existing global
entry allowance is shared across selected files. Legacy selections remain reproducible. File,
depth, call-site and entry omissions are exposed rather than treated as evidence of irrelevance.

After source validation, exact call sites can point to retrieved interfaces and partial bodies via
`possible_callee_interface`/`possible_callee_body` links. Output dimensions, shapes and argument/return
equivalence stay unknown. Comparisons retain source-predicate objects; unsupported unpacking or
mutation retains a source-statement anchor without becoming a false binding for every target.
The LLM still annotates existing IDs only. This uses source parsers, not compiler IR.

Offline regressions are generated by `scripts/check_task_retrieval.py` on the same public images.
Targets and scientific source regions are explicitly posthoc development checks, not extraction
rules or an unseen test set. The receipts record operation locations/kinds: finding a function or
some setup calls is not claimed as complete scientific-body coverage. Missing gravitational
counterparts and incomplete Osprey timing/calibration coverage remain limitations. The updated
[live enrichment comparison](SCIENTIFIC_READING_V1_V2.md) shows better implementation anchoring of
reviewed scientific meaning, with [remaining gaps](SCIENTIFIC_READING_V2_NOTES.md). No repair
comparison has yet evaluated this revision.

## Execution and inspection

Set `"extractor": "scientific_objects"` in an approved run configuration to select this method.
Existing configurations default to the historical annotation method for reproducibility. The new
mode prepares code objects before a single scientific-reading call; it does not invoke the old
probe/refinement loop. It reuses normal Pier/Codex execution and the existing overall allowances.

For offline inspection, without candidate imports or model calls:

```sh
.venv/bin/scicontext scientific-objects --root PATH --output objects.json --llm-input reader-input.json --markdown objects.md
.venv/bin/python scripts/demo_scientific_objects.py --output runs/scientific-object-demo-v1
.venv/bin/python scripts/check_multilingual_sources.py --output runs/multilingual-public-source-new
```

The demo uses hand-authored interpretation fixtures. It tests representation/enrichment plumbing,
not LLM discovery or benchmark performance. Real scientific quality needs a separately approved
live check. Per-file coverage and its denominator are recorded in the graph.

The approved [live reading check](SCIENTIFIC_READING_V1.md) now has outputs from full public
SHTOOLS, Osprey and MACS workspaces. [Source review](SCIENTIFIC_READING_V1_NOTES.md) found substantive
scientific interpretations but insufficient links to the relevant implementation bodies. This is
evidence for a source-selection failure, not repair improvement or completed model–code alignment.

Pinned Linux/x86-64 helper wheels were downloaded for Python 3.10–3.13; this verifies wheel
availability, not imports inside every benchmark image. The 3.10 helper uses rpds-py 0.30.0 because
the existing newer pin lacks a compatible wheel; other guest versions retain that newer pin.

## Research basis and what is not implemented

[Semantic enrichment of dataflow graphs](https://arxiv.org/html/1807.05691v2) motivates separating
concrete computation from domain interpretation and retaining unknown computation without breaking
connectivity. Its richer ontology operations and dynamic interprocedural provenance are not
reproduced by this static prototype.

[SKEMA](https://github.com/ml4ai/skema) separates program analysis, scientific-text reading and
mention/model linking. This supports giving the interpreter scientific source material, not just
a code graph. Our anchored annotations are not a complete text–equation–code alignment system.

[SpecRover](https://arxiv.org/html/2408.02232v4) is a close repair precedent for making issue-conditioned
function intent explicit during retrieval. Consequently, an additional LLM explanation pass alone
is not a novelty claim. The intended contribution here must involve substantive scientific
representation, code-derived relationships and demonstrably useful contextual understanding.

[DSrepair](https://arxiv.org/html/2502.09771v1) retrieves API knowledge-graph information and combines
it with fine-grained execution diagnostics for data-science snippet repair. It is close to the API
knowledge part here, but not the same repository-level setting. Its results also caution against
assuming that longer or richer API descriptions are necessarily better repair context.

[SIGA v2](https://arxiv.org/html/2606.09774v2) grounds native coding agents in simulator documentation,
procedural knowledge and validation. It supports the domain-interface motivation; it does not
justify importing another termination gate or training a procedural-memory system for this task.

[ReproAgent](https://arxiv.org/html/2608.24291v1) links paper-derived obligations and related-code
evidence to implementation work in paper-to-code reproduction. Source-anchored scientific context
is therefore not independently novel. Our investigated direction starts from an existing buggy
repository's objects and computations, then interprets their scientific roles for repair. Whether
that distinction helps is still an empirical question, not an established SOTA or novelty claim.

## Current limits

Python AST and Cython's parser, plus Tree-sitter C/C++/Fortran/MATLAB frontends, feed the shared
representation in scientific-object mode. Legacy packet mode remains Python-only. Native syntax
adds interfaces, declarations, expressions, local call targets and source documentation—not new
scientific API rules or inferred physical laws. Cython compile-time evaluation/includes are disabled;
omissions are exposed. C headers use a C++-compatible parse with dialect ambiguity stated. Macros,
overloads, dynamic dispatch and MATLAB/Fortran call-versus-index ambiguity remain unresolved.

Bounded native packets group contiguous comments and balance documentation, interfaces and
computation across functions. Returns and writes to explicit output parameters receive priority. Omitted prior
definitions prevent stale bindings from being presented as dataflow. Parameter declarations retain
Fortran dimensions/intent as source text. These selection heuristics are not complete slicing.
Scientific-mode Python selection retains the enclosing interfaces and docstrings with selected
body statements; the legacy selector is unchanged. MATLAB implicit outputs refer to header-declared
outputs evaluated at function exit, not whole bodies labelled as return statements.

Pinned public-source checks are in `runs/multilingual-public-source-reviewed`: selected files from
bedtools, Osprey, MACS, SHTOOLS and htslib. They establish artifact generation, not complete parsing
or scientific understanding; htslib macro-related parse errors and packet limits remain visible.
The initially requested MACS `.pyx` file was absent: its pinned version is `BedGraph.py`, parsed as
Python. Earlier failed receipts are preserved; native Cython is covered by synthetic tests here,
not claimed as a successful real `.pyx` benchmark-source check.

### Scientific-input preflight

Follow-up artifacts in `runs/scientific-input-preflight` expose a distinction between component
interpretation and task-complete understanding. No model output was generated or scored.

| Public component | Scientific information available | Missing task coverage |
| --- | --- | --- |
| SHTOOLS magnetic tensor | Source comments state the north-west-up frame, coefficient normalization, output units and zero-trace condition; interfaces and tensor-output writes provide anchors. | One routine cannot establish equivalence across the other tensor implementations, coefficient data and complete public workflow. |
| Osprey quantification | Interfaces and sampled calculations distinguish uncorrected tCr ratios, water scaling and tissue correction; their assumptions are documented locally. | The public task also concerns a model-derived contribution and cross-protocol behavior outside this selected file. |
| MACS sparse signal track | Class/interface anchors retain zero-based, right-open transition conventions and the public task's evidence-attribution requirement. | The packet still omits `bedGraphTrackI.refine_peaks` even though that method exists in the file; the public reproducer and remaining repository are absent from this selected-file check. |

These are source-backed reading targets, not verified scientific truth or intended patches. The
initial Python packet had dropped every interface; interface/docstring reservation fixes that
specific defect. Balancing native entries across functions also exposes Osprey's later calculations
as objects rather than relying on accidental whole-body excerpts. Neither fix establishes task
localization. A component-only reading trial must be labelled accordingly; a task-level test needs
the complete public workspace and must inspect whether its relevant computation is actually indexed.

Broader scientific-source recovery and cross-file argument/return relations remain work.
The finite rule set does not establish full scientific coverage. Interpretation can still be
incorrect despite source anchors. Whole-benchmark effectiveness is untested for this method.

PyCG was checked as an optional source of call edges, not assumed compatible. Its published package
had startup/packaging issues; unmodified official source also failed during analysis initialization
in the tested Python environment after supplying its missing dependency. No call graph was produced.
The check does not prove universal incompatibility. Current wrapper links remain the bounded local
implementation, with cross-file/value-flow limitations explicit; no PyCG fork was introduced.
