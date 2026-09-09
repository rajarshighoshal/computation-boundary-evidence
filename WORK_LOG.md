# Implementation milestone ledger

Canonical live ledger. Approved plan: `RESEARCH_PLAN.md`. Only the primary agent updates this file.

| Milestone | Status | Verification / receipt |
| --- | --- | --- |
| 1. Reconcile approved protocol, establish package and restore pinned release | complete | `eff036b`; pinned source and HF snapshot restored; `data/release-receipt.json`; `uv.lock` |
| 2. Implement evidence, graph contract, alignment and semantic rules | complete | Integrated commits `11ba626`, `44ea3c1`, `04faa4d`, `39a5f8c`; focused synthetic tests pass |
| 3. Implement bounded Codex/Pier controller and reproducible analysis | complete | Through `596b352`; 210 tests passed/5 Linux-only skipped; fresh locked install succeeds; timeout/provenance/summary audit integrated |
| 4. Verify container permissions and subscription integration | complete | Smoke v6: native permission checks pass; GPT-6 Astra executes shell (42), replies READY; 19.05s, cleanup complete, no overrun. `runs/subscription-smoke-v6`; earlier failed attempts retained |
| 5. Development pilot: 002 and 077, one attempt per condition | in progress | Start after smoke verifier finishes; retain graphs, trajectories, patches, timing, usage and verifier receipts |
| 6. Final verification and handoff | pending | Clean test/install; independent summary recomputation; ledger/Git reconciliation |

Full 119-task evaluation follows pilot throughput review and the restricted-license decision. Smoke failures are infrastructure development, not scientific-method outcomes. Initial-session /tmp artifacts are no longer available; current-session native probe files must be copied to durable receipts before handoff.

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

Integration corrections: use custom Pier import without built-in agent name; pre-create upload parent; normalize copied marker/auth ownership to guest uid; pin typing-extensions in the isolated helper closure; forward Pier service-proxy environment only to the client and filter it from tool commands. Native dummy receipts are preserved under `runs/preflight-native`.

Docker exposes 4,109,914,112 bytes while the development tasks request 8192 MiB. Do not claim provisioned-resource parity with the benchmark's published runs. This is a development feasibility pilot; retain resource failures, and resolve host allocation before locked evaluation.
