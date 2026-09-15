# Design note: frozen-run semantics, export budget, and language-agnostic boundary contracts

Status: approved design, queued for implementation after the dev-30 v2 run exits.
Date: 2026-09-15 (22:20 IST). Author: research root session.
Principle: use existing tooling (Joern, tree-sitter, ast). Dense over exhaustive.
Honest labels over confident guesses. No hand-written language parsers.

## 1. Frozen-run semantics — commits must never abort or contaminate a run

Current machinery (already built):
- `_snapshot_frozen_source()` at run start copies `src/scicontext` + `prompts` to
  `runs/<run>/frozen-source/`; the revision is recorded as `implementation_revision`.
- Every trial subprocess gets `PYTHONPATH=<frozen-source>` (cli.py), so the host-side
  agent loop imports the frozen snapshot, not the live worktree; the same snapshot is
  uploaded into science containers. Runs are hermetic by construction.

The defect: `cli.py` (~line 443) re-checks `git rev-parse HEAD` at every dispatch and
raises `RuntimeError("Implementation moved during the run")`. This aborts all remaining
dispatches on any commit (observed: tail-10 abort at 1e8684f→0bd1bd2) even though the
run is already pinned by the snapshot.

Change: demote to a recorded warning. Keep the comparison; write
`head_at_launch` + `head_drift: bool` into the receipt; dispatch regardless.
The frozen snapshot remains the authority for what executes.
Test: dispatch with a moved HEAD records drift and launches.

## 2. Joern export budget

`joern_regions.sc` allocates `maxNodes=4000 / maxEdges=20000` per export; larger method
sets are omitted with `whole_method_exceeds_export_budget`. The raw export never reaches
the model (contracts do), so the budget is a host-side transport limit, not a safety
limit. Raise to `16000 / 60000`, keep the omission path as a final guard, no schema
change. Receipt check: next real run asserts the omission list is empty on the dev set.

## 3. Boundary classification — language-agnostic, three-layer cascade

Core predicate (no parser involved): a callee is **internal** iff its definition exists
in the scanned universe (files read/extracted by the packet and its analyses);
otherwise **external-or-unknown**, refined by stronger evidence below.

Layer 1 — semantic (Joern, for C/C++/Python):
- Resolved CALL edge -> METHOD node with in-repo FILENAME => internal.
- `IS_EXTERNAL=true`, or no METHOD node resolves => external candidate.
- C++ header-defined functions resolve into the CPG -> correctly internal.
- Available in `distill_joern_contracts` (node_map already carries FILENAME/IS_EXTERNAL).

Layer 2 — declarative binding (provider naming, data table not parsers):
  BOUNDARY_DECLS = {
    c/cpp:   r'#include\s*[<"](?P<provider>[\w./-]+)[>"]'
    fortran: r'^\s*use\s*(?:,\s*intrinsic\s*::)?\s*(?P<provider>\w+)'
    python:  ast Import / ImportFrom (existing parse)
    cython:  cimport statements
    matlab:  none (see limitation)
  }
  Plus a small heuristic prefix map for provider attribution (e.g. pthread_* -> pthread.h),
  always marked `basis: prefix_heuristic`, never presented as proof.

Layer 3 — fallback: `unknown_external` with recorded basis. Never faked as external.

Uniform contract schema (identical across all languages; this is the language-agnostic
part that matters):
  {"callee": ..., "line": ..., "code": ...,
   "boundary": {"kind": "internal" | "external" | "unknown_external",
                "provider": "<library or null>",
                "assume": "correct_interface" | null,
                "repair_scope": "caller_file" | "repo",
                "basis": "<layer and evidence>"}}

Epistemics: SWE-bench Science gold patches repair in-repo code; an interface fault would
therefore be in-repo and classified internal by layer 1. External => not-the-repair-site
is consistent with the benchmark, not a heuristic hope. Known false-positive class:
macro-generated calls -> stay `unknown_external`, disclosed.

Language coverage facts (grounding the cascade):
- Installed Joern frontends: C, C++, Python, Java, JS, Rust, ... (no Fortran, no MATLAB).
- Installed tree-sitter grammars: c, cpp, fortran, matlab; Cython via its compiler frontend;
  Python via ast.
- The 6-language set = (benchmark corpus languages) ∩ (available tooling). Adding a
  language later = one dependency + one BOUNDARY_DECLS row + optional Joern route. No
  parser is ever hand-written.

Known limitation (disclosed, not hidden): MATLAB has no standard import mechanism; only
the core predicate applies, so most cross-file MATLAB calls will be `unknown_external`.
Fortran is the strongest declarative case: cross-file calls require `use`.

Files to touch (implementation batch, after run exit):
- src/scicontext/cli.py — guard demotion (+ receipt fields)
- src/scicontext/joern_regions.sc — budget constants
- src/scicontext/source_backends.py — BOUNDARY_DECLS, include parsing, layer merge,
  uniform schema in distill_joern_contracts and distill_native_contracts
- src/scicontext/science_tools.py — surface `boundary` fields in contracts view
- tests: test_source_backends.py fixtures (C++ with #include; Fortran with use; MATLAB
  fallback), test_cli drift-recording test

## 4. Sequencing and gates

1. dev-30 v2 (running) exits -> analyze; check 073/058 movement.
2. Apply batch 1-3 with focused tests + full suite.
3. Freeze: commit; from then on commits are safe during runs (section 1).
4. Optional single dev-30 v3 confirmation if contracts visibly change behaviour;
   then locked-89 evaluation.
5. Deadline 16 Sep 23:59:59 CEST (= 17 Sep 03:29 IST); margin at design time ~29h.
