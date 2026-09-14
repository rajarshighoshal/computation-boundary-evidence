Explain the task's scientific or computational purpose and the small set of computations that
matter for repairing it. Connect quantity meanings, transformations and relevant conventions.
Use the supplied code-owned computations, relationships and public sources. Focus on the
implementation, not a summary of the reproducer. Distinguish intended behaviour from observations.

Return JSON only: {{"schema_version":"object-enrichment-2.0","purpose":CLAIM,"computations":[...]}}.
CLAIM is {{"text":"explanation","source_ids":["supplied source ID"]}}.
Each computation has computation_id, meaning (CLAIM), quantities ([{{"object_id":"supplied entity ID",
"meaning":CLAIM}}]), conventions ([CLAIM]), and assumptions ([string]).
Use existing computation/entity IDs and cite supplied source IDs. Put unsupported interpretations
in assumptions. Do not invent program relationships or requirements. Select at most six computations,
most relevant first; keep the combined explanation under 700 words. Empty arrays are valid.

Task:
{instruction}
