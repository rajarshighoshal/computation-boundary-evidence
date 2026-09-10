Extract a small, testable scientific interpretation for a separate coding-agent repair session.
Your first deliverable is one supported scientific claim linked to an executable public probe,
not a comprehensive reconstruction or a collection of citations. The probe should exercise the
task's actual computation and expose an observation that matters for repair. If the public evidence
cannot support a scientific expectation, use the diagnostic/no-probe alternatives below; do not
invent an oracle to satisfy this objective. Do not repair the code.
Code will check your bindings and run accepted probes after your final JSON. A short revision is
optional when useful and time remains. Do not defer the useful deliverable to that possible pass
or claim that future checks have already run.

Code is preparing a source index and document catalog concurrently with this session:
- {scratch}/catalog.md: compact reference IDs, source locations and previews.
- {scratch}/packet.json: complete indexed expressions and source references.
Start with the task statement, locate the relevant scientific definition and actual code entry point,
then inspect only the source and input conventions needed for a small probe. Search the catalog
for relevant entries; do not dump the complete packet or read the entire repository/paper first.
If the catalog is not ready, read relevant paper/source passages and check again once.
Do not rebuild the index yourself.

Deliver at most five relevant claims (one is enough), with at most twelve
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

Prioritize one independent, self-contained Python probe script as inline source in the JSON;
include at most two. For each probe, use the existing claim fields and probe description/source
to identify:
- the scientific object, expected relationship and public evidence supporting that expectation;
- applicability/preconditions, including any boundary or convention the relationship depends on;
- the actual repository function or computation being exercised, concrete inputs and observed outputs;
- what observation would falsify the relationship, and a discriminating control when appropriate.
Call the inspected repository code; do not merely assert a reimplemented equation, generic mathematical
tautology, AST pattern or import success. Construct a small valid case from the inspected API and
public input conventions. Check that chosen options affect the code path being tested. A large
simulation, broad parameter sweep or full test suite is not needed.
Derive the property from scientific evidence and explicit assumptions; do not manufacture a missing
definition to make a probe possible. Do NOT execute probes in
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
label it diagnostic in its description and leave that scientific choice unresolved; do not assert
an unsupported expected answer. If no meaningful executable probe is supportable, return probes: []
and a specific no-probe reason in unresolved: identify the inspected public evidence and the missing
definition, executable entry point, input convention or dependency that prevents a useful check.
"More context needed" alone is not a reason. Do not silently substitute citation-only claims.
A successful execution is
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
Return the minimum useful JSON EARLY once one supported claim and runnable probe are ready.
Do not spend the remaining allowance adding claims, reading the complete index or polishing citations.
The times are latest stopping points, not a schedule to fill. Preserve other unknowns in unresolved.
If nothing is supportable, return empty quantities/claims/probes and the specific evidence-backed
unresolved reason. There is no open-ended refinement loop.

Your final response must be ONLY the compact annotation JSON object, without
Markdown fences or extra prose. Do not return the full graph or a file-name acknowledgement.

Task root: {root}
Original task:

{instruction}
