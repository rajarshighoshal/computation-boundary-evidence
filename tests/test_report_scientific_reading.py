"""Scientific-object delivery counts do not stand in for scientific correctness."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from report_scientific_reading import summarize_graph


def test_missing_graph_is_unknown_not_zero_quality():
    assert summarize_graph(None) is None
    assert summarize_graph({"schema_version": "legacy", "claims": []}) is None


def test_counts_keep_driver_annotations_separate_from_implementation_coverage():
    graph = {"schema_version": "scientific-objects-1.0", "objects": [
        {"kind": "code_interface", "path": "reproduce.py", "interpretation": {"meaning": "A scientific observation driver."}},
        {"kind": "code_interface", "path": "source/model.m"},
        {"kind": "computational_value", "path": "reproduce.py", "interpretation": {"meaning": "A measurement."}},
    ], "coverage": {"recognized_scientific_operations": 0}, "enrichment": {"dropped": []}}
    result = summarize_graph(graph)
    assert result["objects"] == 3 and result["interpreted_objects"] == 2
    assert result["interfaces"] == 2 and result["interpreted_interfaces"] == 1
    assert result["interpreted_source_paths"] == ["reproduce.py"]
    assert result["source_paths"] == ["reproduce.py", "source/model.m"]
    assert "scientific_correctness" not in result
