# Runtime status — standard runner

The earlier `/proc` blocker is resolved by removing the custom nested sandbox. A different Linux machine was not needed for this check.

The adapter calls upstream Pier 0.3.0 `Codex.run` for both passes. It reuses the standard Codex command, subscription authentication, proxy handling, session logs and cleanup. A plain final-message file and a small GNU-timeout launcher are retained. The current extractor adds bounded code-owned preparation, assembly and probes around compact LLM annotations; the existing alignment/lifting/propagation checks are reused.

## Verified on the same Mac

`runs/standard-smoke-v1` records Codex 0.153.4, Linux x64 in the pinned amd64 task002 image, GPT-6 Astra/high:

- Normal container process-memory access and `pyscf.lib.current_memory()` passed.
- The actual Codex agent successfully executed that PySCF call, printed `42`, and returned `READY`.
- The agent phase completed in 23.68 seconds with `smoke_success: true`.
- 212 remaining tests pass, including tests proving the adapter inherits upstream `Codex.run` and its authentication/launch behavior.

The smoke itself is not a repair result. The subsequent four-trial `runs/pilot-v2` is now complete: both conditions passed tasks002/077, with no observed success gain and higher elapsed time for context. See [pilot results](PILOT_RESULTS.md). The old `runs/pilot-v1` interrupted attempt and earlier diagnostic receipts remain preserved separately.

## Boundaries and next step

Docker supplies isolation, following [OpenAI's documented container approach](https://learn.chatgpt.com/docs/agent-approvals-security#run-codex-in-dev-containers). Temporary authentication stays outside source and image builds, but is accessible to commands inside the same container. No custom credential-isolation claim is made.

The extractor runs on a disposable copy; detected source edits invalidate its graph handoff. Repair starts from a separate unchanged copy. GNU timeout covers normal foreground process groups, not deliberately detached children.

The bounded annotation-based extractor is now implemented and has passed separate extraction-only checks; see [the generated verification report](EXTRACTOR_VERIFICATION.md). No new repair comparison has been run for this revision. Mechanical coverage remains limited, and Docker allocation still needs review before locked evaluation. No full-benchmark run has been launched.
