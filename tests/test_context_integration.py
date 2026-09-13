"""Regressions for the actual cleanup/takeover integration failures; no models."""
import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from scicontext import source_backends
from scicontext.object_context import enrichment_input, object_bundle
from scicontext.pier_agent import ScientificCodex


def graph():
    return {"objects": [], "operations": [], "links": [], "unsupported": []}


def test_live_interpret_invokes_source_analysis_before_model():
    order=[]
    async def analyze(): order.append("source")
    async def model(*args): order.append("model"); return {}
    agent=SimpleNamespace(_augment_source_analysis=analyze,_interpret_call=model)
    asyncio.run(ScientificCodex.interpret(agent,"task",30))
    assert order==["source","model"]


def test_cli_delegates_absolute_root_to_existing_backend(tmp_path,monkeypatch):
    calls=[]
    monkeypatch.setattr(source_backends,"analyze_sources",lambda root,out: calls.append((root,out)))
    source_backends.main(["--root",str(tmp_path),"--output",str(tmp_path/"out")])
    assert calls==[(tmp_path,tmp_path/"out")]


def test_analysis_file_metadata_reaches_input():
    source={"id":"as_1","path":"Main.java","start_line":1,"end_line":4,"sha256":"x"}
    result=enrichment_input(graph(),{"entries":[],"documents":[],"analysis_sources":[source]})
    assert result["context"]["analysis_sources"]==[source]


def test_observations_survive_selection_and_assembly_as_metadata():
    g=graph(); observations=[{"field":"boundary_jump","value":1.5}]
    g["dynamic"]={"observed_values":observations}
    payload=enrichment_input(g,{"entries":[],"documents":[]})
    bundle=object_bundle(g,None,payload)
    assert bundle["graph"]["objects"]==[]
    assert bundle["graph"]["dynamic"]["observed_values"]==observations
    assert bundle["context"]["context"]["observations"]==observations


def test_analyzer_ids_preserve_distinct_nodes_and_relation_types():
    nodes=[{"id":"joern:PYTHONSRC:10737418240"+str(i),"kind":"CALL","path":"m.py","line":1,"properties":{"CODE":"f()"}} for i in range(2)]
    edges=[{"source":nodes[0]["id"],"target":nodes[1]["id"],"role":role} for role in ["REF","REACHING_DEF"]]
    payload={"context":{"code_passages":[{"path":"m.py","start_line":1,"end_line":1}]}}
    result=source_backends.attach_source_analysis(payload,{"analyses":[{"backend":"joern","nodes":nodes,"links":edges}]})
    records=result["context"]["analysis_sources"]
    assert len({r["id"] for r in records})==len(records)
    assert [r["kind"] for r in records[:2]]==["CALL","CALL"]
