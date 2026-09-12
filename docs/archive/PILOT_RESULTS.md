# Development pilot: results

Baseline succeeded on 2/2 tasks; context succeeded on 2/2. This development pilot is too small for a general effectiveness claim.

## Verifier outcomes and time

| Task | Baseline private tests | Context private tests | Baseline minutes | Context minutes |
| --- | --- | --- | ---: | ---: |
| 002 | 8/8 | 8/8 | 11.8 | 17.1 |
| 077 | 13/13 | 13/13 | 5.9 | 14.3 |

All public checks passed: True. Official rewards: 002/baseline=1, 002/science=1, 077/baseline=1, 077/science=1.
Paired success difference: 0.0 percentage points on 2 pairs. No significance claim is made.

Times are measured agent-phase totals, including extraction/handoff where applicable, excluding environment preparation and official verification. Aggregate time was 17.75 minutes for baseline and 31.36 for context (76.6% more). The full serialized pilot took 61.22 minutes. Trials exceeding the total allowance: 0.

## Extraction and mechanical coverage

### Task 002

Extraction status: `timeout` after 337.25s; handoff: `usable_graph`. Source changed: False. Graph nodes: 11 claims, 18 quantities, 16 evidence, 3 observations.
Source-corroborated implementation expressions: 2. Alignments: 1 matching, 1 differing, 9 unknown. Supported semantic lifting: 1; dimensions resolved: 9; scales resolved: 4; shapes resolved: 9.

### Task 077

Extraction status: `timeout` after 336.88s; handoff: `usable_graph`. Source changed: False. Graph nodes: 10 claims, 11 quantities, 13 evidence, 6 observations.
Source-corroborated implementation expressions: 1. Alignments: 1 matching, 0 differing, 9 unknown. Supported semantic lifting: 0; dimensions resolved: 0; scales resolved: 0; shapes resolved: 2.

These counters are not correctness proofs. They include properties propagated through LLM-supplied scientific relations, not only implementation expressions. In the physics case, the threshold dimensional conflict was partly a literal-representation limitation, explicitly qualified in the graph. In geometry, only an alias was source-corroborated; the underlying engine was opaque to the index.

Both geometry repairs independently implemented exact integer-lattice geometry. Baseline preserved modern-engine dispatch; context used its local implementation throughout. Both physics repairs addressed units and spin-density handling; context additionally parsed electronic-state metadata. These descriptive differences do not establish causal benefit or superiority.

## Timing and measurement limitations

The saved checkpoints were usable despite extraction cutoffs. Asking the extractor to repeat the full graph as its final response duplicates a validated artifact. A firmer stopping rule and a short checkpoint identifier are proposed before increasing the cap; see [pilot notes](PILOT_NOTES.md). No such change was applied mid-pilot.

Full context-condition input-token totals are unavailable for 2/2 trials, because interrupted extractions emitted no completed-turn totals. Unknown is not zero; repair-only usage must not be presented as total method cost. Raw sessions are preserved. Fail2Pass/Pass2Pass remain unavailable without matching original-baseline per-test records.

## Protocol and evidence

Evaluated task IDs: **002, 077**. Both are development cases; prior private-test exposure: 002.
Model: gpt-6-astra/high; Codex 0.153.4; Pier 0.3.0. Total allowance 1800s; extraction cap 360s including validation/handoff. Attempts per condition: 1; concurrency: 1.
Order: 002/baseline → 002/science → 077/science → 077/baseline.
Evaluated implementation: `62e4583a32d15ddd8382be2f262fedcfbd8d3498`. Prompts/settings were unchanged during the pilot. Standard Docker execution and subscription auth were used; no API-key fallback.

Pinned dataset/benchmark revisions, images, prompt/config hashes and exact trial paths are in [the committed summary](../results/pilot-v2.json). Raw records remain under `runs/pilot-v2/`; the earlier interrupted pilot is preserved separately and not pooled. No full-benchmark run was started.

Docker exposed 3.83 GiB versus the task's requested 8 GiB. Successful development runs do not establish full-benchmark resource feasibility or parity with published runs.

Independent reconstruction verified 4 trials and 2 pairs; all candidate patch hashes were checked. This document's quantitative text and tables are generated from the preserved records.

```bash
uv run --no-sync python scripts/report_pilot.py
```
