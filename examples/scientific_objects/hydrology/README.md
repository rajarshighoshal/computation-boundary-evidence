# Reservoir balance fixture

This synthetic scientific-context example models stored water volume. `previous_volume`
is volume before a time interval, `outward_flow` is positive for water leaving the reservoir,
and `duration` is the elapsed interval. There is no inflow in this model. Therefore outward
transport decreases the stored volume. The deliberately inconsistent addition in model.py
lets a reviewer inspect the distinction between scientific intent and actual computation.
This is a hand-authored mechanism fixture, not a benchmark task or repair result.
