"""Adapters for existing analyzers. No source execution or replacement type checker."""
from __future__ import annotations

from collections import Counter
from io import BytesIO
from pathlib import Path
import json
import shutil
import subprocess
import time

from .io import digest_file, write_json


def _decode(value):
    if isinstance(value, list):
        return [_decode(v) for v in value]
    if isinstance(value, dict):
        if "@value" in value:
            return _decode(value["@value"])
        return {k: _decode(v) for k, v in value.items() if k != "@type"}
    return value


def read_joern(path, source_root, language):
    """Normalize Joern's GraphSON export, retaining its actual analysis edges."""
    raw = _decode(json.loads(Path(path).read_text()))
    nodes = {}
    for v in raw["vertices"]:
        props = {k: (value[0] if isinstance(value,list) and len(value)==1 else value)
                 for k,value in v.get("properties",{}).items()}
        nodes[v["id"]] = {"id": f"joern:{language}:{v['id']}", "kind": v["label"], "properties": props}
    parents = {e["inV"]: e["outV"] for e in raw["edges"] if e["label"] == "AST"}
    for vid, node in nodes.items():
        cursor, seen, filename = vid, set(), None
        while cursor in nodes and cursor not in seen:
            seen.add(cursor)
            filename = nodes[cursor]["properties"].get("FILENAME")
            if filename:
                break
            cursor = parents.get(cursor)
        if filename:
            file = Path(filename)
            if file.is_absolute():
                try:
                    filename = file.relative_to(source_root).as_posix()
                except ValueError:
                    filename = str(file)
            node["path"] = filename
        node["line"] = node["properties"].get("LINE_NUMBER")
    kinds = {"CALL","IDENTIFIER","LOCAL","LITERAL","METHOD","METHOD_PARAMETER_IN",
             "METHOD_RETURN","RETURN","CONTROL_STRUCTURE","FIELD_IDENTIFIER","MEMBER","TYPE_DECL"}
    keep = {vid for vid,node in nodes.items() if node["kind"] in kinds}
    relations = {"REACHING_DEF","CDG","CFG","CALL","REF","ARGUMENT","RECEIVER","AST","PARAMETER_LINK","CONDITION"}
    edges = [{"source":nodes[e["outV"]]["id"],"target":nodes[e["inV"]]["id"],
              "role":e["label"],"properties":e.get("properties",{})}
             for e in raw["edges"] if e["label"] in relations and e["outV"] in keep and e["inV"] in keep]
    return {"backend":"joern", "language":language, "nodes":[nodes[v] for v in sorted(keep)],
            "links":edges, "edge_counts":dict(Counter(e["role"] for e in edges)),
            "scope":"Static code-property graph; external-call dataflow can be conservative, not a scientific contract."}


def joern_graph(root, language, output):
    output.mkdir(parents=True,exist_ok=False)
    commands = [
        ["joern-parse",str(root),"--language",language,"--output",str(output/"cpg.bin")],
        ["joern-export",str(output/"cpg.bin"),"--repr","all","--format","graphson","--out",str(output/"export")],
    ]
    started=time.monotonic()
    for index, command in enumerate(commands):
        with (output/f"command-{index}.log").open("w") as log:
            result=subprocess.run(command,cwd=output,stdout=log,stderr=subprocess.STDOUT,check=False)
        if result.returncode:
            raise RuntimeError(f"Joern command {index} exited {result.returncode}; see {output}")
    graph=read_joern(output/"export/export.json",root,language)
    graph["elapsed_seconds"]=time.monotonic()-started
    graph["commands"]=commands
    write_json(output/"normalized.json",graph)
    return graph


def fortran_symbols(root, paths):
    """Invoke fortls' own LSP handlers using its default CLI settings, without RPC reimplementation."""
    from fortls.interface import cli
    from fortls.langserver import LangServer
    from fortls.jsonrpc import JSONRPC2Connection, ReadWriter
    from fortls.version import __version__
    settings=vars(cli("fortls").parse_args(["--disable_autoupdate","--nthreads","1","--disable_diagnostics","--hover_signature"]))
    connection=JSONRPC2Connection(ReadWriter(BytesIO(),BytesIO()))
    server=LangServer(connection,settings)
    server.serve_initialize({"params":{"rootPath":str(root)}})
    records=[]
    for path in paths:
        uri=(root/path).as_uri()
        symbols=server.serve_document_symbols({"params":{"textDocument":{"uri":uri}}}) or []
        lines=(root/path).read_text().splitlines()
        interfaces=[]
        for symbol in symbols:
            line=symbol["location"]["range"]["start"]["line"]
            column=lines[line].casefold().find(symbol["name"].casefold())
            if column>=0:
                hover=server.serve_hover({"params":{"textDocument":{"uri":uri},"position":{"line":line,"character":column}}})
                if hover:
                    interfaces.append({"name":symbol["name"],"line":line+1,"hover":hover})
        records.append({"path":path,"symbols":symbols,"interfaces":interfaces})
    return {"backend":"fortls","version":__version__,"files":records,
            "scope":"Language-server symbol/interface information, not full dataflow analysis."}


def analyze_sources(root, output):
    """Analyze an already materialized public-source slice; record unavailable capabilities."""
    root,output=Path(root).resolve(),Path(output).resolve()
    output.mkdir(parents=True,exist_ok=True)
    paths=sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file() and not p.is_symlink())
    by_suffix=Counter(Path(p).suffix.lower() for p in paths)
    result={"source_hashes":{p:digest_file(root/p) for p in paths},"extensions":dict(by_suffix),"analyses":[],"gaps":[]}
    result["adapter_sha256"]=digest_file(Path(__file__))
    result["executables"]={name:{"path":str(Path(shutil.which(name)).resolve()),
                                 "sha256":digest_file(Path(shutil.which(name)).resolve())}
                           for name in ("joern-parse","joern-export") if shutil.which(name)}
    if shutil.which("joern-parse") and shutil.which("joern-export"):
        for language,suffixes in [("PYTHONSRC",{".py"}),("NEWC",{".c",".h",".cpp",".hpp",".cc",".cxx"})]:
            if not any(Path(p).suffix.lower() in suffixes for p in paths):
                continue
            try:
                result["analyses"].append(joern_graph(root,language,output/language.lower()))
            except (OSError,RuntimeError) as error:
                result["gaps"].append({"backend":"joern","language":language,"error":str(error)})
    elif any(Path(p).suffix.lower() in {".py",".c",".cpp",".h",".hpp",".cc",".cxx"} for p in paths):
        result["gaps"].append({"backend":"joern","reason":"executables_unavailable"})
    fortran=[p for p in paths if Path(p).suffix.lower() in {".f",".f90",".f95",".f03",".f08",".for"}]
    if fortran:
        result["analyses"].append(fortran_symbols(root,fortran))
    fallback=[p for p in paths if Path(p).suffix.lower() in {".m",".pyx",".pxd",".pxi"}]
    if fallback:
        result["gaps"].append({"backend":"syntax_frontend","paths":fallback,"reason":"no_deeper_backend_configured"})
    write_json(output/"receipt.json",result)
    return result


def attach_source_analysis(payload, result):
    """Attach analyzer-owned flow; retain mathematical bindings, not guessed call dispatch."""
    model=payload["computation"]
    import copy
    relevant=copy.deepcopy(result)
    ranges={}
    for body in payload["context"].get("function_bodies",[])+payload["context"].get("code_passages",[]):
        ranges.setdefault(body["path"],[]).append((body["start_line"],body["end_line"]))
    for analysis in relevant["analyses"]:
        if analysis["backend"]!="joern":
            continue
        selected={n["id"] for n in analysis["nodes"] if n.get("line") is not None and
                  any(start<=n["line"]<=end for start,end in ranges.get(n.get("path"),[]))}
        # Retain direct boundary endpoints rather than pretending the slice is closed.
        edges=[e for e in analysis["links"] if e["source"] in selected or e["target"] in selected]
        endpoints=selected|{e[k] for e in edges for k in ("source","target")}
        analysis["nodes"]=[{**n,"properties":{k:v for k,v in n["properties"].items() if k in
            {"CODE","NAME","FULL_NAME","METHOD_FULL_NAME","TYPE_FULL_NAME","SIGNATURE","IS_EXTERNAL","ARGUMENT_INDEX"}}}
            for n in analysis["nodes"] if n["id"] in endpoints]
        analysis["links"]=edges
        analysis["export_edge_counts"]=analysis.get("edge_counts",{})
        analysis["edge_counts"]=dict(Counter(e["role"] for e in edges))
        analysis["selection"]="source regions plus direct dependency boundary; complete export in source-analysis.json"
    model["source_analysis"]=relevant
    covered={node.get("path") for a in relevant["analyses"] if a["backend"]=="joern" for node in a["nodes"]}
    quantity_paths={q["id"]:q["path"] for q in model["quantities"]}
    unit_paths={u["id"]:u["path"] for u in model["transformations"]}
    paths={**quantity_paths,**unit_paths}
    model["links"]=[e for e in model["links"] if not (e.get("status")=="static_call_candidate" and
                        paths.get(e["source"]) in covered and paths.get(e["target"]) in covered)]
    model["source_analysis_bindings"]=[]
    for a in relevant["analyses"]:
        if a["backend"]!="joern":
            continue
        index={}
        for node in a["nodes"]:
            index.setdefault((node.get("path"),node.get("line")),[]).append(node["id"])
        for u in model["transformations"]:
            nodes=index.get((u["path"],u["line"]),[])
            if nodes:
                model["source_analysis_bindings"].append({"transformation_id":u["id"],"analyzer_nodes":nodes,
                    "status":"source_location_correspondence_not_value_equivalence"})
    model["dataflow_authority"]={"joern_paths":sorted(p for p in covered if p),
        "other_paths":"existing partial source frontend", "note":"Joern owns program-flow facts on covered paths. Mathematical operand links remain separate."}
    return payload


if __name__=="__main__":
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    analyze_sources(args.root,args.output)
