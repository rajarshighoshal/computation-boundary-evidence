Build a small scientific working model of this task for a separate repair agent.
Do not repair code or design tests. The deliverable is understanding: what this computation
means scientifically, how its objects and interfaces represent that meaning, and which
conventions and assumptions matter for the reported problem.

Read {scratch}/scientific-context-input.json. Code has supplied actual objects, operations,
dataflow links, unresolved items, relevant source passages and public scientific excerpts.
If preparation is still finishing, begin with the task statement, then read the payload.
The response schema is {runtime}/object-enrichment.schema.json.

Use public scientific material to interpret the extracted objects. Do not merely repeat API
names or Python types: distinguish, for example, a coefficient matrix from its scientific
role as a model operator when the supplied material supports that connection. Follow the
recorded relationships to explain how quantities move between components and interfaces.
You may inspect additional public task material read-only when a definition needs context.

Return only object-enrichment-1.0 JSON with an annotations array. Each annotation references
an exact supplied object_id and may contain only meaning, conventions and assumptions.
Include source paths/locations in explanatory text where they support an interpretation.
If a meaning is uncertain, state the uncertainty as an assumption or omit it. Do not infer
physical roles from a familiar variable name alone. State where a convention applies;
do not turn one public example into a requirement for all valid inputs.

Do not create objects, links, unit values, formulas asserted as repair requirements, probes
or patches. The code owns structure and derived properties. Your annotations enrich that
structure; they do not replace it. Existing code may be buggy: distinguish what it computes
from what scientific sources intend, without inventing an unsupported intended answer.

Finish with a compact, useful interpretation, not a comprehensive reconstruction. The model
allowance is at most {seconds} seconds. Stop exploration by {explore_until}, draft by {save_by},
and return JSON by {finish_by}. These are latest milestones, not time to fill.

Task root: {root}
Original task:
{instruction}
