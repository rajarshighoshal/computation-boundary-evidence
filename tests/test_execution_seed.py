import gzip
import json

from scicontext.execution_seed import read_execution
from scicontext.evidence import executed_region_plan
from scicontext.packet import build_packet
from scicontext.object_context import enrichment_input
from scicontext.representation import reading_input, render_reading
from scicontext.scientific_objects import extract_objects


def trace(root, rows):
    with gzip.open(root / "trace.jsonl.gz", "wt") as stream:
        for row in rows:
            stream.write(json.dumps(row) + "\n")
    return read_execution(root)


def test_completion_order_does_not_change_depth(tmp_path):
    rows = [{"pid": 1, "seq": i, "parent_seq": i - 1, "file": "m.py", "name": str(i), "line": i}
            for i in (1, 2, 3)]
    first = trace(tmp_path, rows)
    second = trace(tmp_path, rows[::-1])
    assert first == second
    assert [r["min_depth"] for r in first["functions"]] == [0, 1, 2]


def test_process_local_sequences_do_not_collide(tmp_path):
    rows = [{"pid": pid, "seq": 1, "file": "m.py", "name": str(pid), "line": pid} for pid in (1, 2)]
    result = trace(tmp_path, rows)
    assert len(result["functions"]) == 2
    assert all(r["min_depth"] == 0 for r in result["functions"])


def test_corrupt_ancestry_is_unknown_not_an_execution_root(tmp_path):
    result = trace(tmp_path, [{"seq": i, "parent_seq": 3-i, "file": "m.py", "name": str(i), "line": i} for i in (1, 2)])
    assert all(r["min_depth"] is None for r in result["functions"])


def test_public_build_failure_is_not_relabelled_completed_science(tmp_path):
    (tmp_path / "run.json").write_text(json.dumps({"status": "completed", "script_status": None}))
    (tmp_path / "script_report.json").write_text(json.dumps({"status": "runner_failure", "error": "CMake configuration failed"}))
    result = trace(tmp_path, [])
    assert result["reproduction_status"] == "runner_failure"
    assert "CMake" in result["reproduction_error"]


def test_module_and_class_frames_do_not_invoke_their_contained_methods(tmp_path):
    (tmp_path / "m.py").write_text("def unused():\n    return 1\nclass C:\n    def method(self):\n        return 2\n")
    plan = executed_region_plan(tmp_path, "m.py", [{"name": "<module>", "line": 1}, {"name": "C", "line": 3}])
    assert plan["regions"] == [] and len(plan["omitted_frames"]) == 2


def test_decorated_nested_callable_uses_exact_source_identity(tmp_path):
    (tmp_path / "m.py").write_text("def outer():\n    @decorator\n    def inner(x):\n        return x*2\n    return inner\n")
    plan = executed_region_plan(tmp_path, "m.py", [{"name": "outer.<locals>.inner", "line": 2}])
    assert plan["regions"][0]["symbol"] == "outer.inner"
    assert plan["regions"][0]["start_line"] == 3


def test_executed_nested_body_survives_to_reader_with_public_science(tmp_path):
    (tmp_path / "reproduce.py").write_text("def report(x):\n    return x\nreport(0)\n")
    (tmp_path / "m.py").write_text("def outer():\n    def core(x):\n        return x*17\n    return core\n")
    (tmp_path / "paper.md").write_text("The state is scaled by seventeen.\n")
    seed = [{"file": "m.py", "name": "outer.<locals>.core", "line": 2, "count": 1, "min_depth": 3},
            {"file": "reproduce.py", "name": "report", "line": 1, "count": 100, "min_depth": 0}]
    packet = build_packet(tmp_path, multilingual=True, seed=seed)
    graph = extract_objects(tmp_path, packet)
    text = render_reading(reading_input(enrichment_input(graph, packet)))
    assert "x*17" in text and "scaled by seventeen" in text
    assert packet["coverage"]["selected_source_paths"][0] == "m.py"
    assert packet["coverage"]["execution_regions"]


def test_seeded_budget_preserves_documented_meaning_and_guards(tmp_path):
    from scicontext.evidence import extract_evidence
    (tmp_path / "m.py").write_text('def core(x, flag):\n    """x is stored energy."""\n    if flag:\n        x=x*2\n    return x\n')
    result = extract_evidence(tmp_path, ["m.py"], max_entries=5, preserve_interfaces=True,
        seeded_regions=[{"path": "m.py", "start_line": 1, "end_line": 5}])
    kinds = {e["kind"] for e in result["entries"]}
    assert {"signature", "docstring", "predicate", "assignment"} <= kinds
