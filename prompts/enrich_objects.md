Explain the scientific computation represented by the supplied evidence packets: what the
quantities mean, how they are represented, how the transformations connect them, and which
conventions and conditions apply. Use the task, function bodies and public sources as evidence.
Cover the relevant inputs, transformations and outputs together.

Annotate existing object IDs. Cite supporting source IDs and locations in each interpretation.
Describe measurements as observations and source-stated conditions as requirements. Put specific
missing details in assumptions as "unknown: ...".

Return only {{"schema_version": "object-enrichment-1.0", "annotations": [...]}} with at most 40
annotations, most relevant first. Each annotation contains object_id, meaning (string), conventions
(array of strings) and assumptions (array of strings). Preserve the supplied graph structure.

If shell tools are available, read {scratch}/scientific-context-input.json and save first-pass JSON
to {scratch}/extract_draft-annotations.json early, then return the final JSON. Otherwise, use the
input embedded below and return the JSON directly.

Task root: {root}
Original task:
{instruction}
