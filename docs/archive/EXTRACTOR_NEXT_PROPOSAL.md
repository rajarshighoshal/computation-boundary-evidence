# Next extractor: task-local scientific contracts

Approved for parallel prototype implementation after discussion; not a new experiment protocol. The currently
running initial checks are unchanged. This develops Rajarshi's idea of scientific task understanding
linked to code; it is not a proposal for production guardrails or a larger agent framework.

## What the initial evidence identifies

- Task 091: the packet omitted the relevant volumetric reader because file selection was driven by
  literal filename mentions and then shallow/alphabetic ordering, without resolving reproducer
  imports/calls. Code discovered later by the LLM could be quoted but could not become an indexed
  implementation expression.
- Task 009: even a selected file lost relevant later statements because entries were a source-order
  prefix. A function-signature reference supplied no expression; other quantities lacked code
  symbols. The scientific equation `V = -sum(J)` was sent to an expression-only parser, while
  `-float(np.sum(bjac_i))` lost its reduction subtree at the unsupported cast.
- Some scientific information really is absent. Better retrieval cannot uniquely establish the
  missing projection-wall definition; both passing repairs made documented, different choices.

These findings distinguish retrieval/representation defects from scientific uncertainty. Fixing
the former is worth testing; it does not guarantee higher repair success.

Evidence: the saved packets/annotations/graphs for 091 and 009, and the source paths discussed in
[initial-check notes](RANDOM_FIVE_NOTES.md). Relevant modules are `packet.py`, `evidence.py`,
`annotations.py`, `expressions.py` and `semantics.py` under `src/scicontext/`.

## Proposed algorithm

1. **Retrieve the computation relevant to this task.** Seed a bounded code region from public
   reproducer imports/calls, task-named symbols and cited source spans. Resolve local definitions
   and immediate dependencies. Prefer relevant function bodies and statement neighborhoods over
   arbitrary file prefixes. Reuse the current AST parser, source IDs and evidence catalog.
2. **Have the LLM annotate meaning, using source references.** Describe the intended input/output
   relation, scientific quantities, conventions and assumptions. Reference actual operands and
   outputs by file, scope and source location. A bundled label such as “wall geometry” should not
   stand in for all coordinate and derivative variables when the relationship depends on them.
3. **Let code resolve the referenced computation.** Add missing cited regions to the index after
   annotation and build a small local dependency representation: assignment target, operand reads,
   local definitions, calls, returns and indexed accesses. Keep unsupported operations with their
   children, e.g. `neg → cast(float) → sum → bjac_i`; a cast is not automatically an identity.
   Branches, aliases and external calls may remain unresolved. No general whole-program analysis.
4. **Join scientific relationships to this representation.** Represent an equation as a target and
   RHS rather than mixing assignment syntax with expression matching. Link meanings to resolved
   operands. Units, frame, shape and normalization can independently remain unknown. A syntactic
   correspondence is not proof that a physical law holds.
5. **Produce a small executable scientific property where justified.** Examples include translating
   an origin while preserving relative geometry, or checking that supplied derivatives match the
   constructed surface. Code runs the declared probe using the existing bounded mechanism. Give
   repair the relation, relevant code locations, assumptions and observed result or counterexample.

Prefer deterministic post-annotation source expansion first; this need not introduce another LLM
session. Retain the existing total/extraction allowances for the first implementation test. Native
read-only extraction and ordinary repair stay as they are.

## Fast acceptance and rejection checks

- Using original public source, retrieve 091's reader and 009's relevant downstream statements
  through a recorded task/reproducer/reference path, within the same packet budget.
- Inserting irrelevant earlier declarations must not remove a later relevant function from the
  task-local representation.
- Resolve claimed operands to actual source definitions, or explicitly mark missing bindings.
  No dependency is invented solely from similar variable names.
- Preserve the assignment target and the cast/reduction structure in the example above, without
  claiming float conversion preserves all mathematical properties.
- Recover a useful scientific property and an executable observation when public evidence supports
  it. Probe failure on the buggy original can be informative, not a reason to discard the property.
- Keep the missing projection definition missing; improved graph coverage must not manufacture
  scientific certainty.

Start with deterministic tests using saved annotations and original public source, then a small
extraction-only development check if approved. Compare relevant-source recall, usable operand
bindings, supported properties, unresolved assumptions, time and token usage against the current
extractor. This is mechanism validation, not a claim of repair improvement.

Reject or simplify this direction if it cannot recover better task-local relationships under the
existing allowance, if the output remains generic prose with no operational link, or if apparent
coverage gains depend on unsupported scientific assertions. A fresh paired repair sample is a later
decision; no larger sample or new-method model runs are authorized by this proposal.
