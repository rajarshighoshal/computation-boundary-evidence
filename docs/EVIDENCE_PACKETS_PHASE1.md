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
