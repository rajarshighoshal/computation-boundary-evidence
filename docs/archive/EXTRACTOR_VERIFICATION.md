# Bounded extractor verification

Verified extraction-only runs: 2/2. The cap remained 360 seconds per task. No repair sessions or private verifiers ran.

| Task | Total seconds | Interpretation seconds | Claims | Source changed | Finished cleanly |
| --- | ---: | ---: | ---: | --- | --- |
| 002 | 153.46 | 131.70 | 3 | False | True |
| 077 | 132.74 | 113.03 | 3 | False | True |

The final model responses were short annotation-file identifiers, not duplicate graphs. Code resolved source evidence, assembled and checked the graphs, and ran declared probes. Preparation overlapped interpretation-session startup/execution. Multi-probe concurrency is covered by tests; these live checks each selected a single probe.

Executed probes: 2; assertion failures against the original implementations: 2. Numeric output and traces are preserved in the handoff. These are candidate scientific counterexamples, not an automatic proof that every extracted claim or probe is correct.

Completed-turn usage was available for these interpretation sessions. This verifies completion and artifact handling; it does not measure repair success, nor establish an end-to-end improvement over the earlier pilot.

Evaluated implementation: `004e6f9af7da0b867ccb071cfb460fa8a02464f1`. Raw records: `runs/extractor-annotations-v1`. A subsequent small controller fix reserves/bounds shutdown time; that exception path is covered by synthetic deadline tests, not a new model run.

[Machine-readable verification](../results/extractor-annotations-v1.json). Quantitative text is generated from checked receipts.

```bash
uv run --no-sync python scripts/report_extractor.py
```
