# Runtime status — 10 September 2026

The offline scientific-context prototype is implemented. A valid paired repair experiment has **not** completed. The development pilot is paused for a reproducible runtime incompatibility, not a scientific-method result.

## Verified

- Pinned release, dataset, task002/077 selection, native Codex assets and isolated Python helper dependencies are restored.
- `runs/subscription-smoke-v6` proves GPT-6 Astra/high through Codex 0.153.4 can execute a shell command and return its result using the subscription route: `42`, then `READY`; 19.05 seconds, successful descendant cleanup, no time overrun.
- The official verifier ran on that unchanged source. Its failure is expected for an unrepaired task; this smoke does not measure our method.
- `runs/pilot-v1` began 002/baseline, then was interrupted when the public reproduction hit our `/proc` restriction. The preserved candidate patch is empty; the other three trials were not run. See its `infrastructure-abort.json`.
- The two owned interrupted containers were stopped. New CLI cleanup verifies exact Compose ownership and records shutdown; it does not stop neighboring jobs by prefix.

## Remaining blocker

PySCF reads `/proc/<its-pid>/statm` for memory accounting. The current deny rule blocks it. Removing the rule does not establish a working alternative in this setup:

| Profile variant | Observed result |
| --- | --- |
| Root read with `/proc` denied | Ordinary Python starts; scientific process-memory access is denied |
| Root read with `/proc` readable | Native sandboxed process reports PID2, but `/proc` shows outer-container PIDs; own `statm` is absent. Rosetta Python exits133 resolving `/proc/2/exe` |
| Minimal runtime reads | Python starts, but `/proc` is absent; PySCF fails |
| Minimal runtime plus explicit `/proc` read | Same process-namespace mismatch and Rosetta startup failure |

Executable-link denial did not solve this; legacy Landlock rejected the required split permissions. No sandbox bypass, scientific-source modification or Docker configuration change was used. Dummy credential-access tests remained denied, but that alone does not establish scientific-runtime usability.

Exact observations, image digests and diagnostic scripts are retained in `runs/preflight-native/proc-compatibility.receipt.json` and its referenced files. The native static probe also fails process accounting, so this is **not proven to be exclusively an architecture-emulation problem**. Moving to another machine must be tested, not assumed to fix it.

The preflight now requires `/proc/self` to resolve to the actual command PID and readable numeric `statm`, before uploading subscription credentials. Known-bad setups fail before a model run.

## Next decision

Test a different supported execution setup—preferably an available native Linux x86-64 host—or resolve the pinned Codex sandbox's process-filesystem behavior. First run the no-model scientific/process/credential checks there. Any harness-version change must be recorded and applied equally to both conditions before restarting the pilot in a fresh run directory.

The local Docker VM also exposes only 4,109,914,112 bytes versus each task's 8192 MiB request. Resolve resource allocation before locked evaluation. No full-benchmark launch is authorized by these development checks.

Once preflight passes, four serial trials allow two hours of agent time plus setup and verification. The runtime fix itself does not yet have a reliable ETA.
