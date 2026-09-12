# Scientific feedback: implementation verification

Verified source revision: `a0a7e20e7affad47dcc872fb5093f49fef36f7d6`. Benchmark-agent calls: 0.

| Check | Result |
| --- | --- |
| Full local suite | 475 tests; 0 failures; 0 errors; 0 skipped |
| Preserved original-source check | Passed: 091, 009 |
| Historical token audit | 15 stages unchanged |
| Historical comparison reconstruction | Unchanged |
| Numerical/discrete feedback integration | Passed using deterministic model test doubles and actual local public probes |
| Parallel scheduler | Local process overlap, pair barrier, failure/interrupt and cache-serialization tests passed |

The original-source check initially failed because added entity entries crowded a later referenced computation out of the bounded index. The exact pre-fix failure was replayed and preserved. Selection now shares the fixed cap across referenced regions; the assertion and task list were not weakened.

New source bindings distinguish carriers from expression operands. Feedback, unchanged-probe identity, stale-result rejection, draft fallback, native read-only routing, provider failures and cancellation are covered. Draft and revision costs are summed without counting cached input or reasoning twice.

Parallel mode permits two simultaneous trials. Full comparisons wait for both arms of a task before advancing; extraction-only checks group two tasks. Both share Docker resources; configured per-task memory limits are not reservations.

These checks establish implementation behavior, not improved scientific meaning or repair success. Live extraction quality and actual parallel resource pressure remain untested.

## Reproduction

```bash
.venv/bin/pytest -q --junitxml=runs/semantic-feedback-verification-reproduction/pytest.xml
.venv/bin/python scripts/check_task_local_extractor.py --workspace "$PWD" --output runs/semantic-feedback-source-reproduction
.venv/bin/python scripts/recompute_results.py runs/task-local-five-v2/jobs --verify results/task-local-five-v2.json
.venv/bin/python scripts/audit_session_tokens.py --run-root runs/task-local-five-v2 --output runs/semantic-feedback-verification-reproduction/legacy-token-audit.json
```

Compact provenance is in `results/semantic-feedback-verification.json`; raw checks remain in the cited `runs/` directories. The next extractor-only configuration is proposed and dry-run validated, but has not been launched or approved for live execution.
