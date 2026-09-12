# Assembly timeout fix

The exact saved annotations were replayed in the original pinned scientific environment. Only graph assembly ran: no model calls, repair, scientific probes or hidden tests.

| Allocation | Allowance seconds | Actual seconds | Exit code | Usable graph |
| --- | ---: | ---: | ---: | --- |
| old_limit | 15.00 | 12.02 | 124 | False |
| remaining_budget | 188.41 | 15.47 | 0 | True |

Overall extraction cap: 360s; unchanged collection/shutdown reserve: 60s. The shared work allowance is 300s.

The old allocation terminated the helper before it finished. The corrected allocation uses the work time remaining after interpretation, without spending the outer cleanup reserve. This verifies the saved failure case, not a guarantee that every extraction fits its total budget.

The benchmark comparison remains stopped at the user's request. Raw replay inputs, outputs and commands are preserved under `runs/assembly-budget-replay-v1/`.
