import importlib.util
import json
from pathlib import Path


spec = importlib.util.spec_from_file_location("extractor_report", Path(__file__).parents[1] / "scripts/extractor_report.py")
report = importlib.util.module_from_spec(spec)
spec.loader.exec_module(report)


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


def test_audit_uses_initial_graph_not_agent_edited_store(tmp_path):
    job = tmp_path / "jobs/task-001-science/task_001__synthetic"
    write(job / "run.json", {"task_id": "001", "condition": "science", "status": "completed",
          "stages": [{"name": "prepare", "status": "completed", "index": {"scientific_graph": {"nodes": 99}}}]})
    write(job / "graph-bundle.json", {"graph": {"nodes": [
          {"id": "n1", "path": "original.py", "name": "solve", "kind": "implementation", "source_ids": ["e1"]}], "edges": []}})
    write(job / "agent/science/state.json", {"scientific_graph": {"nodes": [{"id": "edited", "source_ids": ["new"]}]}})
    write(job / "agent/science/packet.json", {"entries": [{"id": "e1"}], "documents": []})
    row = report.task_row(job)
    assert row["graph_snapshot"] == "pre_repair_bundle"
    assert row["nodes"] == 1 and row["implementation_paths"] == ["original.py"]
    assert row["unmatched_packet_source_ids"] == []


def test_paired_audit_excludes_baseline_and_keeps_missing_tasks_explicit(tmp_path):
    write(tmp_path / "schedule.json", {"config": {"task_ids": ["001", "002"]}})
    for arm in ("baseline", "science"):
        write(tmp_path / f"jobs/task-001-{arm}/task_001__synthetic/run.json",
              {"task_id": "001", "condition": arm, "status": "failed", "stages": []})
    output = tmp_path / "audit.json"
    assert report.main(["audit", str(tmp_path), "--output", str(output)]) == 0
    result = json.loads(output.read_text())
    assert len(result["rows"]) == 1 and result["missing_task_ids"] == ["002"]
    assert result["rows"][0]["unmatched_packet_source_ids"] is None


def test_count_only_bundle_is_not_mistaken_for_the_graph(tmp_path):
    write(tmp_path / "graph-bundle.json", {"graph": {"nodes": 20, "edges": 40}})
    write(tmp_path / "agent/science-initial-state.json", {"scientific_graph": {"nodes": [
        {"id": "original", "name": "solve", "source_ids": []}], "edges": []}})
    row = report.task_row(tmp_path)
    assert row["nodes"] == 1 and row["graph_snapshot"] == "pre_repair_state"
