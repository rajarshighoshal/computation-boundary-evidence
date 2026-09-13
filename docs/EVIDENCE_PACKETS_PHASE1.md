# Phase 1: interpreter input before/after

Structural input comparison only; not scientific correctness or repair benefit.

| Measure | Before | After |
|---|---:|---:|
| objects | 300 | 122 |
| operations | 97 | 38 |
| links | 505 | 211 |
| Saved JSON bytes | 535081 | 432526 |

Connected packets: 8; complete function bodies: 8.

## Example source region

Source: `source/desc/stability/terpsichore/external_region.py:11-36`.

Before: the defining excerpt (other indexed fragments may occur elsewhere):
```python
def build_external_region_payload(
    equilibrium_data,
    *,
    wall=None,
    wall_scale: float = 1.0,
    wall_mode: str | None = None,
    projection_awall: float = 2.5,
    projection_gain: float = 0.25,
    nowall: int = 1,
):
```

After: the full hash-checked body, associated with its packet's objects/operations:
```python
def build_external_region_payload(
    equilibrium_data,
    *,
    wall=None,
    wall_scale: float = 1.0,
    wall_mode: str | None = None,
    projection_awall: float = 2.5,
    projection_gain: float = 0.25,
    nowall: int = 1,
):
    inputs = vacmet_inputs_from_equilibrium_data(
        equilibrium_data,
        wall=wall,
        wall_scale=wall_scale,
        wall_mode=wall_mode,
        projection_awall=projection_awall,
        projection_gain=projection_gain,
        nowall=nowall,
    )
    vacmet = compute_vacmet_metrics(**inputs)
    return {
        "inputs": inputs,
        "vacuum_grid_data": vacmet.as_vacuum_grid_data(),
        "rvac": vacmet.rvac,
        "vp": vacmet.vp,
    }
```

## Remaining gaps

- unresolved_input

Omitted packet seeds: 13; reasons: {'packet_limit': 13}. These are selection/budget omissions, not evidence that the excluded material is irrelevant.

Candidate callee links retain their original status; they are not runtime dispatch proofs. No LLM interpretation, guide renderer, repair prompt or scientific rule changed in this phase.

## Manual transformation example: DESC development task 009

This is a manually constructed design target, not automatic extractor output, a gold specification,
or a repair result. This task was already development-exposed. Only the saved input and original
public source/context were inspected here; no candidate code, model experiment or verifier ran.
The example illustrates a general representation; it is not a geometry-specific extraction rule.

### What was actually supplied

Input: `runs/evidence-packets-phase1-final/after.json`.
Selected packet: `ep_a7ca93af09ccf9af0fbf45ac`, rooted at the return from
`vacmet_inputs_from_equilibrium_data` (`equilibrium.py:65`). It supplies the complete adapter body
(`ep_25dbd7e911b1513e7899b4b2`, lines 26–80), source entries, operations, objects and public task notes.
It does **not** supply `vacuum.py`. In fact, that file has no code passages or complete bodies in
the entire saved after-input. The two helper calls have unresolved targets in this packet.

The public import at `equilibrium.py:9` points to `.vacuum`. I followed that import manually to
inspect the boundary adapter, wall builders and metric computation. Those additional bodies are
necessary evidence for the account below: the original packet alone does not support it.
`external_region.py` and the public reproducer are in the wider saved input, outside this packet.

All code paths below are relative to
`runs/task-local-development/originals/task_009/source/desc/stability/terpsichore/`.

### The three connected transformation units

| Unit | Inputs → transformation → outputs | Distinctions that must survive compression | Evidence |
|---|---|---|---|
| T1: extract the plasma boundary representation | Equilibrium geometry fields → alias lookup and boundary selection → coordinate and derivative vectors | Rank-2 arrays are point/radial and select `[:, radial_index]`; rank-1 boundary arrays pass through. The adapter defaults to radial index −1. R/Z/phi and their derivative roles remain distinct; returned vectors must have matching shapes. | Supplied `equilibrium.py:26–59`; additionally retrieved `vacuum.py:225–269`. |
| T2: construct the outer-wall representation | Boundary vectors plus wall controls → prescribed/scaled/projection branch → wall coordinates, angular-derivative arrays and effective `nowall` | Projection mode is a geometry-construction regime, not just a name. Current projection construction deletes `projection_gain` and delegates to the scaled-wall helper with `projection_awall`. Projection sets effective `nowall=-1`. | Supplied control forwarding at `equilibrium.py:65–80` and `paper.md:33–45,63–70`; additionally retrieved `vacuum.py:272–377`. |
| T3: construct and expose pseudo-vacuum quantities | Boundary vectors from T1, wall arrays from T2 and radial controls → interval geometry and metric calculation → `rvac`, `bjac`, metric arrays and `vp`, then the external payload | Wall position alone is insufficient: angular derivatives feed the metric calculation. `ivac=0` returns empty outputs; `ivac>0` requires nonzero `dsvac`. The sign of effective `nowall` selects angular conventions. Array outputs use point × vacuum-interval layout, while `vp` is per interval. | Additionally retrieved `vacuum.py:85–199`; wider-input `external_region.py:21–36`; supplied `paper.md:25–31,63–70`. |

Relations: T1 supplies boundary data to both T2 and T3; T2 supplies wall arrays and its effective
mode to T3. The payload wrapper only packages T3's outputs, so it does not need a separate scientific
unit. These are manually source-traced relationships, not newly resolved edges in the saved graph.

One retained equation makes the wall-to-output relationship explicit. The implementation computes
`rvac_i = svac1*rpvi + svac3*rwall + svac2*rspvi` (`vacuum.py:162`), where the weights depend on
radial position, `dsvac`, `pvac`, `qvac` and `abs(nowall)` (lines 151–160). It then computes the
Jacobian and metric expressions from the corresponding derivatives (lines 163–188), including
`vp[interval] = -sum(bjac_i)` (line 182). This is a description of this implementation, not a claim
that the formula is a universal scientific law or that `vp` has a verified physical normalization.

### Compact context we would want to deliver

> This external-region calculation converts equilibrium geometry into plasma-boundary vectors,
> constructs a wall, and uses both to form pseudo-vacuum geometry and metric payloads. Boundary
> extraction preserves point order and selects the radial axis; coordinates and derivatives travel
> together [T1]. Projection mode must construct a distinct boundary/derivative-based geometry and
> propagate it through the shared downstream path, while preserving the simpler mode [paper.md:
> 33–45,63–70]. In the current source, projection construction discards `projection_gain` and uses
> scaled-wall construction with `projection_awall`; its effective `nowall` is −1 [T2]. Downstream,
> `rvac_i = svac1*rpvi + svac3*rwall + svac2*rspvi`; wall derivatives also enter Jacobian and metric
> expressions, so the wall representation includes more than positions [T3]. The no-vacuum case
> (`ivac=0`) returns empty arrays, and `nowall` sign changes angular conventions. The public workflow
> compares two gains and a scaled-wall case at matching wall size; it checks finite outputs and
> non-collapse within its numerical comparison criterion [reproduce.py:90–140]. Exact intended
> projection normalization is not established by these sources; the required derivative-consistent
> construction cannot be inferred merely from a request for different outputs.

This explanation contains an actual computation, a source-stated expectation, and their relevant
disconnection. It does not prescribe a patch or claim a new execution observed a failure. The public
comparison checks `rvac`, `vp` and `bjac` collectively for collapse; it does not require every element
of every array to differ for every possible parameter change. No invariance violation is inferred
from the name of a report field or from unchanged output alone.

### Binding back to the existing packet

- T1 geometry source entry: `ev_49249b62437743c57b126552`; boundary call:
  `sop_e9569e04fb61348e2726be52`; bound boundary object: `so_138b6ab89e9dced899a691f5`.
- T2 forwarded controls: mode `so_d345ee1757fa81188f0fa11b`, wall size
  `so_1c45f30a3ccdb80062cc3dab`, gain `so_685bcfc513b45c9e6a2a9b36`.
- Shared handoff: operation `sop_4c33f0e25409b928b539e71a` and returned value
  `so_dff22bee65510860bb13afbe`.
- Scientific expectation: `doc_ba9470eacd2e0f6a8cec8671` and
  `doc_8f286786da6f66e8fbd7751b`.
- The added `vacuum.py` internals have no IDs in this saved input. Until retrieval supplies and binds
  them, the current packet-only annotator cannot honestly emit the complete T2/T3 explanation.

### What becomes algorithmic, and what needs interpretation

Code should recover the imports/calls, argument forwarding, array selection, branch conditions,
return fields and recorded dependencies. It can group straight-through adapters and deduplicate
shared source bodies. The LLM interprets quantity roles and scientific stages using that structure
and the public method notes, and proposes grouping across function boundaries. The grouping must
retain the recorded inputs, outputs and controlling conditions; uncertain roles stay explicit.

The smallest next design question is whether targeted retrieval of unresolved implementation
callees supplies enough evidence to construct these connected units. This case needs actual helper
bodies, not a larger API vocabulary or more annotations of wrapper parameters. A callable definition
found via an import remains static resolution evidence, not proof that a runtime dispatch occurred.

### Speed is part of the design

Do not implement acceleration in this step. The candidate fast path is: index unchanged source
once; retrieve and deduplicate the connected implementation regions; interpret the resulting units
in one bounded request where feasible; reuse the durable representation during repair. Share a
scientific convention once across units instead of repeatedly asking the model to explain it.
Any reusable interpretation must be keyed by source, task context, method/prompt and model identity.

Before another scale-up, measure retrieval/assembly time, model time and repair time separately,
alongside input/output tokens and retained scientific relationships. Distinguish per-task latency
from full-benchmark makespan. Then address the measured bottleneck: smaller sufficient inputs,
reuse, or independent-task concurrency. No extraction speedup, runtime target or safe concurrency
level has been measured by this manual example. Faster extraction also does not establish faster
end-to-end repair; that requires the paired evaluation.

### Source verification

The saved complete adapter body and cited public-paper passages were checked against original
source slices. Packet/object/operation/entry/document IDs above were checked for membership.
Additional helper files were read as text, not imported or executed. Original-source SHA-256:

| Path | SHA-256 |
|---|---|
| `runs/evidence-packets-phase1-final/after.json` | `fc16d4b4a0d36c60dc943edaff2ff1ccfc6ce1e3746721c0a7a972526686ce75` |
| `source/desc/stability/terpsichore/equilibrium.py` | `0de6dd1270686e182ef1f3dabc2bc5585e9bb17853d8efbcb92a5cbc3a0a184b` |
| `source/desc/stability/terpsichore/vacuum.py` | `c7f8b3b9455e9fa6aeab7a56dbffed06ab4fba9f5f5037a6b8c5c1eb77c1b84b` |
| `source/desc/stability/terpsichore/external_region.py` | `1537df82d3d4b1809349a1659e2d545d71ce7a1e3fb1097f14eeb7b24f37bfdf` |
| `reproduce.py` | `caab15ea6aede756a4c0c5bb45588d429079e927036876e8e1f741681c438627` |
| `paper.md` | `4a29e559dfda9d18db2823e37ad84665d2c039c27432c532ed42cd855a9dd889` |

## Targeted helper retrieval checkpoint

The connected-input builder now follows statically bound Python helper calls (same-file functions,
relative imports and module aliases), reusing source checks and the AST scope index. Complete bodies,
call records and unresolved-call records are each stored once; packets reference their IDs. Calls
record actual/formal argument syntax, default values, return sites, branch context and any existing
caller operation/result IDs. These are candidate source connections, not runtime value-flow proofs.
Native retrieval is unchanged; this new resolver is Python-only. Decorated/dynamic/rebound targets
and expanded `*args`/`**kwargs` bindings remain unresolved rather than guessed.

Offline replay: `runs/evidence-helper-retrieval-final/`; receipt:
`results/evidence-helper-retrieval.json`. All six required functions are present together in a packet:
boundary extraction, input assembly, projection construction, scaled construction, metric computation
and payload assembly. Source body records are unique. Existing graph objects/operations/links are
unchanged. The receipt records 43 syntactic argument mappings and 20 unresolved argument mappings;
in particular `compute_vacmet_metrics(**inputs)` retains its source expression, not an invented
expansion of dictionary contents.

Assembly/retrieval from the saved graph/packet took 0.1604 seconds in this local check. This excludes
initial packet/graph construction, containers, model interpretation and repair. Saved JSON increased
from 432526 to 641846 bytes because missing implementations and relationships are now included;
scientific compression is still the next phase, not a result of this retrieval change. Earlier local
development replays are preserved under `runs/evidence-helper-retrieval-v1/` and `-v2/`.

Reproduce with `scripts/compare_evidence_packets.py`, the graph/packet/root paths in the receipt,
`--previous-input runs/evidence-packets-phase1-final/after.json`, a fresh `--output` directory, and
one `--require-function` argument for each function listed in `required_function_checks`. These
acceptance names are supplied only to the comparison script, never to the retrieval algorithm.
No model call, candidate execution, semantic-rule update, prompt/schema edit or repair run occurred.
