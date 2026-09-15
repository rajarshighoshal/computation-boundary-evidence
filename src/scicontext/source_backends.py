"""Adapters for existing analyzers. No source execution or replacement type checker."""
from __future__ import annotations

from collections import Counter, defaultdict
from io import BytesIO
from pathlib import Path
import ast
import json
import re
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
    contracts = distill_joern_contracts(nodes, edges, selection, language, root=source_root)
    return {"backend":"joern", "language":language, "nodes":[nodes[v] for v in sorted(keep)],
            "links":edges, "edge_counts":dict(Counter(e["role"] for e in edges)),
            "selection": selection,
            "interface_contracts": contracts,
            "contracts": contracts,
            "scope":"Static code-property graph; external-call dataflow can be conservative, not a scientific contract."}



def _shorten(text, limit=400):
    if not text or not isinstance(text, str):
        return text or ""
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[:limit] + " ... [truncated]"


# Boundary classification, language-agnostic (design note section 3). The scanned
# universe (layer 1) decides "internal"; the caller file's own declarations (layer 2)
# only name a provider; everything else stays `unknown_external` (layer 3).
BOUNDARY_DECLS = {
    "c": (r'^\s*#\s*include\s*[<"](?P<provider>[\w./+-]+)[>"]',),
    "cpp": (r'^\s*#\s*include\s*[<"](?P<provider>[\w./+-]+)[>"]',),
    "fortran": (r'^\s*use\s*(?P<intrinsic>,\s*intrinsic\s*::)?\s*(?P<provider>\w+)',),
    "cython": (r'^\s*cimport\s+(?P<provider>[\w.]+)(?:\s+as\s+(?P<alias>\w+))?',
               r'^\s*from\s+(?P<provider>[\w.]+)\s+cimport\s+(?P<names>[^#\n]+)'),
    "python": (),  # ast Import/ImportFrom, not a regex
    "matlab": (),  # no standard import mechanism: only the core predicate applies
}
BOUNDARY_PATTERNS = {language: tuple(re.compile(p, re.MULTILINE | (re.IGNORECASE if language == "fortran" else 0))
                                     for p in patterns)
                     for language, patterns in BOUNDARY_DECLS.items()}

# Heuristic prefix attribution, always disclosed as `prefix_heuristic` in `basis`.
BOUNDARY_PREFIX_PROVIDERS = (
    ("pthread_", "pthread.h"),
    ("mpi_", "mpi.h"),
    ("MPI_", "mpi.h"),
    ("omp_", "omp.h"),
    ("cuda", "cuda_runtime.h"),
    ("cublas", "cublas_v2.h"),
    ("fftw", "fftw3.h"),
    ("H5", "hdf5.h"),
    ("gsl_", "gsl"),
)
# Fortran intrinsic modules bind names through these prefixes, not through the module name.
FORTRAN_INTRINSIC_MODULES = {
    "iso_c_binding": ("c_",),
    "omp_lib": ("omp_",),
    "openacc": ("acc_",),
    "ieee_arithmetic": ("ieee_",),
    "ieee_exceptions": ("ieee_",),
    "mpi": ("mpi_", "mpi"),
}
_JOERN_LANGUAGES = {"newc": "c", "c": "c", "cpp": "cpp", "c++": "cpp", "cxx": "cpp"}
_NATIVE_LANGUAGES = {"fortran": "fortran", "matlab": "matlab", "cython": "cython"}
_PYTHON_LANGUAGES = {"python": "python", "pythonsrc": "python"}


def boundary_language(language):
    """Map a backend frontend name or source language onto one BOUNDARY_DECLS row."""
    name = (language or "").strip().casefold()
    return _JOERN_LANGUAGES.get(name) or _NATIVE_LANGUAGES.get(name) or _PYTHON_LANGUAGES.get(name) or ""


def _python_import_aliases(text):
    """ast Import/ImportFrom bindings: local name -> module (layer 2 for Python)."""
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError, RecursionError):
        return {}
    aliases = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                aliases[alias.asname or alias.name.split(".")[0]] = alias.name
        elif isinstance(node, ast.ImportFrom) and not node.level and node.module:
            for alias in node.names:
                if alias.name != "*":
                    aliases[alias.asname or alias.name] = node.module
    return aliases


def _declaration_records(text, language):
    """Provider names declared by the caller's own file. Naming only, never proof."""
    declarations = {"includes": [], "modules": [], "aliases": {}}
    if not text:
        return declarations
    if language == "python":
        declarations["aliases"] = _python_import_aliases(text)
        declarations["modules"] = [{"provider": module, "intrinsic": False}
                                   for module in sorted(set(declarations["aliases"].values()))]
        return declarations
    for pattern in BOUNDARY_PATTERNS.get(language, ()):
        for match in pattern.finditer(text):
            provider = match.group("provider")
            groups = match.groupdict()
            if language in {"c", "cpp"}:
                declarations["includes"].append({"provider": provider})
            elif language == "fortran":
                intrinsic = bool(groups.get("intrinsic")) or provider.casefold() in FORTRAN_INTRINSIC_MODULES
                declarations["modules"].append({"provider": provider, "intrinsic": intrinsic})
            else:
                declarations["modules"].append({"provider": provider, "intrinsic": False})
                declarations["aliases"].update(_cython_bindings(provider, groups))
    return declarations


def _cython_bindings(provider, groups):
    """`cimport numpy as np` / `from libc.stdlib cimport malloc, free as release`."""
    bindings = {}
    alias = groups.get("alias")
    if alias:
        bindings[alias] = provider
    elif not groups.get("names"):
        bindings[provider.split(".")[-1]] = provider
    for name in (groups.get("names") or "").split(","):
        parts = name.split(" as ")
        bound = parts[-1].strip()
        if bound.isidentifier():
            bindings[bound] = provider
    return bindings


def _caller_text(root, path, cache):
    """The caller file's own text, read from the repository root; None when unavailable."""
    if root is None or not path or _safe_relative(path):
        return None
    if path not in cache:
        try:
            cache[path] = (Path(root) / path).read_text(encoding="utf-8", errors="replace")
        except (OSError, ValueError, UnicodeError):
            cache[path] = None
    return cache[path]


def _caller_declarations(root, path, language, cache):
    """Layer 2 evidence for one caller file; None when its text is unavailable."""
    if not language:
        return None
    key = ("declarations", language, path)
    if key not in cache:
        text = _caller_text(root, path, cache)
        cache[key] = None if text is None else _declaration_records(text, language)
    return cache[key]


def _name_binds(callee, stem):
    """Exact name or the conventional `stem_` prefix derived from a declaration."""
    return bool(stem) and (callee == stem or callee.startswith(stem + "_"))


def _header_binds(callee, header):
    return _name_binds(callee, re.sub(r"[^0-9A-Za-z_]+", "", header.rsplit("/", 1)[-1].rsplit(".", 1)[0]))


def _module_binds(callee, module):
    return _name_binds(callee, module.split(".")[0]) or _name_binds(callee, module.rsplit(".", 1)[-1])


def _call_root(code):
    match = re.match(r"\s*([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)\s*\(", code or "")
    return match.group(1) if match else ""


def _layer3(declarations):
    if declarations is None:
        return "unknown_external", None, "layer3_no_caller_source"
    if declarations["includes"] or declarations["modules"]:
        return "unknown_external", None, "layer3_no_declaration_match"
    return "unknown_external", None, "layer3_no_declaration"


def _boundary_evidence(language, callee, code, declarations, scanned_modules=frozenset()):
    """Layers 2 and 3 for a callee layer 1 could not place inside the scanned universe."""
    if declarations is None:
        return _layer3(declarations)
    if language in {"c", "cpp"}:
        for include in declarations["includes"]:
            if _header_binds(callee, include["provider"]):
                return "external", include["provider"], f"layer2_include:{include['provider']}"
        for prefix, provider in BOUNDARY_PREFIX_PROVIDERS:
            if callee.startswith(prefix):
                return "external", provider, f"prefix_heuristic:{provider}"
    elif language == "fortran":
        for module in declarations["modules"]:
            prefixes = FORTRAN_INTRINSIC_MODULES.get(module["provider"].casefold()) if module["intrinsic"] else None
            if any(callee.startswith(prefix) for prefix in prefixes or ()) or \
                    (not prefixes and _module_binds(callee, module["provider"])):
                suffix = "(intrinsic)" if module["intrinsic"] else ""
                return "external", module["provider"], f"layer2_use:{module['provider']}{suffix}"
        declared = [m["provider"] for m in declarations["modules"] if not m["intrinsic"]]
        scanned = [name for name in declared if name.casefold() in scanned_modules]
        unscanned = [name for name in declared if name.casefold() not in scanned_modules]
        if scanned:
            # A declared module we already scanned cannot explain an unresolved callee.
            return "unknown_external", None, f"layer3_scanned_module:{scanned[0]}"
        if len(unscanned) == 1:
            # Cross-file Fortran calls require `use`: one unscanned module is the only source left.
            return "external", unscanned[0], f"layer2_use:{unscanned[0]}(only_unscanned_module)"
    else:
        root = _call_root(code)
        for name in dict.fromkeys([callee, (callee or "").split(".")[0], root, root.split(".")[0]]):
            provider = declarations["aliases"].get(name)
            if provider:
                return "external", provider, f"layer2_import:{provider}"
    return _layer3(declarations)


def _boundary(kind, provider=None, basis="", same_file=False):
    """The uniform boundary schema carried on every call record, in every language.

    `assume` records that an external interface is taken as given; `repair_scope` names
    where a repair can live: the caller file for proven-external calls, the repository
    for in-repo definitions in other files, and the repository when the callee is unknown.
    """
    return {
        "kind": kind,
        "provider": _shorten(provider, 80) if provider else None,
        "assume": "correct_interface" if kind == "external" else None,
        "repair_scope": "caller_file" if kind == "external" or (kind == "internal" and same_file) else "repo",
        "basis": _shorten(basis, 120),
    }


def _joern_external_flag(node):
    return node.get("properties", {}).get("IS_EXTERNAL") in (True, "true", "TRUE", 1, "1")


def _scanned_modules(entries):
    """Fortran modules whose definitions the scanned extraction actually covers."""
    modules = set()
    for entry in entries:
        for part in entry.get("scope_chain") or []:
            match = re.search(r"\bmodule:([^@]+)@", part)
            if match:
                modules.add(match.group(1).casefold())
    return modules


def distill_joern_contracts(nodes, links, selection=None, language="unknown", root=None):
    """Distill Joern CPG nodes and edges into clean, dense interface contracts.

    Yields for each method:
    - Boundary signature (name, parameter names/types/order, return type)
    - External calls & library interactions (excluding internal AST operators)
    - Core governing conditions (if/while/for predicates and governed statements)
    - Return expressions and types
    - Boundary types / classes referenced

    Every call record carries the uniform `boundary` classification (layer 1 in-repo
    resolution, layer 2 declarations of the caller file under `root`, layer 3 unknown).
    """
    node_map = {}
    if isinstance(nodes, list):
        for n in nodes:
            node_map[n["id"]] = n
    elif isinstance(nodes, dict):
        for k, v in nodes.items():
            node_map[k] = v
            if isinstance(v, dict) and "id" in v:
                node_map[v["id"]] = v
    methods = []
    if selection and selection.get("methods"):
        methods = selection["methods"]
    else:
        method_nodes = [n for n in node_map.values() if n.get("kind") == "METHOD"]
        if method_nodes:
            methods = [{"id": n["id"], "name": n.get("properties", {}).get("NAME") or n.get("scope", "method"),
                        "node_ids": [n["id"]], "start_line": n.get("line", 0), "end_line": n.get("line", 0)}
                       for n in method_nodes]
        else:
            methods = [{"id": "legacy_region", "name": "boundary_method", "node_ids": list(node_map.keys())}]

    out_edges = defaultdict(list)
    in_edges = defaultdict(list)
    for edge in links or []:
        src, dst = edge.get("source"), edge.get("target")
        out_edges[src].append(edge)
        in_edges[dst].append(edge)

    local_method_ids = {m.get("id") for m in methods} | {n["id"] for n in node_map.values() if n.get("kind") == "METHOD"}
    boundary_lang = boundary_language(language)
    text_cache = {}

    contracts = []
    for m in methods:
        method_body = set(m.get("node_ids", []))
        method_nodes = [node_map[nid] for nid in method_body if nid in node_map]
        if not method_nodes:
            method_nodes = [n for n in node_map.values() if n.get("scope") == m.get("name") or n.get("scope") == m.get("id")]

        m_node = next((n for n in method_nodes if n.get("kind") == "METHOD"), None)
        if not m_node:
            m_node = node_map.get(m.get("id"))
        m_props = m_node.get("properties", {}) if m_node else {}
        m_name = m_props.get("NAME") or m.get("name", "method")
        m_path = m_node.get("path") if m_node else m.get("path", "")
        m_line = m_node.get("line") if m_node else m.get("start_line", 0)
        m_scope = m.get("name") or (m_node.get("scope") if m_node else m_name)

        # 1. Parameters & Return Type
        param_nodes = [n for n in method_nodes if n.get("kind") == "METHOD_PARAMETER_IN"]
        if not param_nodes and m_node:
            param_nodes = [node_map[e["target"]] for e in out_edges[m_node["id"]]
                           if e.get("role") == "AST" and node_map.get(e["target"], {}).get("kind") == "METHOD_PARAMETER_IN"]
        if not param_nodes:
            for nid in method_body:
                for e in in_edges[nid]:
                    src_node = node_map.get(e["source"])
                    if src_node and src_node.get("kind") == "METHOD_PARAMETER_IN" and src_node not in param_nodes:
                        param_nodes.append(src_node)

        def _p_order(p):
            try:
                return int(p.get("properties", {}).get("ORDER", 999))
            except (TypeError, ValueError):
                return 999

        param_nodes.sort(key=_p_order)
        parameters = []
        for p in param_nodes:
            pp = p.get("properties", {})
            parameters.append({
                "name": pp.get("NAME", ""),
                "type": pp.get("TYPE_FULL_NAME") or pp.get("EVALUATION_STRATEGY", ""),
                "order": pp.get("ORDER", len(parameters) + 1)
            })

        ret_node = next((n for n in method_nodes if n.get("kind") == "METHOD_RETURN"), None)
        if not ret_node and m_node:
            ret_node = next((node_map[e["target"]] for e in out_edges[m_node["id"]]
                             if e.get("role") == "AST" and node_map.get(e["target"], {}).get("kind") == "METHOD_RETURN"), None)
        return_type = ret_node.get("properties", {}).get("TYPE_FULL_NAME") if ret_node else (m_props.get("TYPE_FULL_NAME") or "")
        sig = m_props.get("SIGNATURE", "")
        if not sig and parameters:
            sig = f"{return_type or 'void'}({', '.join(p['type'] or 'unknown' for p in parameters)})"

        # 2. Calls & External Library Interactions
        def _is_op(name):
            return bool(name and (name.startswith("<operator>") or name.startswith("<operators>")))

        call_nodes = [n for n in method_nodes if n.get("kind") == "CALL" and not _is_op(n.get("properties", {}).get("NAME"))]
        for nid in method_body:
            for e in out_edges[nid]:
                tgt = node_map.get(e["target"])
                if tgt and tgt.get("kind") == "CALL" and not _is_op(tgt.get("properties", {}).get("NAME")):
                    if tgt not in call_nodes:
                        call_nodes.append(tgt)

        calls = []
        external_calls = []
        local_names = {m.get("name") for m in methods if m.get("name")} | {
            n.get("properties", {}).get("NAME") for n in node_map.values()
            if n.get("kind") == "METHOD" and n.get("properties", {}).get("NAME")
        }
        for call in call_nodes:
            cp = call.get("properties", {})
            callee = cp.get("NAME") or ""
            full_name = cp.get("METHOD_FULL_NAME") or callee
            call_sig = cp.get("SIGNATURE") or ""
            call_ret = cp.get("TYPE_FULL_NAME") or ""
            code = _shorten(cp.get("CODE") or "")
            line = call.get("line") or cp.get("LINE_NUMBER") or 0
            arg_nodes = [node_map[e["target"]] for e in out_edges[call["id"]]
                         if e.get("role") == "ARGUMENT" and e["target"] in node_map]
            def _arg_order(a):
                try:
                    return int(a.get("properties", {}).get("ARGUMENT_INDEX", 999))
                except (TypeError, ValueError):
                    return 999
            arg_nodes.sort(key=_arg_order)
            arguments = [_shorten(a.get("properties", {}).get("CODE") or a.get("properties", {}).get("NAME") or "") for a in arg_nodes if a]
            if not arguments and "(" in code and code.endswith(")"):
                inside = code[code.find("(") + 1 : code.rfind(")")].strip()
                if inside:
                    arguments = [_shorten(arg.strip()) for arg in inside.split(",") if arg.strip()]

            target_methods = [node_map[e["target"]] for e in out_edges[call["id"]]
                              if e.get("role") == "CALL" and node_map.get(e["target"], {}).get("kind") == "METHOD"]
            flagged = [tm for tm in target_methods if _joern_external_flag(tm)]
            resolved = [tm for tm in target_methods if not _joern_external_flag(tm)
                        and (tm.get("path") or tm["id"] in local_method_ids)]
            resolved_ids = {tm["id"] for tm in resolved}
            for tm in target_methods:  # A callee without an in-repo definition still carries its signature.
                if tm["id"] in resolved_ids:
                    continue
                tmp = tm.get("properties", {})
                if not call_sig and tmp.get("SIGNATURE"):
                    call_sig = tmp["SIGNATURE"]
                if not call_ret and tmp.get("TYPE_FULL_NAME"):
                    call_ret = tmp["TYPE_FULL_NAME"]

            declarations = _caller_declarations(root, m_path, boundary_lang, text_cache)
            if flagged:  # Layer 1: Joern already resolved this callee as external.
                provider, boundary_basis = None, "layer1_is_external"
                hint = _boundary_evidence(boundary_lang, callee, code, declarations)
                if hint[0] == "external" and hint[1]:
                    provider, boundary_basis = hint[1], f"{boundary_basis}+{hint[2]}"
                boundary = _boundary("external", provider, boundary_basis)
            elif resolved:  # Layer 1: the definition resolved inside the analysed source.
                anchor = resolved[0]
                boundary = _boundary("internal", None,
                                     "layer1_resolved_in_repo" if anchor.get("path") else "layer1_exported_method",
                                     same_file=bool(anchor.get("path")) and anchor.get("path") == m_path)
            elif callee in local_names and not target_methods:  # Layer 1: method membership.
                boundary = _boundary("internal", None, "layer1_local_member")
            else:  # Layers 2 and 3: declarations of the caller file, else unknown.
                boundary = _boundary(*_boundary_evidence(boundary_lang, callee, code, declarations))
            is_ext = boundary["kind"] != "internal"

            call_record = {
                "callee": callee,
                "full_name": full_name,
                "signature": call_sig,
                "return_type": call_ret,
                "arguments": arguments,
                "line": line,
                "code": code,
                "external": is_ext,
                "boundary": boundary
            }
            calls.append(call_record)
            if is_ext:
                external_calls.append(call_record)

        # 3. Governing Conditions
        ctrl_nodes = [n for n in method_nodes if n.get("kind") == "CONTROL_STRUCTURE"]
        governing_conditions = []
        for ctrl in ctrl_nodes:
            cp = ctrl.get("properties", {})
            ctype = cp.get("CONTROL_STRUCTURE_TYPE") or "CONTROL"
            cline = ctrl.get("line") or cp.get("LINE_NUMBER") or 0
            ccode = cp.get("CODE") or ""
            cond_node = next((node_map[e["target"]] for e in out_edges[ctrl["id"]]
                              if e.get("role") == "CONDITION" and e["target"] in node_map), None)
            cond_text = _shorten(cond_node.get("properties", {}).get("CODE") if cond_node else "")
            if not cond_text and ccode:
                if "(" in ccode and ")" in ccode:
                    cond_text = _shorten(ccode[ccode.find("(") + 1 : ccode.rfind(")")].strip())
                else:
                    cond_text = _shorten(ccode)
            governs = []
            for te in out_edges[ctrl["id"]]:
                if te.get("role") in ("TRUE_BODY", "CDG"):
                    tgt = node_map.get(te["target"])
                    if tgt and tgt["id"] != ctrl["id"]:
                        tcode = _shorten(tgt.get("properties", {}).get("CODE"))
                        if tcode and tcode != cond_text and tcode not in governs:
                            governs.append(tcode)
            for te in out_edges[ctrl["id"]]:
                if te.get("role") == "AST":
                    tgt = node_map.get(te["target"])
                    if tgt and tgt.get("kind") in ("RETURN", "CALL") and not _is_op(tgt.get("properties", {}).get("NAME")):
                        tcode = _shorten(tgt.get("properties", {}).get("CODE"))
                        if tcode and tcode != cond_text and tcode not in governs:
                            governs.append(tcode)

            governing_conditions.append({
                "type": ctype,
                "condition": cond_text,
                "line": cline,
                "code": ccode,
                "governs": governs[:5]
            })

        # 4. Return Expressions
        ret_nodes = [n for n in method_nodes if n.get("kind") == "RETURN"]
        def _ret_order(r):
            try:
                return (int(r.get("line") or r.get("properties", {}).get("LINE_NUMBER") or 0), str(r.get("id", "")))
            except (TypeError, ValueError):
                return (0, str(r.get("id", "")))
        ret_nodes.sort(key=_ret_order)
        return_expressions = []
        for ret in ret_nodes:
            rp = ret.get("properties", {})
            rcode = _shorten(rp.get("CODE") or "")
            rline = ret.get("line") or rp.get("LINE_NUMBER") or 0
            rexpr = next((node_map[e["target"]].get("properties", {}).get("CODE")
                          for e in out_edges[ret["id"]] if e.get("role") in ("AST", "ARGUMENT") and e["target"] in node_map), "")
            if not rexpr and rcode:
                rexpr = rcode.removeprefix("return").rstrip(";").strip()
            rexpr = _shorten(rexpr)
            return_expressions.append({
                "code": rcode,
                "expression": rexpr,
                "line": rline,
                "return_type": return_type
            })

        # 5. Boundary Types
        b_types = set()
        if return_type and return_type != "void":
            b_types.add(return_type)
        for p in parameters:
            if p.get("type"):
                b_types.add(p["type"])
        for c in calls:
            if c.get("return_type") and c["return_type"] != "void":
                b_types.add(c["return_type"])
            fn = c.get("full_name") or ""
            if "::" in fn:
                cls = fn.rsplit("::", 1)[0]
                if cls and not cls.startswith("<"):
                    b_types.add(cls)

        contracts.append({
            "name": m_name,
            "scope": m_scope,
            "path": m_path,
            "line": m_line,
            "signature": sig or m_name,
            "return_type": return_type,
            "parameters": parameters,
            "calls": calls,
            "external_calls": external_calls,
            "governing_conditions": governing_conditions,
            "return_expressions": return_expressions,
            "boundary_types": sorted(b_types)
        })

    return contracts


def distill_fortran_contracts(records):
    """Distill LSP document symbols and hover details into interface contracts."""
    contracts = []
    for rec in records:
        path = rec.get("path", "")
        for iface in rec.get("interfaces", []):
            name = iface.get("name", "")
            line = iface.get("line", 1)
            hover = iface.get("hover", {})
            contents = hover.get("contents", "")
            if isinstance(contents, dict):
                text = contents.get("value", "")
            else:
                text = str(contents)
            text = text.strip().replace("```fortran", "").replace("```", "").strip()
            contracts.append({
                "name": name,
                "scope": f"{path}#{name}",
                "path": path,
                "line": line,
                "signature": text,
                "return_type": "",
                "parameters": [],
                "calls": [],
                "external_calls": [],
                "governing_conditions": [],
                "return_expressions": [],
                "boundary_types": []
            })
    return contracts


def distill_native_contracts(entries, language="unknown", root=None):
    """Distill Tree-sitter native entries into dense interface contracts.

    Every call record carries the uniform `boundary` classification: the scanned
    definition set decides `internal`, the caller file's own declarations under `root`
    name a provider, and anything unexplained stays `unknown_external` with a basis.
    """
    signatures = [e for e in entries if e.get("kind") == "signature" and not e.get("native", {}).get("declaration_only")]
    if not signatures:
        signatures = [e for e in entries if e.get("kind") == "signature"]
    if not signatures:
        scopes = list(dict.fromkeys(e.get("function_scope") or e.get("scope") for e in entries if e.get("function_scope") or e.get("scope")))
        if not scopes:
            return []
        signatures = [{"scope": s, "symbol": s.rsplit(".", 1)[-1].split("@")[0], "text": s,
                       "start_line": min((e["start_line"] for e in entries if (e.get("function_scope") or e.get("scope")) == s), default=1),
                       "path": entries[0].get("path", "") if entries else "",
                       "native": {}} for s in scopes]

    boundary_lang = boundary_language(language)
    normalize = str.casefold if boundary_lang == "fortran" else str
    text_cache = {}
    scanned_modules = _scanned_modules(entries)
    definitions = [(s.get("native", {}).get("function_name") or s.get("symbol") or "", s.get("path"))
                   for s in signatures]
    known_names = {normalize(name) for name, _ in definitions if name}
    definition_paths = {normalize(name): path for name, path in definitions if name}

    contracts = []
    for sig in signatures:
        scope = sig.get("scope")
        name = sig.get("native", {}).get("function_name") or sig.get("symbol") or ""
        path = sig.get("path")
        line = sig.get("start_line")
        sig_text = sig.get("text")
        ret_type = sig.get("native", {}).get("return_type") or ""

        # Parameters
        params = [e for e in entries if e.get("kind") == "parameter" and
                  (e.get("function_scope") == scope or (e.get("scope", "").startswith(scope + ".")))]
        param_list = []
        for i, p in enumerate(params, 1):
            p_sym = p.get("symbol") or (p.get("entity_symbols") or [""])[0] or p.get("text") or ""
            decl = p.get("native", {}).get("declaration_text") or p.get("text") or ""
            p_type = ""
            if decl:
                if "::" in decl:
                    p_type = decl.split("::")[0].strip()
                else:
                    parts = decl.strip().split()
                    if len(parts) >= 2 and p_sym in parts[-1]:
                        p_type = " ".join(parts[:-1])
                    else:
                        p_type = decl
            param_list.append({"name": p_sym, "type": p_type, "order": i})

        # Calls
        calls_raw = [e for e in entries if e.get("kind") == "call" and
                     (e.get("function_scope") == scope or e.get("scope", "").startswith(scope))]
        calls = []
        external_calls = []
        for c in calls_raw:
            expr = c.get("native_expression") or {}
            callee = expr.get("callee") or c.get("text") or ""
            receiver = expr.get("receiver", {}).get("text") if expr.get("receiver") else None
            args = [_shorten(a.get("text")) for a in expr.get("arguments", []) if isinstance(a, dict) and a.get("text")]
            # `known_names` is the scanned definition set; keys are case-folded for Fortran.
            if normalize(callee) in known_names:
                boundary = _boundary("internal", None, "layer1_scanned_definition",
                                     same_file=bool(path) and definition_paths.get(normalize(callee)) == path)
            else:
                boundary = _boundary(*_boundary_evidence(
                    boundary_lang, callee, c.get("text") or callee,
                    _caller_declarations(root, path, boundary_lang, text_cache), scanned_modules))
            is_ext = boundary["kind"] != "internal"
            call_obj = {
                "callee": callee,
                "receiver": receiver,
                "arguments": args,
                "line": c.get("start_line"),
                "code": _shorten(c.get("text")),
                "external": is_ext,
                "boundary": boundary
            }
            calls.append(call_obj)
            if is_ext:
                external_calls.append(call_obj)

        # Conditions
        conditions_raw = [e for e in entries if e.get("kind") in ("comparison", "iteration") and
                          (e.get("function_scope") == scope or e.get("scope", "").startswith(scope))]
        conditions = []
        for cond in conditions_raw:
            parent = cond.get("native", {}).get("parent") or cond.get("kind")
            ptype = "IF" if "if" in parent else "WHILE" if "while" in parent else "FOR" if "for" in parent or "do" in parent else parent.upper()
            conditions.append({
                "type": ptype,
                "condition": _shorten(cond.get("text")),
                "line": cond.get("start_line")
            })

        # Returns
        returns_raw = [e for e in entries if e.get("kind") == "return" and
                       (e.get("function_scope") == scope or e.get("scope", "").startswith(scope))]
        returns = []
        if not ret_type:
            ret_symbols = [r.get("native", {}).get("implicit_output") for r in returns_raw if r.get("native", {}).get("implicit_output")]
            for sym in ret_symbols:
                decl = next((e for e in entries if e.get("kind") == "declaration" and sym in e.get("entity_symbols", []) and (e.get("function_scope") == scope or e.get("scope", "").startswith(scope))), None)
                if decl:
                    decl_text = decl.get("native", {}).get("declaration_text") or decl.get("text") or ""
                    if "::" in decl_text:
                        ret_type = decl_text.split("::")[0].strip()
                        break
                    elif decl_text:
                        parts = decl_text.split()
                        if len(parts) >= 2:
                            ret_type = parts[0].strip()
                            break
        if not ret_type and path:
            # The caller's own file is the only place the declared result type is written.
            src_lines = (_caller_text(root, path, text_cache) or "").splitlines()
            start_l = max(0, (line or 1) - 1)
            end_l = min(len(src_lines), start_l + 80)
            for l in src_lines[start_l:end_l]:
                if "end function" in l.lower() or "end subroutine" in l.lower():
                    break
                for sym in (ret_symbols or [name]):
                    m = re.match(r'^\s*([a-zA-Z0-9_,\s\(\)]+?)\s*::\s*.*?\b' + re.escape(sym) + r'\b', l)
                    if m:
                        ret_type = m.group(1).strip()
                        break
                if ret_type:
                    break
        for ret in returns_raw:
            expr = ret.get("native_expression", {}).get("text") or ret.get("native", {}).get("implicit_output") or ret.get("text")
            returns.append({
                "line": ret.get("start_line"),
                "code": _shorten(ret.get("text")),
                "expression": _shorten(expr),
                "return_type": ret_type
            })

        boundary_types = set()
        if ret_type:
            boundary_types.add(ret_type)
        for p in param_list:
            if p.get("type"):
                boundary_types.add(p["type"])

        contracts.append({
            "name": name,
            "scope": scope,
            "path": path,
            "line": line,
            "signature": sig_text,
            "return_type": ret_type,
            "parameters": param_list,
            "calls": calls,
            "external_calls": external_calls,
            "governing_conditions": conditions,
            "return_expressions": returns,
            "boundary_types": sorted(boundary_types)
        })
    return contracts

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
    contracts = distill_fortran_contracts(records)
    return {"backend":"fortls","version":__version__,"files":records,
            "interface_contracts": contracts, "contracts": contracts,
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


def attach_source_analysis(payload, result, root=None):
    """Keep selected computations; summarize unresolved call-target sets as sets.

    `root` is the analysed source root: layer 2 boundary evidence reads the caller
    file's own declarations from it. Without it, calls stay `unknown_external`.
    """
    records = payload.setdefault("context", {}).setdefault("analysis_sources", [])
    if "serialized_bytes" in payload.get("selection", {}):
        payload["selection"]["serialized_bytes_scope"] = "before_source_analysis"
    seen = {record["id"] for record in records}
    summary = {"backends": [a["backend"] for a in result["analyses"]],
               "joern_nodes": 0, "joern_edges": 0, "omitted_methods": [],
               "gaps": result.get("gaps", []),
               "note": "Method ASTs and boundary facts; unresolved dispatch alternatives are summarized, with all candidates retained in source-analysis.json."}
    all_contracts = []
    for analysis in result.get("analyses", []):
        if analysis.get("backend") == "joern":
            contracts = analysis.get("interface_contracts")
            if not contracts:
                contracts = distill_joern_contracts(analysis.get("nodes", []), analysis.get("links", []),
                                                    analysis.get("selection"), analysis.get("language", "unknown"),
                                                    root=root)
            all_contracts.extend(contracts)
        elif analysis.get("backend") == "fortls":
            contracts = analysis.get("interface_contracts")
            if not contracts:
                contracts = distill_fortran_contracts(analysis.get("files", []))
            all_contracts.extend(contracts)
    summary["interface_contracts"] = all_contracts
    summary["contracts"] = all_contracts
    payload.setdefault("context", {})["interface_contracts"] = all_contracts
    payload["interface_contracts"] = all_contracts
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
            seen.update(r["id"] for r in additions)
            summary["joern_nodes"] += sum(r["kind"] != "edge" for r in additions)
            summary["joern_edges"] += sum(r["kind"] == "edge" for r in additions)
    summary["storage_scope"] = "Full selected evidence on disk; model transport check follows abstraction."
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
