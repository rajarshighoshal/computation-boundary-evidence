# Development pilot notes

These are observations and proposals, not changes to the running pilot. The evaluated code, prompts and time budgets remain frozen at the pilot's recorded revision.

## Extraction stopping — task 002

The extraction stage reached its cutoff, but its saved graph was valid and handed to repair; source files were unchanged. A timeout here is not a lost or invalid extraction. Exact timings and graph counts are generated in [the results](PILOT_RESULTS.md).

The trace includes public scientific probes, graph refinement, one correction of invalid absolute observation-artifact paths, and subsequent checkpoint validation. The workflow also asks for the full graph again as the final response, despite already saving a validated checkpoint. No completed-turn token total was emitted before interruption; the raw session is preserved.

In response to Rajarshi's timing question, the proposed next iteration is: stop new exploration at four minutes, save/validate by five minutes, and return the checkpoint identifier instead of duplicating the full JSON. Explain the expected relative artifact-path format explicitly. These are stopping/interface improvements to test, not evidence that six minutes is intrinsically insufficient.

If useful extraction still gets cut off, an eight-minute cap could be tested under the same 30-minute total allowance, taking two minutes from repair. Do not apply that change halfway through this pilot.

## Completed pilot

Task077 also reached the extraction cutoff with a usable checkpoint and unchanged source. Both context-assisted repairs passed, but both baselines also passed. The context procedure was slower on both tasks. See [the generated results](PILOT_RESULTS.md) for exact timings and counts; the stopping-rule proposal remains unapplied.
