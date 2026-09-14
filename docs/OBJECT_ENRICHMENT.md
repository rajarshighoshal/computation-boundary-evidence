# Interactive scientific tool contract

One repair agent builds its own scientific working model from code-owned, source-linked evidence.
The mandatory separate interpretation pass is retired.

## Tool interface
science(action, ...) supports:
- find(query, offset): ranked public-source/document matches and explicit paging.
- inspect(target, view, offset): relationships, definitions or literal source. Targets are returned
  IDs, relative paths, path:line or path#symbol. Ambiguity is reported; missing owners are not guessed.
- record_model(model): purpose, computations, expected_change and preserve, with source citations.
  Computations carry meanings, selected expression/quantity IDs, conventions and assumptions.

The existing source-cited model schema is reused for this record; its format name does not imply a
separate LLM call. Aim for roughly400words. No hidden per-claim character cap is imposed.

Initially only the science tool is advertised and callable. Ordinary shell tools become available
after a valid record_model result. Dispatch checks the actual tool name and current gate state,
including multiple tool calls returned in one model turn. Failed records leave the gate closed;
failure of a later revision does not pretend that revision was saved.

## Scientific evidence
Code derives source expressions, quantities, bindings and controlling predicates. Joern adds
targeted data/control-flow information when available. Source/analyzer identities are scoped to the
source version; cached analysis is not a global namespace. Fortran/MATLAB/Cython use their existing
frontends; unsupported structure remains source-linked and explicit.

Default answers are small views. Source/document pages use character offsets; relationship pages
use expression offsets. Large source/template text is explicitly expandable rather than dumped or
silently treated as complete. Parser-size limits are reported. Full source remains in the task repo.

Different invocations retain their bindings. Shared syntax does not imply equal values. A current
model cannot silently combine stale source versions. Code excerpts are distinguished from documents;
documented requirements and current implementation behaviour must not be conflated.

## Artifacts and interpretation boundary
The tool records query payloads, visible source identities, model revisions and a readable model.
The host preserves model submission and tool-result trajectories. All preparation, science queries,
reasoning and repair count in the task allowance. Cached input and reasoning tokens are subsets,
not additional tokens to double count.

Reference validity is not scientific entailment. The checkpoint demonstrates an observable
source-linked model-building step, not internal understanding. Development review checks whether
the scientific relationships are correct/useful and whether repair follows them.
