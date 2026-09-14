"""Prepare public evidence and assemble the single scientific interpretation format."""
from __future__ import annotations

import copy

from .io import digest_json
from .scientific_model import join, render, schema

# A transport sanity check AFTER source-level abstraction, not a selection rule.
ENRICHMENT_MAX_BYTES = 1_500_000


def enrichment_schema():
    return schema()


def enrichment_input(graph, packet, *, root=None):
    """Keep evidence intact on disk; representation.reading_input owns abstraction."""
    coverage = packet.get("coverage", {})
    return {**{key: copy.deepcopy(graph.get(key, [])) for key in
               ("objects", "operations", "links", "unsupported")},
            "context": {"scientific_passages": copy.deepcopy(packet.get("documents", [])),
                        "linked_document_paths": [r["path"] for r in coverage.get("document_references", [])],
                        "code_passages": copy.deepcopy(packet.get("entries", [])),
                        "analysis_sources": copy.deepcopy(packet.get("analysis_sources", [])),
                        "analysis_regions": copy.deepcopy(
                            coverage.get("execution_regions", []) +
                            coverage.get("workflow_retrieval", {}).get("references", []) +
                            coverage.get("task_local_retrieval", {}).get("references", [])),
                        "observations": copy.deepcopy(graph.get("dynamic", {}).get("observed_values", [])),
                        "execution": {**copy.deepcopy(coverage.get("execution_status", {})),
                            **copy.deepcopy(coverage.get("execution_seed", {})),
                            "resolved_callables": len(coverage.get("execution_regions", [])),
                            "selected_callable_excerpts": sum(r["admitted"] for r in coverage.get("executed_functions", []))}},
            "selection": {key: value for key, value in coverage.items()
                          if isinstance(value, (int, bool))}}


def enrich_objects(graph, response, context=None):
    return join(graph, response, context)


def render_guide(graph):
    model = graph.get("scientific_model")
    return render(model) if model and model.get("purpose") and model.get("computations") else ""


def render_objects(graph):
    return render_guide(graph)


def object_bundle(graph, response, context=None):
    combined = join(graph, response, context)
    model = combined.get("scientific_model", {})
    usable = bool(model.get("purpose") and model.get("computations"))
    return {"graph": combined, "graph_sha256": digest_json(combined),
            "handoff": render_guide(combined) if usable else "",
            "context": copy.deepcopy(context),
            "assembly": {"usable": usable, "status": "scientific_model" if usable else "no_scientific_model",
                         "interpretation_status": "enriched" if usable else "invalid",
                         "enrichment": combined["enrichment"]},
            "analysis": {"coverage": combined.get("coverage", {}).get("totals", {})},
            "validation": {"valid": usable,
                           "scope": "code_owned_structure_and_citation_IDs_not_scientific_entailment"}}
