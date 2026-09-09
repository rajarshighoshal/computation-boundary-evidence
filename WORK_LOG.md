# Implementation milestone ledger

Canonical live ledger. Approved plan: `RESEARCH_PLAN.md`. Only the primary agent updates this file.

| Milestone | Status | Verification / receipt |
| --- | --- | --- |
| 1. Reconcile approved protocol, establish package and restore pinned release | complete | `eff036b`; pinned source and HF snapshot restored; `data/release-receipt.json`; `uv.lock` |
| 2. Implement evidence, graph contract, alignment and semantic rules | complete | Integrated commits `11ba626`, `44ea3c1`, `04faa4d`, `39a5f8c`; focused synthetic tests pass |
| 3. Implement bounded Codex/Pier controller and reproducible analysis | in progress | Analysis `432c629` integrated; controller/integration tests underway |
| 4. Verify container permissions and subscription integration | in progress | Native ARM64 Codex passes dummy sandbox checks inside unchanged amd64 task002 image; authenticated integration pending |
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

## Verified environment finding

Codex0.153.4 amd64 fails seccomp installation under this Apple Silicon host's emulation. The official ARM64 Linux binary, with its adjacent runtime resources, passes source/scratch/auth/network permission checks in the same pinned amd64 task image under default Docker security. Use host-native harness architecture for both arms and record it separately from scientific image architecture. No privileged container or security override is required.
