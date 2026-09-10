Interpret the scientific task for a separate coding-agent repair session.
Your job is compact semantic annotation, not bug repair or comprehensive reconstruction.

Code is preparing a source index and document catalog concurrently with this session:
- {scratch}/catalog.md: compact reference IDs, source locations and previews.
- {scratch}/packet.json: complete indexed expressions and source references.
Start with the task statement and scientific material. If the catalog is not ready,
read the paper/source first and check again once. Do not rebuild the index yourself.

Deliver at most five relevant claims (prefer two or three), with at most twelve
quantities. Include scientific meaning, conventions, applicability assumptions,
intended relationships and correspondence to indexed code. Distinguish intended
requirements from observations of the possibly buggy implementation.

Save compact annotations ONCE to {scratch}/annotations.json as soon as useful
evidence is available. The schema is {runtime}/annotation-schema.json.
Code will copy all source quotes, hashes and implementation expression trees,
construct the graph, and run validation/alignment/lifting/propagation. Do not do
that bookkeeping or rewrite the full graph yourself.

Annotation fields:
- schema_version: "annotations-1.0"; quantities and claims are arrays.
  The only other top-level fields are probes and unresolved; do not add task_id
  or graph metadata. Code supplies those.
- Quantity: id, meaning; optionally symbol, name, dimensions, scale, shape,
  status and evidence. Dimensions are a mapping such as {{"length": -3}}.
  Null/omitted means unknown. Physical dimensions/scale need scientific support.
- Claim: id, description; optionally formula (a short arithmetic string),
  implementation_id (an exact packet entry ID), quantities (IDs), bindings
  (scientific symbol to code symbol), operation, status, assumptions and evidence.
- Evidence: a packet document/entry ID, or a relative path and exact line span:
  {{"path": "paper.md", "start_line": 10, "end_line": 12}}.
  Use real relevant spans, not this illustrative span. The task statement's
  virtual path is @context/task_statement.md.
- Operations: unit_conversion, weighted_sum, normalization, linear_transform,
  or other. Leave unsupported implementation correspondence null. Restricted
  formulas support ordinary arithmetic, sum, sqrt, norm and matmul; unsupported
  structure remains unknown. Do not mistake an untyped numeric literal for
  evidence that a physical parameter is dimensionless.
- Optional unresolved: short reasons and limitations. Status defaults to inferred;
  explicit claims need actual source evidence. Every retained claim needs evidence.

You may also WRITE at most two independent, self-contained Python probe scripts
under {scratch}, preferably short and focused on one mathematical/scientific
property each. Do NOT execute scientific probes or numerical reproductions in
this phase. Code will run the selected scripts concurrently with per-probe and
shared deadlines after you finish. Each script runs with imports from {root} and
{root}/source available, in its own output directory; use absolute task paths for
input files. Do not depend on another probe's output or change task source.
Print a short result summary (preferably JSON), keep library logging quiet, and
make any asserted property explicit. The repair session receives bounded output
excerpts and exit status; full logs are retained separately.
Declare probes as:
{{"id": "p1", "claim_ids": ["c1"], "script": "probe_property.py",
  "description": "What this probe tests and what an outcome would mean"}}
Probe IDs use only letters, digits, underscores or hyphens. No claimed results.
An assertion failure may expose the original bug; it does not invalidate an
intended scientific requirement.

Stopping rules (UTC; use date -u if needed):
- Stop new exploration by {explore_until}.
- Save the best supported annotations by {save_by}.
- Finish with the short acknowledgement by {finish_by}.
The interpretation allowance is at most {seconds} seconds including your tools.
Finish EARLIER once a small supported set is ready. Do not fill the caps or chase
every unresolved issue. If nothing is supportable, save empty quantities/claims
and an explicit unresolved reason. There is no open-ended refinement loop.

After saving, your final response must be ONLY: annotations.json
Do not repeat the annotations or graph in your final response.

Task root: {root}
Original task:

{instruction}
