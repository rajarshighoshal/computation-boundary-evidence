# Scientific-object enrichment contract

The implemented enrichment interface preserves the original division of work:
code derives scientific objects and computational relationships; the LLM relates that structure
to the task's scientific meaning. It does not generate a replacement graph or a test oracle.

## Input

The LLM receives the code-derived `objects`, `operations`, `links` and `unsupported` records,
plus `context`: the public task statement and relevant scientific excerpts with source provenance.
Context uses the existing public-source packet; no private outcomes, previous repair answers,
personal memory or unsupported synthetic evidence enters the payload.

The base input uses a bounded selection. Workflow-retrieved interfaces and their
dataflow neighborhood are kept first, then everything else up to fixed object, unsupported-item
and byte budgets. A `selection` receipt records every drop as a structure-budget decision, not
a scientific-relevance verdict; the full graph remains in the objects artifact. The current Joern
attachment happens after this selection and is not yet bounded correctly. Do not claim the final
model payload is bounded until that integration is fixed and checked.

The interpreter returns annotations as output; the caller saves them. It does not edit source
or write a partial artifact during a read-only turn. A completed call can return no annotations.

This deliberately differs from a graph-only input proposal: scientific context is necessary for
the planned model–code alignment. Removing it would leave only API semantics and variable names.
The restriction belongs on what the LLM can change, not on removing the scientific source material.

## Output

`src/scicontext/object-enrichment.schema.json` defines the output. Each annotation contains an
existing `object_id` and only `meaning`, `conventions` and/or `assumptions`.

```json
{
  "schema_version": "object-enrichment-1.0",
  "annotations": [
    {
      "object_id": "so_id_from_the_supplied_graph",
      "meaning": "This right-hand-side vector represents the applied load in the supplied model.",
      "conventions": ["The scientific source defines the coordinate order."],
      "assumptions": ["The model description applies to this calculation."]
    }
  ]
}
```

The example is illustrative, not an extracted scientific result. The LLM cannot add objects,
operations, links, executable probes, patches, formulas asserted as requirements, or derived
dimensions/scales/shapes. It cannot mark unsupported relationships as resolved. Conventions and
assumptions remain contextual statements, not replacements for code-derived properties.

## Joining the two halves

- Match annotations to the exact object IDs in the supplied graph.
- Drop unanchored, malformed or duplicate annotations and record a short reason. Do not retry the
  model merely to repair such output; an empty annotation set is a valid result.
- Attach accepted interpretation under a separate field. Preserve the original structure,
  dimensions, scales, operation contracts, source links and recorded conflicts unchanged.
- Render the combined representation for inspection. API recognition, contextual interpretation
  and derived facts remain distinguishable. No annotation becomes a mandatory repair instruction.

## This prototype's boundary

Keep the current finite API families; do not expand the rule catalogue to inflate a demo.
Use existing unit/call-analysis tools only where they reduce implementation work and actually fit
the runtime. A call edge alone is not argument/return-value or scientific equivalence.

Coverage reports must expose the denominator and unsupported cases per file. They measure rule
coverage, not scientific understanding or repair benefit. Cross-domain examples demonstrate the
mechanism; benchmark claims still require a separately approved controlled comparison.
