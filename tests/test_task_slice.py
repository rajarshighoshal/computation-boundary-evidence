from scicontext import packet
from scicontext.evidence import extract_evidence
from scicontext.packet import build_packet, expand_packet


def write(root, path, text):
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text)


def test_reproducer_import_reaches_deep_reader_before_shallow_files(tmp_path, monkeypatch):
    for index in range(30):
        write(tmp_path, f'a{index}.py', 'unused = 1\n')
    write(tmp_path, 'reproduce.py', 'from physics.io.common import Reader\nvalue = Reader.read("input")\n')
    write(tmp_path, 'source/src/physics/io/common.py',
          'class Reader:\n' + ''.join(f'    unused{i} = {i}\n' for i in range(160)) +
          '    def read(path):\n        scale = 2\n        return scale * path\n')
    monkeypatch.setattr(packet, 'MAX_SOURCE_FILES', 2)
    monkeypatch.setattr(packet, 'MAX_ENTRIES_PER_FILE', 8)
    result = build_packet(tmp_path)
    assert any(e['text'] == 'return scale * path' for e in result['entries'])
    assert len(result['entries']) <= 16
    assert result == build_packet(tmp_path)


def test_expand_late_region_preserves_ids_context_and_bounds(tmp_path, monkeypatch):
    source = ''.join(f'unused{i} = {i}\n' for i in range(160))
    source += 'def compute(x):\n    y = x * 2\n    z = y + 1\n    return z\n'
    write(tmp_path, 'model.py', source)
    monkeypatch.setattr(packet, 'MAX_ENTRIES_PER_FILE', 6)
    monkeypatch.setattr(packet, 'MAX_ENTRIES', 6)
    before = build_packet(tmp_path)
    before['task_id'] = 'synthetic'
    keep = before['entries'][0]['id']
    after = expand_packet(tmp_path, before, [{'path': 'model.py', 'start_line': 163, 'end_line': 163}], keep_ids=[keep])
    assert len(after['entries']) == 6
    assert keep in {e['id'] for e in after['entries']}
    assert after['documents'] == before['documents'] and after['task_id'] == 'synthetic'
    assert any(e['text'] == 'return z' for e in after['entries'])
    z = next(e for e in after['entries'] if e['text'] == 'z = y + 1')
    y = next(e for e in after['entries'] if e['text'] == 'y = x * 2')
    assert z['local_dependencies'][0]['definition_id'] == y['id']
    assert after == expand_packet(tmp_path, before, [{'path': 'model.py', 'start_line': 163, 'end_line': 163}], keep_ids=[keep])


def test_local_dependencies_are_exact_scoped_and_ambiguity_is_explicit(tmp_path):
    write(tmp_path, 'model.py', 'def f(x, flag):\n    a = x * 2\n    b = a + 1\n    if flag:\n        a = 0\n    c = a + 1\n    d = external(b)\n    return d\ndef g():\n    return a\n')
    entries = extract_evidence(tmp_path, ['model.py'])['entries']
    lookup = {e['text']: e for e in entries}
    assert lookup['b = a + 1']['local_dependencies'][0]['definition_id'] == lookup['a = x * 2']['id']
    assert lookup['c = a + 1']['local_dependencies'][0]['reason'] == 'branch_or_dynamic_binding'
    assert lookup['return a']['local_dependencies'][0]['status'] == 'unresolved'
    assert lookup['d = external(b)']['unresolved_operations'] == ['call']
    assert lookup['d = external(b)']['reads'] == ['b', 'external']


def test_ambiguous_import_is_not_an_invented_edge(tmp_path):
    write(tmp_path, 'reproduce.py', 'from physics.core import solve\ny = solve()\n')
    for prefix in ['one', 'two']:
        write(tmp_path, f'{prefix}/physics/core.py', 'def solve():\n    return 2\n')
    result = build_packet(tmp_path)
    assert result['coverage']['task_local_retrieval']['unresolved'][0]['reason'] == 'ambiguous_or_external_import'


def test_task_named_symbol_and_relative_reexport(tmp_path, monkeypatch):
    root, context = tmp_path / 'root', tmp_path / 'context'
    write(root, 'reproduce.py', 'from physics import solve\nx = solve()\n')
    write(root, 'source/physics/__init__.py', 'from .core import solve\n')
    write(root, 'source/physics/core.py', 'padding = 0\ndef solve():\n    return 2\n')
    monkeypatch.setattr(packet, 'MAX_ENTRIES_PER_FILE', 2)
    result = build_packet(root)
    assert any(e['path'].endswith('core.py') and e['text'] == 'return 2' for e in result['entries'])
    write(context, 'task_statement.md', 'Correct `late_compute`.\n')
    write(root, 'other.py', ''.join(f'padding{i} = 0\n' for i in range(160)) +
          'def late_compute():\n    return 42\n')
    result = build_packet(root, context)
    assert any(e['text'] == 'return 42' for e in result['entries'])


def test_downstream_dependencies_do_not_displace_reproducer_reader(tmp_path, monkeypatch):
    write(tmp_path, 'reproduce.py', 'from reader import read\nresult = read()\n')
    write(tmp_path, 'reader.py', 'from aaa import dependency\ndef read():\n    return dependency()\n')
    write(tmp_path, 'aaa.py', 'def dependency():\n' +
          ''.join(f'    padding{i} = 0\n' for i in range(160)) + '    return 1\n')
    monkeypatch.setattr(packet, 'MAX_ENTRIES', 8)
    result = build_packet(tmp_path)
    assert len(result['entries']) <= 8
    assert any(e['path'] == 'reader.py' and e['text'] == 'return dependency()' for e in result['entries'])
