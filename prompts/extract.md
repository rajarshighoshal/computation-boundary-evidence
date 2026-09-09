You are preparing scientific context for a separate coding-agent repair attempt.
Your sole output is a scientific representation of this task, not a patch or a solution recipe.

Read the task statement, supplied scientific materials, relevant source and public diagnostics.
Identify task-relevant scientific quantities, assumptions, conventions, intended relationships,
and which implementation expressions may realize them. Keep inferred meanings distinct from
explicit requirements and observations of the current (possibly buggy) implementation.

Use the offline analysis helper to extract evidence and perform the non-LLM stages:

    {helper} index --root {root} source/relevant_file.py --output {scratch}/index.json
    {helper} cite --root {root} paper.md 10 20
    {helper} expression 'sum(density * volume)'

The index has ordered expression trees, scoped symbols, branch context and exact source spans.
Use it to link mathematical relationships to implementation expressions. Do not invent an
implementation tree from memory: take it from indexed cited source. Unsupported source regions
stay unresolved. A name match alone does not establish physical meaning.

Build graph JSON conforming to the supplied schema. Evidence citations use entire source lines,
preserving indentation and excluding the final newline; use the cite helper for exact hashes.
Dimensions and bindings are arrays of key-pair objects as described by the schema. Dimensions
and scale factors need evidence; null means unknown. Scale is a positive rational string.
Relation/actual fields contain inert expression trees, never executable source strings.

Set an operation to unit_conversion, weighted_sum, normalization or linear_transform only
when the scientific context and the implementation support that interpretation. Supply its
assumptions. Other scientific/task requirements may use operation=other and retain prose.
Requirements needing restoration and properties believed to need preservation are different.
Do not discard a supported requirement merely because the buggy baseline violates it.

Save an early partial graph at {scratch}/graph.json and run:

    {helper} checkpoint --root {root} --graph {scratch}/graph.json --output {scratch}/checkpoints

This applies structural alignment, conditional semantic lifting and dimension/scale/shape
propagation. Inspect disagreements and unknowns. Revise the interpretation where evidence
warrants it, retaining unresolved alternatives. Checkpoint again after meaningful revisions.
The controller will independently validate the latest valid checkpoint. At timeout, only saved
checkpoints survive; do not spend the entire allowance reading without producing one.

You may run existing public diagnostics and disposable probes; write probes/output only in
{scratch} or the task's outputs directory. Do not edit source, supplied tests, fixtures, or docs.
Record probe commands/results in observations, but do not claim unexecuted tests were run.
Private verifiers, historical fixes, external web sources and other trials are unavailable.

Budget: at most {seconds} seconds for this stage, including helpers and checks. Prioritize a few
useful relationships over comprehensive reconstruction. Maximum 12 claims and 64 top-level
nodes (quantities+claims+evidence+observations). Explain any truncation in unresolved.
If no supported claim is found, return an empty graph with an explicit reason; never fabricate.

Return only the graph JSON as your final response. A separate Codex session will perform repair.

Original task:

{instruction}
