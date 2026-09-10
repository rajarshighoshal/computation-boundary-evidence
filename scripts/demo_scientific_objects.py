#!/usr/bin/env python3
"""Generate inspectable cross-domain mechanism fixtures, with no model/candidate execution."""
import argparse
import json
import subprocess
from importlib.metadata import version
from pathlib import Path

from scicontext.io import digest_file, write_json
from scicontext.object_context import enrichment_input, object_bundle
from scicontext.packet import build_packet
from scicontext.scientific_objects import extract_objects


MEANINGS = {
    "hydrology": {
        "previous_volume": "Stored reservoir water before the interval (README.md).",
        "outward_flow": "Positive-outward volumetric transport; the scientific description says it decreases storage (README.md).",
        "duration": "Elapsed transport interval, using a time unit consistent with the flow rate (README.md).",
    },
    "mechanics": {
        "stiffness": "Constrained stiffness operator mapping displacement to force (README.md).",
        "applied_load": "External force vector in the same displacement basis as the stiffness operator (README.md).",
    },
    "electrical": {
        "power_samples": "Instantaneous electrical power samples, not already integrated energy (README.md).",
        "sample_times": "Ordered times corresponding to power samples; irregular spacing is allowed (README.md).",
        "power": "Electrical power obtained from the explicit voltage and current quantities (README.md).",
    },
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    workspace = Path(__file__).resolve().parents[1]
    receipt = {"kind": "scientific_object_mechanism_demo", "model_calls": 0,
               "interpretation_origin": "hand_authored_fixture_not_LLM_discovery", "cases": [],
               "implementation_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=workspace, text=True).strip(),
               "implementation_hashes": {name: digest_file(workspace / "src/scicontext" / name) for name in
                   ("scientific_objects.py", "object_context.py", "packet.py", "evidence.py", "expressions.py")},
               "script_sha256": digest_file(Path(__file__)), "pint_version": version("pint")}
    for domain, meanings in MEANINGS.items():
        root = workspace / "examples/scientific_objects" / domain
        packet = build_packet(root)
        graph = extract_objects(root, packet)
        graph["task_id"] = "fixture_" + domain
        payload = enrichment_input(graph, packet)
        # A fixed stand-in for the reader's output tests the join, not scientific inference quality.
        response = {"schema_version": "object-enrichment-1.0", "annotations": [
            {"object_id": obj["id"], "meaning": meanings[obj["symbol"]],
             "assumptions": ["The supplied README's scientific description applies to this fixture."]}
            for obj in graph["objects"] if obj["symbol"] in meanings]}
        bundle = object_bundle(graph, response, payload["context"])
        destination = args.output / domain
        write_json(destination / "reader-input.json", payload)
        write_json(destination / "example-interpretation.json", response)
        write_json(destination / "bundle.json", bundle)
        (destination / "scientific-context.md").write_text(bundle["handoff"])
        assert bundle["assembly"]["interpretation_status"] == "enriched"
        receipt["cases"].append({"domain": domain, "source": str(root.relative_to(workspace)),
            "source_hashes": {p.name: digest_file(p) for p in sorted(root.iterdir()) if p.is_file()},
            "coverage": graph["coverage"], "annotated_objects": len(bundle["graph"]["enrichment"]["applied_object_ids"]),
            "bundle": str(destination / "bundle.json"), "bundle_sha256": digest_file(destination / "bundle.json")})
    write_json(args.output / "receipt.json", receipt)
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
