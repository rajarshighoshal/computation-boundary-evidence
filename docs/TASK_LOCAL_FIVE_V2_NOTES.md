# Restarted task-local comparison: qualitative notes

Posthoc artifact review only. These notes are not supplied to the evaluated agents and do not
change the frozen method, prompts or budgets. Quantitative results are generated separately from
the run records. This is a development comparison on previously inspected tasks.

A later user-requested [task001 diagnosis](TASK001_FAILURE_DIAGNOSIS.md) inspected the saved hidden
failure and ran a separate public counterexample. That diagnostic extends the review below; it
does not backdate new knowledge into the evaluated agents' context or establish graph-level causality.

## Task 091

Both patches express atomic positions relative to the cube grid origin. Treatment subtracts the
origin before conversion to angstroms; baseline converts first and subtracts afterward. These are
algebraically equivalent, without claiming identical floating-point results. Both preserve lattice
construction and scalar sample order. The production changes are narrow and have relevant tests.

The treatment received its handoff and independently checked original versus origin-relative
fractional coordinates before editing. Its behavior is consistent with the supplied guidance, but
the trajectory does not establish that the graph caused the fix. Baseline reached the same
diagnosis independently. Important source bindings and mathematical correspondences remain unknown;
the handoff is useful narrative context rather than a mechanically established scientific proof.

Evidence under `runs/task-local-five-v2/jobs/`:

- `task-091-science/task_091__3JmuMCs/artifacts/model.patch`
- `task-091-baseline/task_091__okeQPcT/artifacts/model.patch`
- Treatment `graph-bundle.json`, `agent/repair.jsonl` and `agent/repair-sessions`.

## Task 009

Both repairs replace a gain-ignoring scaled surrogate, but choose different wall constructions.
Treatment offsets along the normalized meridional radial tangent while preserving interface
toroidal phase. Baseline uses the full physical radial direction, including its toroidal component,
and extends wall-phase coordinates and derivatives through VACMET and prescribed-wall plumbing.
The baseline's broader change is relevant to that representation choice, but also changes how
explicit phases interact with `nowall`.

Both differentiate their chosen geometry analytically and check derivatives with finite differences.
These checks support internal consistency, not identification of the intended historical projection
operator. Treatment documents the specification as unresolved in its inspected material and
distinguishes radial tangent from surface normal; baseline likewise qualifies normality by
radial-coordinate orthogonality. This review does not establish absence from all repository or
literature sources.
Shared test success does not establish equivalence between these scientific constructions.

The treatment received its handoff, reproduced the gain collapse independently and chose a documented
local convention consistent with the handoff's stated uncertainty. No explicit rejection of a graph
claim is visible, nor evidence of causal treatment benefit. Mechanical support remains partial:
claims have source-matched provenance and an existing radial interpolation expression matches, but
the exact construction and propagation expressions remain unresolved. Dimensions, scales, shapes
and scientific lifting are not established. The graph explicitly leaves the projection operator,
gain law, orientation and AWALL mapping unspecified. Its public-workflow probe checks finite,
noncollapsed outputs, not the uniqueness or correctness of the scientific operator.

Evidence under `runs/task-local-five-v2/jobs/`:

- `task-009-science/task_009__FHfaZYz/artifacts/model.patch`
- `task-009-baseline/task_009__4LrQgge/artifacts/model.patch`
- Treatment `graph-bundle.json`, `agent/repair.jsonl` and `agent/repair-sessions`.
- Baseline `agent/repair.jsonl`.

## Task 001

Baseline passes the supplied verifier; treatment remains incomplete. Both change reversal handling
and ring detection, but their axis definitions differ. Treatment pairs ambiguous linear-atom
neighbors using structural priorities and combines eligible path ends into collective axes.
Baseline uses reagent geometry heuristics for in-line directions, requires agreement at adjacent
atoms, leaves ambiguous continuations as endpoints, and splits lines at transverse substituents
to preserve separate rotations.

The public trajectories expose different rotor multiplicities despite both repairs stabilizing
the tested presentations and distinguishing the negative control. Presentation invariance alone
therefore does not establish completeness of the selected axes. This observation does not identify
the remaining hidden failure.

Both patches affect shared segment, coordinate and symmetry consumers; baseline is not simply
narrower. Treatment introduces a general exact canonicalization search with repeated isomorphism
checks, whereas baseline uses local direction rules and coordinate ranking. The former adds
potential worst-case cost without establishing the chemistry. Baseline still breaks chemically
ranked coordinate ties using atom keys, so its tested symbol-signature stability must not be
generalized to exact key-equivariant coordinate selection.

Treatment received the handoff and followed its reversal, multiplicity and collective-axis concerns
without visibly rejecting a claim. It independently reproduced discrepancies and tested additional
arrangements. The handoff acknowledged that branching cap/neighbor selection was not fully specified
in the inspected material. Axis-selection and linearity implementation references remain unresolved,
and structural alignments remain unknown. Structural tie-breaking does not by itself establish
physical collinearity or correct rotor selection. The observed paired outcome does not isolate a
causal effect of the graph or any particular claim.

Evidence under `runs/task-local-five-v2/jobs/`:

- `task-001-baseline/task_001__GGfH99H/artifacts/model.patch`
- `task-001-science/task_001__nJayhq5/artifacts/model.patch`
- Both trials' `agent/repair.jsonl`, including public reproduction output.
- Treatment `graph-bundle.json` and `agent/repair-sessions`.
- Baseline `agent/repair.jsonl`.

## Task 058

Both repairs derive lattice-index translations from stored ray-to-face distances instead of
reconstructed endpoints whose absolute coordinate tolerance could miss the selected crossing.
Baseline requires exact equality with the selected minimum; treatment also accepts a relative
floating-point tolerance. Their new near-tie regressions encode different policies. Treatment
documents that tolerance as an implementation choice not specified by the paper/manual. Passing
the benchmark therefore does not resolve all near-coincident-crossing behavior.

Both production patches are narrowly scoped to the distance routine and its supporting include/
test registration. The treatment receives cited scientific hypotheses and independently diagnoses
the original implementation. It checks the direction-normalization assumption against source.
The C++ source remains unsupported by the mechanical index, so its claims are not mechanically
verified C++ constraints. No extraction probe ran. No causal benefit is established by shared success.

Evidence under `runs/task-local-five-v2/jobs/`:

- `task-058-baseline/task_058__W3CJj2K/artifacts/model.patch`
- `task-058-science/task_058__eGAKKPX/artifacts/model.patch`
- Treatment `graph-bundle.json`, `agent/repair.jsonl` and `agent/repair-sessions`.

## Task 114

Both patches gate per-period cycling by the main cyclic flag, apply explicit initialization to
noncyclic assets, and correct Store scenario-mask alignment. Baseline additionally changes the
meaning of prescribed initial energy by applying standing retention in Store and StorageUnit.
Treatment preserves the existing initialization insertion. Its chronological boundary tests use
zero standing losses, so they do not settle this initial-loss convention. The difference is a
plausible source of different coverage, not an identified explanation of individual hidden failures.

Treatment also corrects the Store charging/discharging sign in documentation; baseline refactors
StorageUnit scenario alignment. These changes remain in storage constraints, tests and related
documentation, but baseline's initial-loss change expands the semantics beyond the common
label-boundary repair.

The treatment received its scientific handoff, independently inspected documentation/reproduction,
followed the boundary-gating interpretation and corrected the sign inconsistency flagged by the
graph. It found stochastic alignment during repair testing. No explicit rejection of a handoff
claim appears. Source-matched provenance supports the boundary/cyclic claims, but the Store balance
implementation reference is unresolved. Some quantities bind to source; structural comparisons
and scientific lifting remain unknown. The conservation claim separates prescribed initialization
as a boundary case and restricts its applicability around inactive gaps.

The recorded outcome is greater partial hidden-test coverage for treatment, with neither repair
fully successful. Aggregate counts alone do not establish the affected test identities or causally
attribute the difference to guidance.

Evidence under `runs/task-local-five-v2/jobs/`:

- `task-114-science/task_114__X86DdXk/artifacts/model.patch`
- `task-114-baseline/task_114__rxKXqVv/artifacts/model.patch`
- Treatment `graph-bundle.json`, `agent/repair.jsonl` and `agent/repair-sessions`.
- Baseline `agent/repair.jsonl`.
