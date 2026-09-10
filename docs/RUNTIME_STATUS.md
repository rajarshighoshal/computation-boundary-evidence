# Runtime status — standard runner

The earlier `/proc` blocker is resolved by removing the custom nested sandbox. A different Linux machine was not needed for this check.

The adapter now calls upstream Pier 0.3.0 `Codex.run` for both passes. It reuses the standard Codex command, subscription authentication, proxy handling, session logs and cleanup. The only execution additions are output-file/schema flags and a small GNU-timeout launcher for the experiment's time allowance. The scientific extraction, alignment, semantic lifting and propagation code is unchanged.

## Verified on the same Mac

`runs/standard-smoke-v1` records Codex 0.153.4, Linux x64 in the pinned amd64 task002 image, GPT-6 Astra/high:

- Normal container process-memory access and `pyscf.lib.current_memory()` passed.
- The actual Codex agent successfully executed that PySCF call, printed `42`, and returned `READY`.
- The agent phase completed in 23.68 seconds with `smoke_success: true`.
- 212 remaining tests pass, including tests proving the adapter inherits upstream `Codex.run` and its authentication/launch behavior.

This is an infrastructure smoke, not a repair result. No valid paired research pilot has completed yet. The old `runs/pilot-v1` interrupted attempt and earlier diagnostic receipts remain preserved and are not counted as comparative method results.

## Boundaries and next step

Docker supplies isolation, following [OpenAI's documented container approach](https://learn.chatgpt.com/docs/agent-approvals-security#run-codex-in-dev-containers). Temporary authentication stays outside source and image builds, but is accessible to commands inside the same container. No custom credential-isolation claim is made.

The extractor runs on a disposable copy; detected source edits invalidate its graph handoff. Repair starts from a separate unchanged copy. GNU timeout covers normal foreground process groups, not deliberately detached children.

Next is the four-trial development pilot in a fresh directory, with the existing model and time allowances. Docker still exposes about 4 GB versus the tasks' requested 8 GiB; increase allocation before locked evaluation. No full-benchmark run is launched by the smoke check.
