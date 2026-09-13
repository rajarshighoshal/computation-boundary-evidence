# Concurrency, cloud feasibility and scientific-design review

Read-only review of checkpoint `c6b973d`. No instance rented, no benchmark run started/stopped,
and no method/configuration edits. Budget clarified by Rajarshi: **USD 2 total for cloud VMs**;
he already has a Hetzner account. Desired throughput is continuously occupied worker slots,
eventually 20–30 simultaneous attempts, not barriers between groups.

Reproducible diagnostics: `scripts/review_concurrency.py`; measured inputs, source hashes,
synthetic counterexamples and counterfactual timing calculations:
`results/concurrency-review-2026-09-13.json`.

## Recommendation

First replace batch admission with a rolling pool in a separately approved revision. Keep each
attempt's tools sequential unless independent, but admit another task when an entire attempt
finishes. Prefetch only a bounded number of upcoming task images; currently every group's pulls
finish before any of that group's agents starts. These changes target idle time without buying
hardware. Do not modify the already running process or silently restart completed attempts.

A native x86 Linux VM avoids the current ARM-to-amd64 execution path, but cannot accelerate remote
DeepSeek inference. Do not promise a numerical native speedup without a same-task measurement.
Docker warns that emulation can particularly slow compilation and compression:
[Docker multi-platform documentation](https://docs.docker.com/build/building/multi-platform/).

For this very small budget, the conditional candidate is **Hetzner CX53 in Germany/Finland**:
16 shared x86 vCPUs, 32 GB RAM, 320 GB NVMe. Its published base hourly price is USD 0.0561;
the diagnostic receipt calculates a 24-hour base bill of USD 1.3464. Tax, Primary IPv4 and any
extra services are excluded. **The public product page currently marks it unavailable**;
console inventory and the actual all-in quote must be checked. This is not a guaranteed offer.
[Specifications/availability](https://www.hetzner.com/cloud/cost-optimized/),
[current published price adjustment](https://docs.hetzner.com/general/infrastructure-and-availability/price-adjustment/).

Do not treat this as a reliable 20–30-worker machine. A provisional modest worker count must be
tested against actual peak memory, CPU and I/O, not idle container RSS or memory limits. If the
cheap tier is unavailable, do not substitute a much more expensive VM without approval. With this
budget, fixing local slot utilization is preferable to spending the whole allocation on a large
VM's setup/download period. Keep DeepSeek API costs separate from VM costs.

Export all run artifacts before deleting a cloud instance. Powering it off does not stop charges;
remaining paid Primary IPs are billed separately. Budget alerts are not hard spending caps.
[Hetzner billing](https://docs.hetzner.com/cloud/billing/faq/).

Runpod CPU pods are not a drop-in replacement for this Pier/Docker Compose architecture: Runpod's
current Docker-runtime CPU pods do not support Docker-in-Docker. A VM with its own Docker daemon
fits this code; a GPU pod is unnecessary because inference is remote.
[Runpod's CPU runtime change](https://www.runpod.io/blog/enhanced-cpu-pods-docker-network).

## Concurrency evidence and limits

- `cli.py:485–533` is a group barrier, not a rolling queue. Staggering startup does not fix it.
- Docker is configured with fewer CPUs/RAM than the host total; exact live readings are in the
  receipt. Idle task containers and egress proxies have different footprints. The task's 8 GiB
  setting is a limit, not reservation; neither summing limits nor extrapolating idle RSS proves
  a safe concurrency level. Heavy tracers, compilers, solvers and verifiers can overlap.
- The timing receipt replays completed development-job durations through batch and rolling
  schedules. It is a counterfactual, not a cloud benchmark. Its full-cohort service-time bounds
  assume that small development sample represents the full benchmark, which is unestablished.
  More workers cannot shorten the longest individual attempt's sequential reasoning chain.
- DeepSeek documents account-level concurrency far above the present local worker count, but
  also describes queuing and keep-alive behavior. More keys do not independently multiply an
  account's quota. Per-request latency and observed errors still matter.
  [DeepSeek rate limits](https://api-docs.deepseek.com/quick_start/rate_limit/).
- Current session JSONL records completed API steps, not token-level network streaming, and lacks
  enough per-step timing to precisely separate API wait from shell work. Do not claim measured
  API-versus-CPU percentages from those logs.

## What is genuinely scientific now

The newer pipeline is materially closer to the research hypothesis: execute the public workflow,
record quantities and transformations, derive relationship candidates, connect these to source
locations, then let the LLM attach conventions/assumptions. The code contributes behavioral
evidence rather than only a list of names. Sibling implementations can supply evidence for a
convention that a failure observation alone leaves ambiguous.

However, **observed behavior, inferred relationship and scientifically required relationship are
different claims**. Input changes need not always change output; a boundary difference need not
be an error; a successful exit does not establish scientific correctness. Required invariance,
sensitivity or continuity needs an explicit predicate, convention and applicability conditions.
Native process observations provide coarse execution coverage, not universal scientific understanding.

### Reproduced correctness issues

1. **Lossy fingerprints masquerade as equality.** `fingerprint.py` hashes summary statistics for
   large arrays; `relations._same` accepts the resulting matching `content` digest and
   `_output_relation` calls it `identical`. The diagnostic swaps two interior values in an array:
   different arrays, matching summaries, reported identical. This can manufacture sensitivity or
   collapse findings. Summary equality should be labelled summary agreement/unknown, not exact
   equality. Sampled comparison can disprove equality but cannot prove full equality.
2. **Field names are mistaken for predicates.** A synthetic successful report with `collapse: false`
   is classified as a violated distinctness constraint. A nonzero `boundary_difference` is classified
   as violated continuity without a supplied expected value or tolerance. The code should preserve
   the actual predicate and polarity; a naming heuristic must remain an explicitly tentative candidate.
3. **The advertised static fallback is not reached on trace exceptions.** In `prepare`, the initial
   trace helper call is outside the exception handler. A synthetic trace failure exits before the
   packet helper is called. The diagnostic confirms this; a larger VM does not repair that control flow.

These are small evidence-contract corrections, not a reason to build a new framework or formal prover.
The latest development receipts also do not establish that convention guidance reliably fixes DESC:
the later iteration again failed that case. Keep iterations separate and avoid causal certainty from
one stochastic success. “No patch found yet” for autochem is not proof the task is unsolvable.

## Other pipeline issues before scaling

- **Cost missingness:** `scripts/cost_report.py` maps absent usage to zero. With mixed recorded and
  missing cache splits, the global fallback can omit part of input cost. Require complete per-stage
  accounting or label partial/lower-bound totals; do not call an incomplete number an exact bill.
  Current official DeepSeek pricing could not be fetched reliably in this review, so the script's
  rate constants have not been independently revalidated here.
- **Configuration fidelity:** `reasoning_effort` is recorded but not passed in `_api_completion`.
  Current DeepSeek documentation says the default is high, so this is not evidence that these runs
  used the wrong effort. It is a reproducibility issue for future configuration changes. Also,
  temperature is ignored in thinking mode; setting zero does not make the experiment deterministic.
  [DeepSeek thinking-mode documentation](https://api-docs.deepseek.com/guides/thinking_mode/).
- **Frozen source:** snapshotting helpers/prompts fixes the previous container-input drift. The host
  agent is still imported from the live checkout; the HEAD check does not detect all uncommitted
  source changes. Use one immutable execution checkout. Do not commit even report changes into its
  HEAD while the current launcher is active: the next attempt checks that HEAD has not moved.
- **Linux portability:** the launch shell script is Mac-specific, contains an absolute Mac path,
  Docker Desktop restart commands and deletion of a prior run directory. Do not run it unchanged
  on a VM. Recreate the Linux virtualenv and rebase selection paths without altering pinned task
  contents. Use fresh output names and preserve receipts; avoid broad pruning on a shared daemon.
- **Inference comparison:** keep both arms of a task on the same hardware/resource class, retain
  extraction in the treatment budget, and disclose wall-clock matching versus token differences.
  Disjoint task sharding needs declared IDs and one attempt per arm; do not duplicate active work.

## Minimal next sequence, requiring approval to implement

Correct the two scientific-evidence labels and trace fallback; implement rolling admission; verify
with offline counterexamples and a bounded existing-workload capacity check. Then freeze one source
version before scaling. Check the cheap VM's stock and all-in quote only if it would save enough
time to justify migration. No purchase, runtime change or new outcome-producing run is authorized
by this review itself.
