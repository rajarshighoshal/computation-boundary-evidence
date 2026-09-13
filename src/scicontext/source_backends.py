"""Adapters for existing analyzers. No source execution or replacement type checker."""
from __future__ import annotations

from collections import Counter
from io import BytesIO
from pathlib import Path
import json
import os
import shutil
import subprocess
import time

from .io import digest_file, write_json

# Routing metadata, not a set of language-specific analyzers. Joern owns parsing.
JOERN_SOURCE_ROUTES = (
    (("PYTHONSRC", "PYTHON"), {".py", ".pyi"}),
    (("NEWC", "C"), {".c", ".h", ".cpp", ".hpp", ".cc", ".cxx", ".hh", ".hxx"}),
    (("JAVASRC", "JAVA"), {".java"}),
    (("JSSRC", "JAVASCRIPT"), {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}),
    (("KOTLIN",), {".kt", ".kts"}),
    (("GOLANG",), {".go"}),
    (("RUST",), {".rs"}),
    (("RUBYSRC",), {".rb", ".rake", ".gemspec"}),
    (("PHP",), {".php", ".phtml", ".php5"}),
    (("CSHARPSRC", "CSHARP"), {".cs"}),
    (("SWIFTSRC",), {".swift"}),
    (("ABAP",), {".abap"}),
)
JOERN_SOURCE_SUFFIXES = frozenset(s for _, suffixes in JOERN_SOURCE_ROUTES for s in suffixes)


def installed_frontends():
    result = subprocess.run(["joern-parse", "--list-languages"], capture_output=True, text=True, check=True)
    return {line[2:].strip().upper() for line in result.stdout.splitlines() if line.startswith("- ")}


def frontend_routes(paths, available):
    """Invoke each applicable installed frontend once, including mixed-language slices."""
    routes, gaps = [], []
    for aliases, suffixes in JOERN_SOURCE_ROUTES:
        selected = [p for p in paths if Path(p).suffix.lower() in suffixes]
        if not selected:
            continue
        language = next((alias for alias in aliases if alias in available), None)
        if language:
            routes.append((language, selected))
        else:
            gaps.append({"backend": "joern", "frontend_aliases": list(aliases), "paths": selected,
                         "reason": "frontend_unavailable"})
    return routes, gaps


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
                node["scope"] = nodes[cursor]["properties"].get("FULL_NAME", str(cursor))
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
    environment = os.environ.copy()
    # Some packaged launchers look beside the wrapper instead of the frontend.
    # Use Joern's documented override and its already-installed binary.
    if language in {"JSSRC", "JAVASCRIPT"} and not environment.get("ASTGEN_BIN"):
        executable = Path(shutil.which("joern-parse")).resolve()
        for base in (executable.parent, executable.parent.parent / "libexec"):
            binaries = [p for p in (base / "frontends/jssrc2cpg/bin/astgen").glob("astgen-*") if p.is_file() and os.access(p, os.X_OK)]
            if len(binaries) == 1:
                environment["ASTGEN_BIN"] = str(binaries[0])
                break
    commands = [
        ["joern-parse",str(root),"--language",language,"--output",str(output/"cpg.bin")],
        ["joern-export",str(output/"cpg.bin"),"--repr","all","--format","graphson","--out",str(output/"export")],
    ]
    started=time.monotonic()
    for index, command in enumerate(commands):
        with (output/f"command-{index}.log").open("w") as log:
            result=subprocess.run(command,cwd=output,stdout=log,stderr=subprocess.STDOUT,check=False,env=environment)
        if result.returncode:
            raise RuntimeError(f"Joern command {index} exited {result.returncode}; see {output}")
    graph=read_joern(output/"export/export.json",root,language)
    graph["elapsed_seconds"]=time.monotonic()-started
    graph["commands"]=commands
    if environment.get("ASTGEN_BIN"):
        graph["astgen_binary"] = environment["ASTGEN_BIN"]
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
        available = installed_frontends()
        result["available_frontends"] = sorted(available)
        routes, gaps = frontend_routes(paths, available)
        result["gaps"].extend(gaps)
        for language, selected in routes:
            try:
                graph = joern_graph(root,language,output/language.lower())
                graph["requested_source_paths"] = selected
                result["analyses"].append(graph)
            except (OSError,RuntimeError) as error:
                result["gaps"].append({"backend":"joern","language":language,"error":str(error)})
    elif any(Path(p).suffix.lower() in JOERN_SOURCE_SUFFIXES for p in paths):
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
    """Attach analyzer-owned code facts (signatures, calls, data flow) as
    analysis_sources on the packet — they feed the bounded selection, not a
    parallel computation representation."""
    import copy
    relevant=copy.deepcopy(result)
    ranges={}
    for body in payload["context"].get("function_bodies",[])+payload["context"].get("code_passages",[])+payload["context"].get("analysis_sources",[]):
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
    # Attach the enriched analysis regions as context — the bounded selection
    # picks from them like any other code evidence.
    payload.setdefault("context", {}).setdefault("analysis_sources", [])
    for a in relevant["analyses"]:
        if a["backend"] != "joern":
            continue
        for node in a["nodes"]:
            path = node.get("path")
            line = node.get("line")
            if not path or line is None:
                continue
            code = node.get("properties", {}).get("CODE", "")
            name = node.get("properties", {}).get("NAME", "")
            full_name = node.get("properties", {}).get("FULL_NAME", name)
            if not code and not name:
                continue
            payload["context"]["analysis_sources"].append({
                "id": f"sa_{node['id'][:16]}",
                "path": path, "start_line": line, "end_line": line,
                "text": code or f"// {full_name}",
                "analyzer": "joern",
                "name": name, "full_name": full_name,
                "kind": node.get("type", "unknown"),
                "language": a.get("language", "unknown"),
            })
        # Attach call/dataflow edges as evidence links
        for edge in a["links"]:
            payload["context"]["analysis_sources"].append({
                "id": f"sl_{edge['source'][:8]}_{edge['target'][:8]}",
                "path": "analysis://joern/edges", "start_line": 0, "end_line": 0,
                "text": f"{edge.get('role', 'call')}: {edge['source']} -> {edge['target']}",
                "analyzer": "joern", "kind": "edge",
            })
    payload["source_analysis_summary"] = {
        "backends": [a["backend"] for a in relevant["analyses"]],
        "joern_nodes": sum(len(a["nodes"]) for a in relevant["analyses"] if a["backend"] == "joern"),
        "joern_edges": sum(len(a["links"]) for a in relevant["analyses"] if a["backend"] == "joern"),
        "note": "Analyzer facts attached as analysis_sources; they feed the bounded selection.",
    }
    return payload


def lift_cpg_computations(payload, result):
    """Translate Joern's common AST into the existing representation, regardless of frontend.

    Only paths not handled by an existing mathematical frontend are lifted.
    Program flow stays in Joern's graph; this adapter does not infer it again.
    """
    from .computation import Builder, ident, attach_computation
    from .symbolic_math import symbolic_projection
    model = payload["computation"]
    covered = {u["path"] for u in model["transformations"]}
    builder = Builder({"context": {"scientific_passages": payload["context"].get("scientific_passages", [])}})
    operators = {"addition": "add", "subtraction": "sub", "multiplication": "mul", "division": "div",
                 "exponentiation": "pow", "modulo": "mod", "minus": "neg", "plus": "pos"}
    for analysis in result["analyses"]:
        if analysis["backend"] != "joern":
            continue
        nodes = {n["id"]: n for n in analysis["nodes"]}
        arguments, ast_children, controls, refs = {}, {}, {}, {}
        nested = set()
        for e in analysis["links"]:
            if e["role"] == "ARGUMENT":
                arguments.setdefault(e["source"], []).append(e["target"])
                nested.add(e["target"])
            elif e["role"] == "AST":
                ast_children.setdefault(e["source"], []).append(e["target"])
                if nodes[e["source"]]["kind"] == "RETURN":
                    nested.add(e["target"])
            elif e["role"] == "CDG":
                controls.setdefault(e["target"], []).append(e["source"])
            elif e["role"] == "REF":
                refs[e["source"]] = e["target"]
        def children(n):
            ids = arguments.get(n["id"], ast_children.get(n["id"], []))
            return sorted((nodes[i] for i in ids), key=lambda c: c["properties"].get("ARGUMENT_INDEX", c["properties"].get("ORDER", 0)))
        def expression(n, body, depth=0):
            p = n["properties"]
            if depth > 24:
                return {"op": "unknown", "syntax": "cpg_expression_depth_limit"}
            if n["kind"] == "LITERAL":
                return {"op": "literal", "value": p.get("CODE", "")}
            if n["kind"] in {"IDENTIFIER", "LOCAL", "METHOD_PARAMETER_IN", "FIELD_IDENTIFIER"}:
                qid = builder.quantity(body, p.get("CODE") or p.get("NAME", "unknown"), binding_key=refs.get(n["id"], n["id"]))
                builder.quantities[qid]["analyzer_node_id"] = n["id"]
                builder.quantities[qid]["representation"]["declared_type"] = p.get("TYPE_FULL_NAME")
                return {"op": "quantity", "quantity_id": qid}
            if n["kind"] == "CALL":
                name = p.get("NAME", "unknown")
                args = [expression(c, body, depth+1) for c in children(n)]
                suffix = name.removeprefix("<operator>.")
                return {"op": operators[suffix], "args": args} if suffix in operators else {"op": "call", "callee": p.get("METHOD_FULL_NAME") or name, "args": args}
            return {"op": "unknown", "syntax": p.get("CODE", n["kind"])}
        for n in nodes.values():
            path = n.get("path")
            if not path or path in covered or path.startswith("<") or not n.get("line"):
                continue
            p, args = n["properties"], children(n)
            if n["kind"] == "CALL" and p.get("NAME") == "<operator>.assignment" and len(args) >= 2:
                name, value = args[0]["properties"].get("CODE", "assigned"), args[1]
            elif n["kind"] == "RETURN" and args:
                name, value = f"return@{n['line']}", args[0]
            elif n["kind"] == "CALL" and n["id"] not in nested:
                name, value = f"call_result@{n['line']}", n
            else:
                continue
            body = {"id": ident("cb_", [path, n.get("scope"), analysis["language"]]), "path": path}
            expr = expression(value, body)
            conditions = [{"analyzer_node_id": cid, "expression": nodes[cid]["properties"].get("CODE", ""),
                           "kind": "joern_control_dependency"} for cid in controls.get(n["id"], [])]
            builder.add(body, name, n["line"], expr, expr, {}, conditions, analysis["language"], n["id"], p.get("COLUMN_NUMBER",0))
    extra = builder.build()
    for key in ("templates", "quantities", "transformations", "links", "condition_sets", "guards", "gaps"):
        model[key].extend(extra[key])
    counts = Counter(u["template_id"] for u in model["transformations"])
    model["coverage"].update(transformations=len(model["transformations"]), unique_templates=len(counts),
        shared_templates=sum(n>1 for n in counts.values()), instances_in_shared_templates=sum(n for n in counts.values() if n>1),
        languages=sorted({t["language"] for t in model["templates"]}),
        cpg_lifted_transformations=sum(u["source_id"].startswith("joern:") for u in model["transformations"]))
    for key in ("arithmetic_transformations", "non_reproducer_arithmetic_transformations"):
        model["coverage"][key] += extra["coverage"][key]
    model["symbolic_math"] = symbolic_projection(model)
    existing = {o["id"] for o in payload.get("objects", [])}
    payload.setdefault("objects", []).extend(o for o in attach_computation({"objects": []}, extra)["objects"] if o["id"] not in existing)


if __name__=="__main__":
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    analyze_sources(args.root,args.output)
