# Hybrid scientific working model

This describes the current scientific-object method, not the retired probe-first experiments.
It is a research prototype; state-of-the-art performance and repair improvement are not established.

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

## Execution and inspection

Set `"extractor": "scientific_objects"` in an approved run configuration to select this method.
Existing configurations default to the historical annotation method for reproducibility. The new
mode prepares code objects before a single scientific-reading call; it does not invoke the old
probe/refinement loop. It reuses normal Pier/Codex execution and the existing overall allowances.

For offline inspection, without candidate imports or model calls:

```sh
.venv/bin/scicontext scientific-objects --root PATH --output objects.json --llm-input reader-input.json --markdown objects.md
.venv/bin/python scripts/demo_scientific_objects.py --output runs/scientific-object-demo-v1
```

The demo uses hand-authored interpretation fixtures. It tests representation/enrichment plumbing,
not LLM discovery or benchmark performance. Real scientific quality needs a separately approved
live check. Per-file coverage and its denominator are recorded in the graph.

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

Python is the implemented frontend; the full release is multilingual. Other language frontends,
broader scientific-source recovery and cross-file argument/return relations remain work.
The finite rule set does not establish full scientific coverage. Interpretation can still be
incorrect despite source anchors. Whole-benchmark effectiveness is untested for this method.

PyCG was checked as an optional source of call edges, not assumed compatible. Its published package
had startup/packaging issues; unmodified official source also failed during analysis initialization
in the tested Python environment after supplying its missing dependency. No call graph was produced.
The check does not prove universal incompatibility. Current wrapper links remain the bounded local
implementation, with cross-file/value-flow limitations explicit; no PyCG fork was introduced.
