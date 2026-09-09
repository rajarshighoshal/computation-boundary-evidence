# Implementation milestone ledger

Canonical live ledger. Approved plan: `RESEARCH_PLAN.md`. Only the primary agent updates this file.

| Milestone | Status | Verification / receipt |
| --- | --- | --- |
| 1. Reconcile approved protocol, establish package and restore pinned release | complete | `eff036b`; pinned source and HF snapshot restored; `data/release-receipt.json`; `uv.lock` |
| 2. Implement evidence, graph contract, alignment and semantic rules | complete | Integrated commits `11ba626`, `44ea3c1`, `04faa4d`, `39a5f8c`; focused synthetic tests pass |
| 3. Implement bounded Codex/Pier controller and reproducible analysis | complete | Includes `596b352`, `26cb2bd`; 224 tests passed/5 Linux-only skipped; isolated locked install tested; timeout/provenance/summary and exact-container cleanup audits integrated |
| 4. Verify container permissions, subscription and scientific-runtime integration | blocked: execution setup decision required | Basic subscription smoke v6 passes (42/READY, 19.05s, cleanup complete). No scientifically usable credential-safe `/proc` policy verified after bounded root/minimal/read/deny/legacy probes; see `docs/RUNTIME_STATUS.md` and `runs/preflight-native/proc-compatibility.receipt.json` |
| 5. Development pilot: 002 and 077, one attempt per condition | blocked by milestone 4 | `runs/pilot-v1`: 002/baseline interrupted, empty patch retained, other three trials not run. No valid paired result. Restart in a fresh directory only after corrected runtime preflight; preserve old attempt |
| 6. Verify current implementation and hand off exact remaining work | complete for this blocked handoff | Fresh locked environment: 224 passed/5 skipped; durable Linux supervisor receipt: 17 passed. Independent recomputation verifies smoke-v6 and aborted-pilot summaries. Docker has no running containers. End-to-end scientific evaluation remains explicitly unfinished in milestones 4/5 |

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

Milestone 4 scope explicitly reopened after the first public scientific computation: trivial shell and file-policy smoke is insufficient to establish compatibility with scientific libraries. No method tuning or comparative-outcome selection was performed in response to the aborted trial.
