# Five-task comparison: partial findings and stop

This run is incomplete. The generated [report](WORKFLOW_FIVE_V1.md) retains every planned arm,
including the interrupted and unstarted ones. It must not be presented as a completed five-task
comparison or used to count unrun arms as repair failures.

## Completed geometry-reader pair

The baseline subtracts the cube grid origin from atomic coordinates. The context-assisted patch
instead requests periodic wrapping with `to_unit_cell=True`, leaving origin handling unchanged.
Both satisfy the public check, but only the baseline satisfies the official private evaluation.
These are different transformations; wrapping is not origin translation.

The supplied scientific context explicitly mentioned the unused nonzero origin, distinguished
translation from wrapping and stated that the visible evidence did not resolve the intended choice.
Thus the evidence does not support saying the extractor simply omitted origin. The repair agent's
tests used zero-origin examples and reinforced wrapping without distinguishing the alternatives.
The defensible failure description is incorrect generalization from an underdetermining public
condition despite relevant contextual evidence. This pair alone does not prove context caused it.

Review used patches and scientific annotations, not private assertion bodies. Artifacts:
`runs/workflow-five-v1/jobs/task-091-baseline/` and `task-091-science/`.

## OpenMC infrastructure failure

Extraction completed, but the repair launch failed with host error
`[Errno 7] Argument list too long: 'docker'`. The adapter passed the complete rendered graph through
the upstream command-string interface. The saved graph/handoff and repair-process receipt establish
that this was a launch/representation-size failure, not an extraction timeout or Docker OOM.

The repair model did not start. The fail-fast runner interrupted the concurrent baseline and did
not launch the remaining tasks. Failed/interrupted costs remain explicit; no retry was performed.

The appropriate transport is the documented
[Codex stdin prompt route](https://learn.chatgpt.com/docs/non-interactive-mode#use-codex-exec---when-stdin-is-the-prompt).
Transport alone does not address the verbose handoff: the repair-facing view should emphasize
scientific annotations and relevant structure, while preserving the complete graph as an accessible
artifact. This is a presentation change and needs a newly frozen comparison, not an unrecorded
mid-run modification. Neither correction nor a rerun is claimed here.

The original method source/prompts remained unchanged from `a27cc93`; `6574276` froze this run's
approved settings. Task001's prior diagnostic exposure was disclosed in the run configuration and
is carried into the generated report. No conclusions about the full benchmark are supported.
