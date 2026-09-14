# Connected scientific interpretation contract

Current interpretation version: **object-enrichment-2.0**. The code graph remains
scientific-objects-1.0; old annotation artifacts and renderers remain readable.

## Code-owned input

The existing source/analysis pipeline builds computations, quantities and relationships.
scientific_model.reading_input compiles a shared entity/source index plus callable views:
each definition references its member entities, boundary entities and recorded relationships.
Source and Joern namespaces stay distinct. A callable correspondence needs a unique matching
definition site and name; it is not inferred from name similarity. Analyzer scope disambiguates
overlapping source ranges when available.

Operand roles, data dependencies, comparisons, control conditions and original code properties
remain code-owned. Missing operands/outputs stay explicit unknowns. Alternative call targets
remain alternatives. The reader view omits detailed AST/CFG scaffolding; the original analysis
remains in the durable source-analysis artifact. This is a projection of recorded evidence,
not mathematical equivalence or a newly recovered complete scientific specification.

Scientific documents, code excerpts and analyzer representations have distinct provenance.
Analyzer-generated pseudo-code is not a literal source quote. Private verifiers, gold patches
and prior repair answers do not enter this input.

## One scientific interpretation call

[The schema](../src/scicontext/scientific-model.schema.json) requests:

- A source-cited description of the task's scientific/computational purpose.
- Up to six selected computation IDs, each with a source-cited scientific meaning.
- Meanings for relevant quantity IDs belonging to that computation or its recorded boundary.
- Source-cited conventions/conditions and separately stated assumptions.

A cited statement has text and source_ids. The interpreter does not write graph edges,
dimensions, executable probes, patches or verified statuses. The same short prompt and
compiled input are used by the Codex and DeepSeek routes; there is one interpretation call.

The caller saves the response. Assembly validates the envelope, IDs and cited-source existence.
It preserves original code facts and joins accepted interpretation with the computation's actual
relationships. **Citation validity is not scientific entailment.** Scientific correctness and
usefulness still require inspecting actual model outputs against public evidence.

## Durable model and repair guide

The joined model is stored under graph.scientific_model and handed off as scientific-model.json.
Entities and source records are stored once and referenced by ID. Interpretations remain scoped
to their computations, so distinct conventions are not silently merged.

The guide presents purpose, computation meanings, quantity roles, conventions, assumptions and
source-level code predicates. Predicates describe implementation behaviour, not automatically
required physical laws. Compiler-generated predicates remain analyzer facts in the model rather
than being presented as literal source rules.

The renderer aims for 9,000 characters and keeps a displayed computation's explanation,
conventions and assumptions together. The first complete computation is always shown, even when
it exceeds that soft display target; additional complete computations remain in the model file.
The actual collection path uploads the model and inserts the guide into the repair prompt once.
The repair agent gets source locations for implementation inspection rather than a requirement
to mine the entire raw graph.

An invalid/empty 2.0 model is not accepted merely because the code graph is nonempty.
If no scientific model is delivered, the live science path does not start an unassisted repair
and label it science. Valid legacy 1.0 artifacts remain inspectable through their original path.

## Verification boundary

Offline tests cover identity, citations, unresolved inputs/outputs, condition preservation,
provider output handling, real helper assembly, real collection and controller handoff.
The five-archive replay checks deterministic compilation, not fresh extraction. The manually
authored source-grounded cube-reader fixture tests rendering, not LLM discovery.

Receipt: [connected science check](../results/connected-science-review-2026-09-14.json).
Model-generated scientific quality and repair improvement remain untested for this revision.
