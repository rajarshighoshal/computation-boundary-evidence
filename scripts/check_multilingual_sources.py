#!/usr/bin/env python3
"""Static checks on pinned public source files; no models, compilation or benchmark scoring."""
import argparse
import csv
import json
from importlib.metadata import version
from pathlib import Path
import shutil
import subprocess
import urllib.request

from scicontext.io import digest_file, write_json
from scicontext.language_frontends import source_language
from scicontext.object_context import enrichment_input
from scicontext.packet import build_packet
from scicontext.scientific_objects import extract_objects


# File choices are fixed before parser outcomes; do not reroll failed cases.
CASES = {"004": "BlockMgr.cpp", "025": "OspreyQuantify.m", "016": "BedGraph.py",
         "051": "MakeMagGradGridDH.f95", "068": "vcf.c"}


def fetch(url):
    request = urllib.request.Request(url, headers={"User-Agent": "scicontext-public-source-check"})
    with urllib.request.urlopen(request, timeout=40) as response:
        return response.read()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--reuse-source", type=Path, help="Reuse matching pinned files from an earlier check; fetch missing files only")
    args = parser.parse_args()
    workspace = Path(__file__).resolve().parents[1]
    rows = {r["task_id"]: r for r in csv.DictReader((workspace / "data/release/data/tasks.csv").open())}
    args.output.mkdir(parents=True, exist_ok=False)
    previous = {c["task_id"]: c for c in json.loads((args.reuse_source / "receipt.json").read_text())["cases"]} if args.reuse_source else {}
    receipt = {"kind": "pinned_public_source_frontend_check", "model_calls": 0,
               "scope": "Selected files, not whole-repository coverage or scientific-meaning quality",
               "implementation_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
               "implementation_hashes": {name: digest_file(workspace / "src/scicontext" / name) for name in
                   ("scientific_objects.py", "object_context.py", "packet.py", "evidence.py", "language_frontends.py", "cython_frontend.py", "native_objects.py")},
               "dependencies": {p: version(p) for p in ("tree-sitter", "tree-sitter-c", "tree-sitter-cpp", "tree-sitter-fortran", "tree-sitter-matlab", "Cython", "pint")},
               "script_sha256": digest_file(Path(__file__)), "cases": []}
    for task, basename in CASES.items():
        row = rows[task]
        assert row["restricted_license"].lower() == "false" and row["base_commit"]
        repo = row["repository_url"].removeprefix("https://github.com/")
        case = {"task_id": task, "language": row["language"], "repository": row["repository_url"],
                "source_commit": row["base_commit"], "requested_basename": basename}
        if task == "016":
            case["selection_correction"] = "v1 requested absent BedGraph.pyx. At this pinned commit the file is BedGraph.py (Python syntax); this is not a real .pyx frontend check. Failed v1 receipt is preserved."
        try:
            old = previous.get(task, {})
            reusable = (old.get("status") == "extracted" and old.get("source_commit") == row["base_commit"] and
                        old.get("repository") == row["repository_url"] and Path(old.get("path", "")).name == basename)
            if reusable:
                path = old["path"]
            else:
                tree_url = f"https://api.github.com/repos/{repo}/git/trees/{row['base_commit']}?recursive=1"
                tree = json.loads(fetch(tree_url))
                if tree.get("truncated"):
                    raise ValueError("GitHub source tree response truncated")
                candidates = [e["path"] for e in tree["tree"] if e["type"] == "blob" and Path(e["path"]).name == basename]
                if len(candidates) != 1:
                    raise ValueError(f"Expected unique requested file; found {candidates}")
                path = candidates[0]
            url = f"https://raw.githubusercontent.com/{repo}/{row['base_commit']}/{path}"
            root, context = args.output / task / "source", args.output / task / "context"
            target = root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            if reusable:
                saved = args.reuse_source / task / "source" / path
                if digest_file(saved) != old["source_sha256"]:
                    raise ValueError("Saved source differs from its receipt")
                shutil.copyfile(saved, target)
            else:
                target.write_bytes(fetch(url))
            context.mkdir(parents=True)
            shutil.copyfile(workspace / f"data/release/tasks/task_{task}/instruction.md", context / "task_statement.md")
            packet = build_packet(root, context, multilingual=True, source_paths=[path])
            graph = extract_objects(root, packet)
            write_json(args.output / task / "packet.json", packet)
            write_json(args.output / task / "objects.json", graph)
            write_json(args.output / task / "reader-input.json", enrichment_input(graph, packet))
            case.update(status="extracted", path=path, source_url=url, source_sha256=digest_file(target),
                        frontend=source_language(path), reused_source=bool(reusable),
                        packet_coverage=packet["coverage"], object_coverage=graph["coverage"])
        except Exception as error:
            case.update(status="failed", error=f"{type(error).__name__}: {error}")
        receipt["cases"].append(case)
        write_json(args.output / "receipt.json", receipt)
        print(json.dumps({k: case.get(k) for k in ("task_id", "language", "status", "path", "error")}), flush=True)


if __name__ == "__main__":
    main()
