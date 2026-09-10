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
| 7. Implement compact annotations and code-owned evidence preparation/assembly | complete | Packet and compiler integrated from isolated worktrees; source references, quotes, hashes and actual expression trees are code-owned; contract in `docs/EXTRACTION_V2.md` |
| 8. Integrate bounded phases and independent parallel work | complete | Preparation/interpretation overlap; two bounded probes can run concurrently; interpretation stops before code-owned assembly/handoff; standard Pier retained, no duplicate graph final response |
| 9. Verify revised extractor and document handoff | complete | `runs/extractor-annotations-v1`: both development checks finished cleanly with valid graphs, short acknowledgements and recorded token use; no repairs/private verification. Programmatic report `docs/EXTRACTOR_VERIFICATION.md`; bounded shutdown fix covered by deadline tests. Old pilot independently rechecked unchanged; plan/docs updated; no running containers or full benchmark |
| 10. Freeze a random five-task comparison cohort | complete | `8790658` freezes seed/population/draw: 091, 058, 009, 114, 001 from 94 eligible tasks; separate release receipt preserves development selection; public TOML/Dockerfile checks and dry-run schedule verified; 289 tests pass |
| 11. Run initial random-five checks | complete after scope revision | `runs/random-five-v1` high-effort checks on 091/058 completed. User requested medium/native-read-only simplification for later initial checks; operator stop caught 009 during image pull, before model inference. Receipts/audit: `operator-stop-request.json`, `results/random-five-v1-high.json`, `docs/RANDOM_FIVE_HIGH_RESULTS.md`. No benchmark containers remain running |
| 12. Simplify extraction and lower effort | complete | Integrated `d3e2ff4`; 313 tests pass. Native ARM Codex read-only reads taskfile and rejects writes; no-model receipt `runs/readonly-native-preflight/receipt.json`. Medium remaining-task config dry-run verified. Code saves final JSON/scripts; Git guard removed; native CLI only for extraction, repair unchanged. No custom permission framework |
| 13. Continue remaining selected initial checks | complete | `runs/random-five-medium-resume-v1` completed114/001 pairs atmedium with the old method unchanged. Previous quota-failedlaunch retained. All original selectedtask pairs nowhave outcomes; no API fallback or completed-pair reruns |
| 14. Verify and report available initial checks | complete | High and medium pre-quota summaries independently reconstructed; available patch hashes checked; incomplete schedules explicit. Generated reports `docs/RANDOM_FIVE_HIGH_RESULTS.md` and `docs/RANDOM_FIVE_MEDIUM_RESULTS.md` now include audited reasoning-token subsets. Original cohort continuation is tracked in13/15 |
| 15. Verify resumed checks and reconcile the original cohort | complete | All original pairs audited with patch hashes and token subsets. `docs/INITIAL_FIVE_OVERVIEW.md` / `results/initial-five-overview.json` preserve versions and both interrupted/quota receipts. No expanded sample launched |
| 16. Discuss a better scientific extractor | complete | `docs/EXTRACTOR_NEXT_PROPOSAL.md` records concrete retrieval/grammar/binding failures and a bounded task-local scientific-contract design with falsification checks. User then requested parallel implementation; existing live method remains unchanged |
| 17. Implement improved extractor in isolated worktrees | complete and integrated | Retrieval, preserved syntax, scoped bindings and dependency handoff integrated through`94f940a` after old checks stopped. Source hashes match live-tested worktree`d317bdd`. No extra interpretation sessions/production guards |
| 18. Verify improved extractor and hand off | complete | 371 tests passed; independent review findings corrected. Original public-source mechanism receipts preserved in`runs/task-local-development/verified-final` and`results/task-local-mechanism.json`. Remaining binding/scientific limitations documented; no new-method repair comparison or expanded sample run |
| 19. Test redesigned extraction with the model | complete | `runs/extractor-task-local-check-v1`: both091/009 extraction-only checks completed atmedium with usablegraphs within360s; no repairs/hidden tests. Audited report`docs/EXTRACTOR_TASK_LOCAL_CHECK.md`; input/output/reasoning checked independently against session counters. All containers stopped |

Full 119-task evaluation follows pilot throughput review and the restricted-license decision. Smoke failures are infrastructure development, not scientific-method outcomes. Initial-session /tmp artifacts are no longer available; current-session native probe files must be copied to durable receipts before handoff.

## User-directed simplification

The user explicitly rejected the extra sandbox layer and requested standard tools with only the scientific-context intervention added. Docker becomes the execution isolation boundary, using the documented Codex container invocation. Do not build another sandbox or credential broker. Keep authentication temporary and out of image builds/Git, but do not claim it is unreadable to commands inside the same container. Use separate extraction/repair task copies and evidence validation for the experimental handoff.

## Accepted decisions

- Exactly two conditions: ordinary Codex and extraction then fresh repair. Historical runs use GPT-6 Astra/high; current initial-check continuation uses medium by user request.
- 1800 seconds total per trial; extraction cap 360 seconds including helpers/probes/handoff.
- One combined alignment, semantic lifting and propagation stage.
- Native Codex read-only extraction; code saves outputs and executes declared public scratch probes. Repair uses a separate original candidate; no Git source-change guard.
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

## Random-five preflight

Frozen cohort/config: `configs/random-five-v1.selection.json` and `configs/random-five-v1.json`.
Materialized release: `data/random-five-v1-release.json`; original development receipt preserved.
Public Dockerfiles declare CPython 3.11/3.12, within helper support; actual guest versions remain
runtime checks. Every selected task requests 2 CPUs, 8192 MiB memory and 20480 MiB storage.
Task 058 has an empty TOML `base_commit_hash` despite a populated original source hash in public
metadata and the release receipt; guest Git HEAD will be recorded independently. No image-private
assertions or comparative outcomes were inspected for selection. Sampling exclusions were only
restricted licenses and development IDs 002/077, with no domain/language filter or reroll.
