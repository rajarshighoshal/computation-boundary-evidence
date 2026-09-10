# Implementation milestone ledger

Canonical live ledger. Approved plan: `RESEARCH_PLAN.md`. Only the primary agent updates this file.

| Milestone | Status | Verification / receipt |
| --- | --- | --- |
| 1. Reconcile approved protocol, establish package and restore pinned release | complete | `eff036b`; pinned source and HF snapshot restored; `data/release-receipt.json`; `uv.lock` |
| 2. Implement evidence, graph contract, alignment and semantic rules | complete | Integrated commits `11ba626`, `44ea3c1`, `04faa4d`, `39a5f8c`; focused synthetic tests pass |
| 3. Simplify runner to standard Codex-in-Docker plus the research intervention | complete | Reuses upstream Pier Codex.run; removed custom profiles, permission probes and subreaper supervisor; 212 remaining tests pass |
| 4. Verify standard runner and scientific execution | complete | `runs/standard-smoke-v1`: normal process/PySCF check passes; actual Codex PySCF command returns 42/READY, smoke_success true, 23.68s; verifier finishes on unchanged source |
| 5. Development pilot: 002 and 077, one attempt per condition | complete | `runs/pilot-v2`: both arms passed all verifiers. Exact outcomes and times in `results/pilot-v2.json`; frozen implementation `62e4583`; old interrupted pilot-v1 preserved separately |
| 6. Verify and report pilot outcomes | complete | Independent summary reconstruction and patch hashes verified; `scripts/report_pilot.py` generates quantitative report from receipts; tests pass; no running containers. Stopping-rule proposal recorded but not implemented. No full-benchmark launch |
| 7. Implement compact annotations and code-owned evidence preparation/assembly | in progress | User approved bounded hybrid extractor; contract in `docs/EXTRACTION_V2.md`. Preserve the evaluated pilot and existing scientific-analysis modules |
| 8. Integrate bounded phases and independent parallel work | pending | Standard Pier Codex retained; interpretation sub-deadline, code-owned probes/checks, short final acknowledgement, no duplicate graph JSON |
| 9. Verify revised extractor and document handoff | pending | Unit/integration tests, bounded extraction-only development check, programmatic receipts, plan/docs/Git reconciliation. No new repair pilot or full benchmark in this step |

Full 119-task evaluation follows pilot throughput review and the restricted-license decision. Smoke failures are infrastructure development, not scientific-method outcomes. Initial-session /tmp artifacts are no longer available; current-session native probe files must be copied to durable receipts before handoff.

## User-directed simplification

The user explicitly rejected the extra sandbox layer and requested standard tools with only the scientific-context intervention added. Docker becomes the execution isolation boundary, using the documented Codex container invocation. Do not build another sandbox or credential broker. Keep authentication temporary and out of image builds/Git, but do not claim it is unreadable to commands inside the same container. Use separate extraction/repair task copies and evidence validation for the experimental handoff.

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

## Earlier implementation (superseded)

The earlier nested-sandbox implementation encountered seccomp and process-filesystem problems and was removed at the user's direction. Its diagnostic receipts remain preserved, but those checks and architecture workarounds are not requirements of the current standard runner. The current runner uses the normal Linux x64 binary in the amd64 scientific image.

Retained integration details: use the adapter import without a conflicting built-in agent name; pin the Codex binary and isolated helper dependencies; reuse upstream authentication and proxy handling. Old diagnostics are under `runs/preflight-native`.

Docker exposes 4,109,914,112 bytes while the development tasks request 8192 MiB. Do not claim provisioned-resource parity with the benchmark's published runs. This is a development feasibility pilot; retain resource failures, and resolve host allocation before locked evaluation.

The standard-runner smoke exercises the exact PySCF operation blocked by the discarded policy. No scientific method tuning or comparative-outcome selection was performed in response to the old infrastructure failure.
