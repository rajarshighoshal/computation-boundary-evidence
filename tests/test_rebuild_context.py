import gzip
import importlib.util
import json
from pathlib import Path


def test_rebuild_compares_immutable_initial_graph_not_agent_modified_store(tmp_path):
    path = Path(__file__).resolve().parents[1] / 'scripts/rebuild_context.py'
    spec = importlib.util.spec_from_file_location('rebuild_test', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    store = tmp_path / 'agent/science'
    (store / 'trace').mkdir(parents=True)
    (store / 'packet.json').write_text(json.dumps({'entries':[], 'documents':[]}))
    (store / 'scientific-objects.json').write_text(json.dumps({'objects':[], 'operations':[], 'links':[]}))
    (store / 'state.json').write_text(json.dumps({'scientific_graph':{'nodes':[{},{}]}}))
    initial = store.parent / 'science-initial-state.json'
    initial.write_text(json.dumps({'scientific_graph':{'nodes':[{}]}}))
    with gzip.open(store / 'trace/trace.jsonl.gz', 'wt') as stream:
        stream.write('')
    result = module.rebuild(store, tmp_path / 'output')
    assert result['before']['nodes'] == 1
    assert result['before_snapshot'] == str(initial)
