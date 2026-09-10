Draft a scientific interpretation of this task for a separate coding-agent repair session.
Your job is a small amount of useful scientific meaning, not bug repair or comprehensive reconstruction.
Code will check your draft's bindings and run accepted public probes; a short revision may then
use those diagnostics before the final handoff. Do not claim that those future checks have run.

Code is preparing a source index and document catalog concurrently with this session:
- {scratch}/catalog.md: compact reference IDs, source locations and previews.
- {scratch}/packet.json: complete indexed expressions and source references.
Start with the task statement and scientific material. If the catalog is not ready,
read the paper/source first and check again once. Do not rebuild the index yourself.

Deliver at most five relevant claims (prefer two or three), with at most twelve
quantities or scientific objects. Include scientific meaning, conventions, applicability assumptions,
intended input/output relationships and correspondence to actual code operands
and outputs. Distinguish intended
requirements from observations of the possibly buggy implementation.

For each useful claim, identify what the data/computation represents scientifically, not merely
its Python type or implementation name. State when the interpretation applies and a plausible
different interpretation that the public evidence can distinguish. A graph, sequence, set or
state need not have a scalar equation. Do not invent dimensions, geometry or a missing definition
to force a mathematical match. Generic advice such as "preserve behavior" or "make tests pass"
is not scientific content.

Return compact annotations ONCE as the JSON object in your final response as soon
as useful evidence is available. The schema is {runtime}/annotation-schema.json.
Only read and inspect; do not edit task source or write annotation/probe files.
Code will save your final annotations and any inline probe scripts.
Code will copy all source quotes, hashes and implementation expression trees,
construct the graph, and run validation/alignment/lifting/propagation. Do not do
that bookkeeping or rewrite the full graph yourself.

Annotation fields:
- schema_version: "annotations-1.0"; quantities and claims are arrays.
  The only other top-level fields are probes and unresolved; do not add task_id
  or graph metadata. Code supplies those.
- Quantity/object: id, meaning; optionally entity_id, symbol, code_ref, name, dimensions, scale, shape,
  status and evidence. Dimensions are a mapping such as {{"length": -3}}.
  Null/omitted means unknown. Physical dimensions/scale need scientific support.
  Prefer entity_id for a scientific object's actual code carrier: copy an exact source entry ID
  from the packet for a parameter, output, assignment or container update. Inspect its entity_role
  and source scope. This grounds the code entity only, not an equation or a scientific property.
  Do not guess IDs or silently equate the same spelling in different scopes.
  For a mathematical operand occurrence, use code_ref with path, exact start_line/end_line,
  symbol, and optional scope (copy the index scope verbatim when available):
  {{"path": "source/model.py", "start_line": 20, "end_line": 20, "symbol": "arrays['rpvi']"}}.
  Use inspected source locations. A source binding does not establish scientific
  meaning, units, frame, shape or normalization; leave each unsupported property
  unknown and state missing scientific definitions in unresolved.
- Claim: id, description; optionally formula (a short RHS or equation such as
  "V = -sum(J)"), implementation_id (an exact packet entry ID),
  implementation_ref (path, exact start_line/end_line, optional symbol and scope), quantities (IDs), bindings
  (scientific symbol to code symbol), operation, status, assumptions and evidence.
  Use implementation_ref for relevant computation discovered after the initial
  packet, or when its packet ID is absent. Code expands the index once from these
  references after you finish. Prefer the exact assignment/return span rather
  than an entire function. Reference actual operands separately instead of one
  broad label for unrelated coordinates, derivatives and outputs.
  Also use these optional text fields when supported:
  scientific_object (the scientific thing being represented),
  applicability (conditions and boundaries under which this interpretation holds),
  alternative_interpretation (a plausible competing meaning, not an invented strawman),
  discriminating_observation (what public observation would separate the meanings).
  consumer_ids is an optional array of actual packet entity IDs for affected consumers;
  a source reference alone does not prove runtime dataflow or scientific equivalence.
- Evidence: a packet document/entry ID, or a relative path and exact line span:
  {{"path": "paper.md", "start_line": 10, "end_line": 12}}.
  Use real relevant spans, not this illustrative span. The task statement's
  virtual path is @context/task_statement.md.
- Operations: unit_conversion, weighted_sum, normalization, linear_transform,
  or other. Leave unsupported implementation correspondence null. Restricted
  formulas support ordinary arithmetic, sum, sqrt, norm and matmul; unsupported
  structure remains unknown. Do not mistake an untyped numeric literal for
  evidence that a physical parameter is dimensionless.
- Optional unresolved: short reasons and limitations. Status is explicit, inferred
  or unresolved and defaults to inferred;
  explicit claims need actual source evidence. Every retained claim needs evidence.

You may also INCLUDE at most two independent, self-contained Python probe scripts
as inline source in the JSON, preferably short and focused on one mathematical/scientific
property each. Derive the property from scientific evidence and explicit assumptions;
do not manufacture a missing geometric definition to make a probe possible. State
what observation could falsify the proposed correspondence. Do NOT execute probes in
this phase. Code will run the selected scripts concurrently with per-probe and
shared deadlines after you finish. Each script runs with imports from {root} and
{root}/source available, in its own output directory; use absolute task paths for
input files. Do not depend on another probe's output or change task source.
Print a short result summary (preferably JSON), keep library logging quiet, and
make any asserted property explicit. The repair session receives bounded output
excerpts and exit status; full logs are retained separately.
Prefer a discriminating case and a relevant control when the evidence supports them; invariance
under presentation changes alone cannot establish that the computed scientific object is right.
Explain where the expected relationship comes from: public documentation, an explicit requirement,
or a justified reference/limiting case. Do not infer the expected answer just by copying the
current implementation. If a probe only compares hypotheses without deciding which is correct,
report it as diagnostic and leave that scientific choice unresolved. A successful execution is
not proof that the proposed meaning is true. Include inline source so repair can rerun the check.
Declare probes as:
{{"id": "p1", "claim_ids": ["c1"], "script": "probe_property.py",
  "source": "print('replace with a focused scientific probe')\n",
  "description": "What this probe tests and what an outcome would mean"}}
Probe IDs use only letters, digits, underscores or hyphens. No claimed results.
Keep each script below 32 KiB and the complete JSON below 64 KiB.
An assertion failure may expose the original bug; it does not invalidate an
intended scientific requirement.

Stopping rules (UTC; use date -u if needed):
- Stop new exploration by {explore_until}.
- Draft the best supported annotations by {save_by}.
- Return the final JSON by {finish_by}.
The interpretation allowance is at most {seconds} seconds including your tools.
Finish EARLIER once a small supported set is ready. Do not fill the caps or chase
every unresolved issue. If nothing is supportable, return empty quantities/claims
and an explicit unresolved reason. There is no open-ended refinement loop.

Your final response must be ONLY the compact annotation JSON object, without
Markdown fences or extra prose. Do not return the full graph or a file-name acknowledgement.

Task root: {root}
Original task:

{instruction}
