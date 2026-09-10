# Runtime status — standard runner

The earlier `/proc` blocker is resolved by removing the custom nested sandbox. A different Linux machine was not needed for this check.

The adapter calls upstream Pier 0.3.0 `Codex.run` for both passes, preserving authentication, proxy handling, session logs and cleanup. The existing small launcher replaces Pier's bypass flag with Codex's native read-only option only for extraction; repair is unchanged. Codex returns compact annotations through its final-message file; code saves annotations/scripts and performs preparation, assembly and probes.

## Verified on the same Mac

`runs/standard-smoke-v1` records Codex 0.153.4, Linux x64 in the pinned amd64 task002 image, GPT-6 Astra/high:

- Normal container process-memory access and `pyscf.lib.current_memory()` passed.
- The actual Codex agent successfully executed that PySCF call, printed `42`, and returned `READY`.
- The agent phase completed in 23.68 seconds with `smoke_success: true`.
- 212 remaining tests pass, including tests proving the adapter inherits upstream `Codex.run` and its authentication/launch behavior.

The smoke itself is not a repair result. The subsequent four-trial `runs/pilot-v2` is now complete: both conditions passed tasks002/077, with no observed success gain and higher elapsed time for context. See [pilot results](PILOT_RESULTS.md). The old `runs/pilot-v1` interrupted attempt and earlier diagnostic receipts remain preserved separately.

## Boundaries and next step

Docker supplies isolation, following [OpenAI's documented container approach](https://learn.chatgpt.com/docs/agent-approvals-security#run-codex-in-dev-containers). Temporary authentication stays outside source and image builds, but is accessible to commands inside the same container. No custom credential-isolation claim is made.

The extractor runs in native read-only mode on a disposable copy. The Git source-change rejection is removed: in the initial OpenMC check, a Git line-ending warning was mistaken for a changed filename. Repair starts from a separate original copy. GNU timeout covers normal foreground process groups, not deliberately detached children.

The high-effort initial checks were stopped at the user's request after the active pair finished, before further inference; see [the generated initial report](RANDOM_FIVE_HIGH_RESULTS.md). The user explicitly treats these as feasibility checks, not the locked experiment. Remaining drawn tasks use medium effort and the simplified output/read-only revision. Mechanical coverage remains limited, and Docker allocation still needs review before locked evaluation. No full-benchmark run has been launched.

## Native read-only compatibility

`runs/readonly-native-preflight/receipt.json` preserves no-model CLI checks with the pinned binary
hashes, exact commands, image digest and raw output. Under this Mac's emulated amd64 Docker image,
the x64 sandbox fails while installing seccomp; the native ARM build reads the public task file
and denies a write. Extraction therefore uses the native build on ARM Docker hosts; repair and
the scientific image remain x64/amd64. This is a standard CLI option, not a custom permission
profile or sandbox implementation. The installed CLI's diagnostic syntax is `codex sandbox
COMMAND`, without the platform subcommand shown in current online examples.

OpenAI Docs was used to check [native read-only options and container limitations](https://learn.chatgpt.com/docs/agent-approvals-security).
The actual pinned CLI and saved execution receipts determine local feasibility. Scientific probes
are code-owned executions after annotation, not model-generated commands inside the read-only phase.

The actual task009 extraction session also records medium effort, read-only sandbox policy and
approval policy `never`; its delivered graph and completed repair are preserved in the
[medium initial-check report](RANDOM_FIVE_MEDIUM_RESULTS.md). After the user restored quota, the
remaining task pairs completed; the failed quota receipt remains preserved. The
[initial-cohort overview](INITIAL_FIVE_OVERVIEW.md) consolidates the completed outcomes without
claiming a uniform controlled experiment.

The task-local prototype was implemented in isolated worktrees while those old runs continued,
then integrated. Its original-source checks and separate [model extraction checks](EXTRACTOR_TASK_LOCAL_CHECK.md)
completed without repair or hidden-test execution. The integrated source hashes match the tested
worktree. No benchmark containers remain active; a new repair comparison is a subsequent decision.

The subsequently requested full comparison stopped at the user's instruction after initial graph
assembly hit a premature internal sub-limit. The fix now uses the remaining shared extraction work
budget while retaining the outer cleanup reserve. The exact saved failure was reproduced and fixed
without a model call, then a user-approved full extraction-only check completed with a non-empty
source-backed graph within its cap. See [replay](ASSEMBLY_TIMEOUT_FIX.md) and
[bounded check](ASSEMBLY_BUDGET_CHECK.md). This does not guarantee scientific usefulness; direct
expression matching remained unresolved in the smoke. Comparisons have not restarted.
