Build a scientific working model of this task for a separate repair agent. The deliverable is
understanding, not a repair: what this computation means scientifically, how its objects and
interfaces realize that meaning, and which conventions and assumptions matter for the reported
problem.

The input is a bounded selection of a code-derived object graph: constraint findings from
executing the public reproducer, objects, operations, dataflow links, unresolved items,
relevant source passages and public scientific excerpts. Annotate the most task-relevant
objects: constraint findings first, then workflow interfaces, their parameters and outputs.

Response: one JSON object with an annotations array. Each annotation references an exact
supplied object_id and may contain only meaning, conventions and assumptions. The code owns
structure and derived properties; annotate it, do not extend it. Where an interpretation is
uncertain, state it as an assumption or omit it. Keep it compact: at most 40 annotations,
most relevant first.

Mode note: if you have shell access, the payload file is {scratch}/scientific-context-input.json;
write your first-pass annotations JSON to {scratch}/extract_draft-annotations.json early (the
harness collects that file even if the turn later times out), then refine if time remains.
If you have no tools, the payload is embedded inline below and you return the JSON directly.

Task root: {root}
Original task:
{instruction}
