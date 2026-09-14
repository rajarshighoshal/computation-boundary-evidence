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

from .io import digest_file, digest_json, write_json
from .io import _safe_relative

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
    for method in sorted(raw.get("selection", {}).get("methods", []),
                         key=lambda m: m["end_line"] - m["start_line"], reverse=True):
        for identifier in method["node_ids"]:
            if identifier in nodes:
                nodes[identifier]["scope"] = method["name"]
    kinds = {"CALL","IDENTIFIER","LOCAL","LITERAL","METHOD","METHOD_PARAMETER_IN",
             "METHOD_RETURN","RETURN","CONTROL_STRUCTURE","FIELD_IDENTIFIER","MEMBER","TYPE_DECL"}
    keep = set(nodes) if "selection" in raw else {vid for vid,node in nodes.items() if node["kind"] in kinds}
    relations = {"REACHING_DEF","CDG","CFG","CALL","REF","ARGUMENT","RECEIVER","AST","PARAMETER_LINK","CONDITION","TRUE_BODY","FALSE_BODY"}
    edges = [{"source":nodes[e["outV"]]["id"],"target":nodes[e["inV"]]["id"],
              "role":e["label"],"properties":e.get("properties",{})}
             for e in raw["edges"] if e["label"] in relations and e["outV"] in keep and e["inV"] in keep]
    selection = raw.get("selection", {})
    for method in selection.get("methods", []):
        method["id"] = f"joern:{language}:{method['id']}"
        method["node_ids"] = [f"joern:{language}:{identifier}" for identifier in method["node_ids"]]
    return {"backend":"joern", "language":language, "nodes":[nodes[v] for v in sorted(keep)],
            "links":edges, "edge_counts":dict(Counter(e["role"] for e in edges)),
            "selection": selection,
            "scope":"Static code-property graph; external-call dataflow can be conservative, not a scientific contract."}


def source_regions(payload):
    """Use recovered regions, not full-file inventory entries, as query roots."""
    context = payload.get("context", {})
    records = context.get("analysis_regions") or context.get("function_bodies") or context.get("code_passages", [])
    regions, seen = [], set()
    for item in records:
        path, start, end = item.get("path"), item.get("start_line"), item.get("end_line")
        if not isinstance(path, str) or _safe_relative(path) or path.startswith("@context/"):
            continue
        if type(start) is not int or type(end) is not int or not 1 <= start <= end:
            continue
        key = (path, start, end)
        if key not in seen:
            regions.append({"path": path, "start_line": start, "end_line": end})
            seen.add(key)
    # Multi-line implementation regions precede header-only references. Preserve
    # retrieval order within each category; the query deduplicates enclosing methods.
    regions.sort(key=lambda r: r["start_line"] == r["end_line"])
    return regions


def export_joern_regions(cpg, root, language, output, regions):
    request = output / "regions.json"
    write_json(request, {"regions": regions})
    target = output / "selected.json"
    command = ["joern", "--script", str(Path(__file__).with_name("joern_regions.sc")),
        "--param", f"cpgFile={cpg}", "--param", f"regionsFile={request}", "--param", f"outFile={target}"]
    with (output / "command-1.log").open("w") as log:
        result = subprocess.run(command, cwd=output, stdout=log, stderr=subprocess.STDOUT, check=False)
    if result.returncode:
        raise RuntimeError(f"Joern selected export exited {result.returncode}; see {output}")
    graph = read_joern(target, root, language)
    graph["query_sha256"] = digest_file(Path(__file__).with_name("joern_regions.sc"))
    return graph, command


def joern_graph(root, language, output, regions):
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
    commands = [["joern-parse",str(root),"--language",language,"--output",str(output/"cpg.bin")]]
    started=time.monotonic()
    for index, command in enumerate(commands):
        with (output/f"command-{index}.log").open("w") as log:
            result=subprocess.run(command,cwd=output,stdout=log,stderr=subprocess.STDOUT,check=False,env=environment)
        if result.returncode:
            raise RuntimeError(f"Joern command {index} exited {result.returncode}; see {output}")
    graph, command = export_joern_regions(output/"cpg.bin", root, language, output, regions)
    commands.append(command)
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


def analyze_sources(root, output, regions=None):
    """Analyze an already materialized public-source slice; record unavailable capabilities."""
    root,output=Path(root).resolve(),Path(output).resolve()
    output.mkdir(parents=True,exist_ok=True)
    paths=sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file() and not p.is_symlink())
    by_suffix=Counter(Path(p).suffix.lower() for p in paths)
    result={"source_hashes":{p:digest_file(root/p) for p in paths},"extensions":dict(by_suffix),"analyses":[],"gaps":[]}
    result["adapter_sha256"]=digest_file(Path(__file__))
    result["executables"]={name:{"path":str(Path(shutil.which(name)).resolve()),
                                 "sha256":digest_file(Path(shutil.which(name)).resolve())}
                           for name in ("joern-parse","joern") if shutil.which(name)}
    if shutil.which("joern-parse") and shutil.which("joern"):
        available = installed_frontends()
        result["available_frontends"] = sorted(available)
        routes, gaps = frontend_routes(paths, available)
        result["gaps"].extend(gaps)
        for language, selected in routes:
            requested = [r for r in regions or [] if r["path"] in selected]
            if not requested:
                result["gaps"].append({"backend":"joern", "language":language, "reason":"no_task_regions"})
                continue
            try:
                graph = joern_graph(root,language,output/language.lower(),requested)
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
    """Keep selected computations; summarize unresolved call-target sets as sets."""
    from .object_context import ENRICHMENT_MAX_BYTES
    records = payload.setdefault("context", {}).setdefault("analysis_sources", [])
    if "serialized_bytes" in payload.get("selection", {}):
        payload["selection"]["serialized_bytes_scope"] = "before_source_analysis"
    seen = {record["id"] for record in records}
    summary = {"backends": [a["backend"] for a in result["analyses"]],
               "joern_nodes": 0, "joern_edges": 0, "omitted_methods": [],
               "gaps": result.get("gaps", []),
               "note": "Method ASTs and boundary facts; unresolved dispatch alternatives are summarized, with all candidates retained in source-analysis.json."}
    payload["source_analysis_summary"] = summary
    for analysis in result["analyses"]:
        if analysis["backend"] != "joern":
            continue
        nodes = {n["id"]: n for n in analysis["nodes"]}
        summary["omitted_methods"].extend(analysis.get("selection", {}).get("omissions", []))
        methods = analysis.get("selection", {}).get("methods")
        # Legacy normalized fixtures lack method membership; preserve their single
        # available neighborhood without presenting it as recovered method identity.
        groups = methods if methods is not None else [{"id": "legacy_region", "node_ids": list(nodes)}]
        method_nodes = {identifier for group in groups for identifier in group["node_ids"]}
        candidates = {}
        for edge in analysis["links"]:
            if (edge["role"] == "CALL" and edge["target"] not in method_nodes and
                    nodes.get(edge["target"], {}).get("kind") == "METHOD"):
                candidates.setdefault(edge["source"], set()).add(edge["target"])
        ambiguous = {source: targets for source, targets in candidates.items() if len(targets) > 1}
        links = [edge for edge in analysis["links"] if not (
            edge["role"] == "CALL" and edge["target"] in ambiguous.get(edge["source"], set()))]
        for method in groups:
            body = set(method["node_ids"])
            edges = [e for e in links if e["source"] in body or e["target"] in body]
            endpoints = body | {e[k] for e in edges for k in ("source", "target")}
            additions = []
            for identifier in sorted(endpoints):
                node = nodes.get(identifier)
                if node is None:
                    continue
                properties = node.get("properties", {})
                name = properties.get("NAME", "")
                record = {"id": "sa_" + identifier,
                    "path": node.get("path") or "analysis://joern/boundary",
                    "start_line": node.get("line") or 0, "end_line": node.get("line") or 0,
                    "text": properties.get("CODE") or name or node["kind"],
                    "analyzer": "joern", "kind": node["kind"],
                    "scope": node.get("scope"),
                    "language": analysis.get("language", "unknown"),
                    "properties": {key: value for key, value in properties.items() if key != "CODE"}}
                if identifier in ambiguous:
                    record["dispatch"] = {"status": "unresolved_alternatives",
                        "boundary_candidate_count": len(ambiguous[identifier]),
                        "evidence": {"artifact": "source-analysis.json", "source_id": identifier},
                        "note": "These are alternative static targets, not a sequence of calls or proven dispatch."}
                additions.append(record)
            for edge in edges:
                additions.append({"id": "sl_" + digest_json(edge)[:24],
                    "analyzer": "joern", "kind": "edge",
                    "source": "sa_" + edge["source"], "target": "sa_" + edge["target"],
                    "relation": edge["role"], "properties": edge.get("properties", {})})
            additions = [r for r in additions if r["id"] not in seen]
            records.extend(additions)
            # Reserve space for the small selection receipt, never split a method
            # or detach a branch/operand just to squeeze in another graph fragment.
            if len(json.dumps(payload, ensure_ascii=False).encode()) > ENRICHMENT_MAX_BYTES - 8192:
                if additions:
                    del records[-len(additions):]
                summary["omitted_methods"].append({"method_id": method["id"], "reason": "whole_method_exceeds_input_budget"})
            else:
                seen.update(r["id"] for r in additions)
                summary["joern_nodes"] += sum(r["kind"] != "edge" for r in additions)
                summary["joern_edges"] += sum(r["kind"] == "edge" for r in additions)
    summary["within_input_budget"] = False
    if len(json.dumps(payload, ensure_ascii=False).encode()) <= ENRICHMENT_MAX_BYTES:
        summary["within_input_budget"] = True
    return payload




def main(argv: list[str] | None = None) -> int:
    """CLI: run installed analyzers on the given source root, write receipt."""
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--input", type=Path, help="Public enrichment input containing retrieved source regions")
    args = parser.parse_args(argv)
    if args.input:
        analyze_sources(args.root, args.output, source_regions(json.loads(args.input.read_text())))
    else:
        analyze_sources(args.root, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
