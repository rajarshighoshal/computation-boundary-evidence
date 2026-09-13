"""Offline representation coverage of archived public packets; no model/outcome access."""
import argparse
import json
from pathlib import Path
from time import perf_counter

from scicontext.computation import build_computation
from scicontext.io import digest_file, read_json, write_json


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jobs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args=parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Choose a new output directory to preserve prior checks")
    args.output.mkdir(parents=True)
    rows=[]
    for path in sorted(args.jobs.glob("task-*-science/*/agent/extract-scratch/packet.json")):
        task=path.parts[-5].split("-")[1]
        packet=read_json(path)
        payload={"context":{"code_passages":packet["entries"], "scientific_passages":packet.get("documents",[])}}
        start=perf_counter()
        model=build_computation(payload)
        elapsed=perf_counter()-start
        ids={q["id"] for q in model["quantities"]}|{u["id"] for u in model["transformations"]}
        valid=all({e["source"],e["target"]}<=ids for e in model["links"])
        write_json(args.output/f"task-{task}.json",model)
        rows.append({"task_id":task, "source":str(path), "sha256":digest_file(path),
                     **model["coverage"], "elapsed_seconds":elapsed, "valid_endpoints":valid,
                     "gap_count":len(model["gaps"]), "model_bytes":(args.output/f"task-{task}.json").stat().st_size})
    receipt={"scope":"Public archived packet expressions only; not repair outcomes, scientific correctness or fresh full-body retrieval.",
        "tasks":rows, "tasks_checked":len(rows), "tasks_with_arithmetic":sum(r["arithmetic_transformations"]>0 for r in rows),
        "tasks_with_shared_templates":sum(r["shared_templates"]>0 for r in rows),
        "tasks_with_non_reproducer_arithmetic":sum(r["non_reproducer_arithmetic_transformations"]>0 for r in rows),
        "all_endpoints_valid":all(r["valid_endpoints"] for r in rows),
        "total_seconds":sum(r["elapsed_seconds"] for r in rows), "model_calls":0, "candidate_execution":False}
    write_json(args.output/"receipt.json",receipt)
    print(json.dumps({k:v for k,v in receipt.items() if k!="tasks"},indent=2))


if __name__=="__main__":
    main()
