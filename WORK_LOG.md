# Implementation milestone ledger

Canonical live ledger. Approved plan: `RESEARCH_PLAN.md`. Only the primary agent updates this file.

| Milestone | Status | Verification / receipt |
| --- | --- | --- |
| 1. Reconcile approved protocol, establish package and restore pinned release | in progress | Preserve user files; verify source revisions and image references |
| 2. Implement evidence, graph contract, alignment and semantic rules | pending | Synthetic traceability, ambiguity, unit/scale and unsupported-syntax tests |
| 3. Implement bounded Codex/Pier controller and reproducible analysis | pending | Timeout/process-tree, checkpoint/fresh-session, patch and usage tests |
| 4. Verify container permissions and subscription integration | pending | No-model sandbox probe, then bounded subscription smoke |
| 5. Development pilot: 002 and 077, one attempt per condition | pending | Graphs, trajectories, patches, timing, usage and verifier receipts |
| 6. Final verification and handoff | pending | Clean test/install; independent summary recomputation; ledger/Git reconciliation |

Full 119-task evaluation follows pilot throughput review and the restricted-license decision. Old /tmp smoke artifacts are no longer available and are not reproducible receipts.

## Accepted decisions

- Exactly two conditions, both rerun with GPT-6 Astra/high: ordinary Codex and extraction then fresh repair.
- 1800 seconds total per trial; extraction cap 360 seconds including helpers/probes/handoff.
- One combined alignment, semantic lifting and propagation stage.
- Public scratch execution allowed; candidate source immutable during extraction.
- Repair may challenge inferred constraints with evidence.
- All 119 tasks remain the target population; unsupported mechanical regions are recorded.
- Development tasks 002/077. Prior private-test exposure on 002 must be disclosed.

## Coordination

Independent modules use separate worktrees from a verified commit; no concurrent writers share a checkout. Preserve user-owned `.serena/` and both PDFs. Primary agent integrates worker commits and updates this ledger.
