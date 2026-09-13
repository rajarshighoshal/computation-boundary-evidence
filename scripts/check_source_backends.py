"""Run installed source analyzers on a public source slice; no models or code execution."""
import argparse
import json
from pathlib import Path
from scicontext.source_backends import analyze_sources
from scicontext.source_backends import attach_source_analysis
from scicontext.io import read_json, write_json, digest_file

if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--analysis-receipt",type=Path,help="Reuse a preserved analyzer result after source hash verification")
    parser.add_argument("--check-handoff",action="store_true")
    args=parser.parse_args()
    if args.analysis_receipt:
        result=read_json(args.analysis_receipt)
        for path,digest in result["source_hashes"].items():
            if digest_file(args.root/path)!=digest:
                raise ValueError("Source differs from the preserved analyzer input")
        args.output.mkdir(parents=True,exist_ok=False)
    else:
        result=analyze_sources(args.root,args.output)
    if args.check_handoff:
        from scicontext.packet import build_packet
        from scicontext.scientific_objects import extract_objects
        from scicontext.object_context import enrichment_input, object_bundle
        packet=build_packet(args.root,multilingual=True)
        graph=extract_objects(args.root,packet)
        payload=enrichment_input(graph,packet,root=args.root,connected=True)
        payload=attach_source_analysis(payload,result)
        bundle=object_bundle(graph,None,payload)
        write_json(args.output/"input.json",payload)
        write_json(args.output/"bundle.json",bundle)
        (args.output/"guide.md").write_text(bundle["handoff"])
        receipt={"source_analysis_receipt":str(args.analysis_receipt) if args.analysis_receipt else str(args.output/"receipt.json"),
                 "source_hashes":result["source_hashes"],"computation":payload["computation"]["coverage"],
                 "annotation_targets":len(payload["objects"]),"usable":bundle["assembly"]["usable"],
                 "guide_characters":len(bundle["handoff"]),"model_calls":0,"candidate_code_executed":False}
        write_json(args.output/"handoff-check.json",receipt)
        print(json.dumps(receipt,indent=2))
    print(json.dumps({"backends":[a["backend"] for a in result["analyses"]],"extensions":result["extensions"],"gaps":result["gaps"]},indent=2))
