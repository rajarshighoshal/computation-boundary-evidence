"""Library adapters and the extractor's actual analyzer invocation/handoff path."""
import asyncio
import copy
import json
from pathlib import Path
import subprocess
import sys
import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from scicontext.computation import build_computation
from scicontext.source_backends import read_joern, attach_source_analysis
from scicontext.source_backends import frontend_routes, JOERN_SOURCE_ROUTES
from scicontext.pier_agent import ScientificCodex, SCRATCH
from test_computation import python_payload


def test_sympy_is_used_for_symbolic_projection_and_cse():
    model=build_computation(python_payload('def f(x,y):\n    a=x*y\n    b=x*y+1\n    return a+b\n'))
    math=model['symbolic_math']
    assert math['engine']=='sympy' and math['version']=='1.14.0'
    assert math['shared_expressions']
    assert all(r['transformation_id'] in {u['id'] for u in model['transformations']} for r in math['results'])


def test_sympy_does_not_execute_source_strings_or_simplify_source_truth():
    model=build_computation(python_payload('def f(x):\n    y=evil(x)\n    return y\n'))
    assert model['symbolic_math']['unsupported_transformation_ids']
    assert any(t['pattern'].get('op')=='call' for t in model['templates'])


def test_graphson_edges_are_analyzer_owned_and_paths_follow_ast(tmp_path):
    data={'@type':'tinker:graph','@value':{'vertices':[
        {'id':{'@type':'g:Int64','@value':1},'label':'METHOD','properties':{'FILENAME':{'@value':['model.py']}}},
        {'id':{'@value':2},'label':'IDENTIFIER','properties':{'LINE_NUMBER':{'@value':[4]},'CODE':{'@value':['x']}}},
        {'id':{'@value':3},'label':'RETURN','properties':{'LINE_NUMBER':{'@value':[5]}}}],
        'edges':[{'outV':1,'inV':2,'label':'AST'},{'outV':1,'inV':3,'label':'AST'},
                 {'outV':2,'inV':3,'label':'REACHING_DEF','properties':{'VARIABLE':'x'}}]}}
    p=tmp_path/'graph.json';p.write_text(json.dumps(data))
    graph=read_joern(p,tmp_path,'PYTHONSRC')
    assert graph['edge_counts']['REACHING_DEF']==1
    assert all(n.get('path')=='model.py' for n in graph['nodes'])


def test_joern_flow_attaches_without_relabeling_source_matches_as_value_proofs():
    payload=python_payload('def f(x):\n    return x*2\n')
    payload['computation']=build_computation(payload)
    analysis={'analyses':[{'backend':'joern','nodes':[{'id':'j1','kind':'RETURN','path':'model.py','line':2,
                                                   'properties':{'CODE':'return x*2'}}], 'links':[]}], 'gaps':[]}
    result=attach_source_analysis(payload,analysis)
    assert result['computation']['source_analysis_bindings']
    assert result['computation']['source_analysis_bindings'][0]['status'].startswith('source_location')
    assert result['computation']['dataflow_authority']['joern_paths']==['model.py']


def test_real_fortls_symbols_via_supported_entrypoint(tmp_path):
    root=Path(__file__).parent/'fixtures/source_backends/fortran'
    proc=subprocess.run([sys.executable,'-m','scicontext.source_backends','--root',str(root),
                         '--output',str(tmp_path/'out')],capture_output=True,text=True,timeout=30)
    assert proc.returncode==0,proc.stderr
    result=json.loads((tmp_path/'out/receipt.json').read_text())
    fortls=result['analyses'][0]
    assert fortls['backend']=='fortls' and fortls['version']=='3.2.2'
    names=[s['name'] for f in fortls['files'] for s in f['symbols']]
    assert 'scale' in names and 'advance' in names


def test_interpret_invokes_backend_before_model_and_accounts_for_time():
    order=[]
    async def augment():order.append('backend')
    async def interpret(instruction,seconds):
        order.append('model');assert 0<seconds<=300;return {'ok':True}
    agent=SimpleNamespace(_augment_source_analysis=augment,_interpret_call=interpret)
    assert asyncio.run(ScientificCodex.interpret(agent,'task',300))=={'ok':True}
    assert order==['backend','model']


def test_extractor_source_analysis_path_updates_the_model_input(tmp_path,monkeypatch):
    """Exercise download, exact source checks, subprocess invocation and upload."""
    import hashlib
    import scicontext.pier_agent as module
    source='def f(x):\n    return x*2\n'
    payload=python_payload(source)
    for b in payload['context']['function_bodies']:
        b['sha256']=hashlib.sha256(source.encode()).hexdigest()
    payload['computation']=build_computation(payload)
    uploads=[]
    async def download(remote,local):
        local.parent.mkdir(parents=True,exist_ok=True)
        local.write_text(json.dumps(payload) if remote.endswith('scientific-context-input.json') else source)
    async def upload(local,remote):uploads.append((json.loads(local.read_text()),remote))
    async def execute(*command,**kwargs):
        out=Path(command[command.index('--output')+1]);out.mkdir(parents=True)
        (out/'receipt.json').write_text(json.dumps({'analyses':[], 'gaps':[{'reason':'test_backend'}]}))
        return SimpleNamespace(wait=AsyncMock(return_value=0))
    monkeypatch.setattr(module.asyncio,'create_subprocess_exec',execute)
    agent=SimpleNamespace(logs_dir=tmp_path,root='/app/task',extract_environment=SimpleNamespace(download_file=download,upload_file=upload))
    asyncio.run(ScientificCodex._augment_source_analysis(agent))
    assert uploads[0][1]==SCRATCH+'/scientific-context-input.json'
    assert uploads[0][0]['computation']['source_analysis']['gaps'][0]['reason']=='test_backend'
    assert agent._source_analysis_file.is_file()


@pytest.mark.parametrize("aliases,suffixes",JOERN_SOURCE_ROUTES)
def test_all_registered_source_frontends_route_from_capability_list(aliases,suffixes):
    paths=['source/model'+suffix for suffix in sorted(suffixes)]
    routes,gaps=frontend_routes(paths,{aliases[-1]})
    assert routes==[(aliases[-1],paths)] and not gaps


def test_mixed_languages_are_all_routed_once_and_missing_frontend_is_explicit():
    routes,gaps=frontend_routes(['a.py','b.java','c.js','d.ts','e.rs','unknown.zz'], {'PYTHONSRC','JAVASRC','JSSRC'})
    assert [r[0] for r in routes]==['PYTHONSRC','JAVASRC','JSSRC']
    assert routes[2][1]==['c.js','d.ts']
    assert gaps[0]['paths']==['e.rs'] and gaps[0]['reason']=='frontend_unavailable'


@pytest.mark.parametrize("suffix",['.java','.js','.ts','.go','.rs','.rb','.php','.cs','.swift','.abap','.kt'])
def test_joern_only_sources_survive_packet_and_input_selection(tmp_path,suffix):
    from scicontext.packet import build_packet
    from scicontext.scientific_objects import extract_objects
    from scicontext.object_context import enrichment_input
    source=tmp_path/'source';source.mkdir()
    (source/('entry'+suffix)).write_text('public source fixture\n')
    packet=build_packet(tmp_path,multilingual=True)
    path='source/entry'+suffix
    assert path in {s['path'] for s in packet['analysis_sources']}
    payload=enrichment_input(extract_objects(tmp_path,packet),packet,root=tmp_path,connected=True)
    assert path in {s['path'] for s in payload['context']['analysis_sources']}


def test_cpg_only_language_can_create_annotatable_math_and_a_repair_guide():
    from scicontext.object_context import object_bundle
    payload={'context':{'function_bodies':[], 'code_passages':[], 'scientific_passages':[],
                        'analysis_sources':[{'path':'m.js','start_line':1,'end_line':3}]}}
    payload['computation']=build_computation(payload)
    def node(i,kind,code,name=None,index=0):
        return {'id':'joern:JSSRC:'+str(i),'kind':kind,'path':'m.js','line':2,'scope':'advance',
                'properties':{'CODE':code,'NAME':name or code,'ARGUMENT_INDEX':index}}
    nodes=[node(1,'CALL','out=a*b','<operator>.assignment'), node(2,'IDENTIFIER','out',index=1),
           node(3,'CALL','a*b','<operator>.multiplication',2),node(4,'IDENTIFIER','a',index=1),node(5,'IDENTIFIER','b',index=2)]
    edges=[{'source':nodes[a]['id'],'target':nodes[b]['id'],'role':'ARGUMENT'} for a,b in [(0,1),(0,2),(2,3),(2,4)]]
    result={'analyses':[{'backend':'joern','language':'JSSRC','nodes':nodes,'links':edges}],'gaps':[]}
    payload=attach_source_analysis(payload,result)
    unit=payload['computation']['transformations'][0]
    assert payload['computation']['coverage']['cpg_lifted_transformations']==1
    assert payload['computation']['coverage']['transformations']==1
    response={'schema_version':'object-enrichment-1.0','annotations':[{'object_id':unit['id'],'meaning':'Product of supplied quantities.'}]}
    bundle=object_bundle({'objects':[]},response,payload)
    assert 'Product of supplied quantities.' in bundle['handoff']
    assert bundle['assembly']['interpretation_status']=='enriched'
