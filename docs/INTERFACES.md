# Implementation interfaces

Package `scicontext`, Python 3.12+. Core helpers use stdlib and jsonschema. JSON dictionaries form the boundary. Never import task code to parse it; never evaluate generated strings.

## Expressions and evidence

`expressions.py`:

- `parse_expression(text: str) -> dict`: ordered safe expression tree or `{"op":"unknown","text":...}`. Nodes: `{"op":"symbol","name":"x"}`, `{"op":"constant","value":number}`, `{"op":OP,"args":[...]}`. Arithmetic OP: add, sub, mul, div, pow, neg. Recognized calls: sum, sqrt, matmul, norm. Unknown calls retain source spelling and stay unknown. Preserve operand order; no array/float algebraic rewrites.
- `align_expressions(expected: dict, actual: dict, bindings: dict[str,str] | None = None) -> dict`: status match/mismatch/unknown, ordered differences and limitations. Bindings rename expected to actual symbol names. Structural matching is not mathematical equivalence.

`evidence.py`: `extract_evidence(root: Path, paths: list[str] | None = None, *, max_files: int = 200, max_entries: int = 2000) -> dict` with schema_version, entries, coverage. Each entry: id, path, sha256, start_line, end_line, scope, kind, text, expression (tree or null). IDs depend on immutable source/span. Restrict to regular files beneath root; exclude hidden/auth/verifier paths; record unsupported languages/parser failures. Extract assertions, assignments, returns, comparisons, signatures/docstrings and import context. Syntactic references do not establish complete dataflow.

## Graph and semantics

`graph.py`:

- `graph_schema() -> dict`: Codex-compatible strict JSON Schema.
- `validate_graph(graph: dict, root: Path, *, max_claims: int = 12, max_nodes: int = 64) -> dict`: valid, errors, warnings. Verify schema, IDs, references, safe paths, exact evidence spans/hash and caps. Citation matches are not semantic proof.
- `render_graph(graph: dict, analysis: dict | None = None) -> str`: deterministic bounded text preserving assumptions/conflicts.

Canonical graph fields (required): schema_version="1.0", task_id, quantities, claims, evidence, observations, unresolved.

- Quantity: id, name, meaning, code_symbol, dimensions (dimension-label to rational-as-string exponent object or null), scale (positive canonical-unit multiplier or null), shape (list of positive integer/string extents or null), evidence_ids, status (explicit/inferred/unresolved).
- Claim: id, description, relation (expression tree or null), actual (expression tree or null), bindings (expected-symbol to actual-symbol strings), quantity_ids, evidence_ids, assumptions, operation (unit_conversion/weighted_sum/normalization/linear_transform/other), status.
- Evidence: id, path, sha256, start_line, end_line, quote.
- Observation: id, claim_id, description, status (proposed/reported), artifact (relative scratch path or null). Reported observations require execution-log corroboration; the graph alone cannot certify execution.
- unresolved: string array.

`semantics.py`: `analyze_graph(graph: dict) -> dict` with findings (claim_id, kind, status, explanation, assumptions) and coverage. Rules: add/sub require equal dimensions; products/ratios add/subtract exponents; rational powers/sqrt; sums preserve dimensions; explicit scales; shape/broadcast/matmul checks where supported. Conditional semantic lifting needs assumptions/evidence, not merely an operation name. Use Fraction for exponents/exact scaling cancellation. Distinguish algebraic from floating-point claims and preserve unknown/conflicting anchors.

## Ownership and integration

Expression worker owns expressions.py, evidence.py and their tests. Graph worker owns graph.py, semantics.py and their tests. Root owns CLI, prompts, config, deadlines, checkpoint collection, Codex/Pier adapter, release restoration, analysis, docs and integration fixtures. Workers must not edit root files or the shared protocol/interface docs. Separate worktrees and explicit commits only.

Before describing an actual expression as code-derived, controller must cross-check it against indexed source. Preserve invalid output; never fabricate repaired semantic content. Keep graph and probe artifacts outside candidate repository.
