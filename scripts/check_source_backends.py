"""Run installed source analyzers on a public source slice; no models or code execution."""
import argparse
import json
from pathlib import Path
from scicontext.source_backends import analyze_sources

if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    result=analyze_sources(args.root,args.output)
    print(json.dumps({"backends":[a["backend"] for a in result["analyses"]],"extensions":result["extensions"],"gaps":result["gaps"]},indent=2))
