import hashlib
import json

import pytest

from scicontext.expressions import parse_expression
from scicontext.graph import render_graph, validate_graph
from scicontext.tool_cli import analyze_grounded, checkpoint, main


def graph_for(tmp_path, source="v = d * t\n", start=1, end=1):
    path = tmp_path / "model.py"
    path.write_text(source)
    evidence = {"id": "e_source", "path": "model.py", "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "start_line": start, "end_line": end, "quote": "\n".join(source.splitlines()[start-1:end])}
    return {"schema_version": "1.0", "task_id": "002", "quantities": [],
            "claims": [{"id": "c_speed", "description": "Speed relationship", "relation": parse_expression("d/t"),
                        "actual": parse_expression("d*t"), "bindings": [], "quantity_ids": [], "evidence_ids": ["e_source"],
                        "assumptions": ["same displacement and elapsed time"], "operation": "other", "status": "inferred"}],
            "evidence": [evidence], "observations": [], "unresolved": []}


def test_alignment_is_a_real_component_even_without_unit_anchors(tmp_path):
    graph = graph_for(tmp_path)
    analysis = analyze_grounded(graph, tmp_path)
    assert analysis["code_grounding"][0]["status"] == "source_matched"
    assert analysis["alignments"][0]["status"] == "mismatch"
    assert "structural alignment" in render_graph(graph, analysis)


def test_uncorroborated_actual_is_explicit_in_handoff(tmp_path):
    graph = graph_for(tmp_path, "v = d / t\n")
    analysis = analyze_grounded(graph, tmp_path)
    assert analysis["alignments"][0]["status"] == "unknown"
    text = render_graph(graph, analysis)
    assert "not uniquely corroborated" in text


def test_multiline_expression_only_citation_is_allowed(tmp_path):
    graph = graph_for(tmp_path, "v = (\n    d * t\n)\n", 2, 2)
    assert validate_graph(graph, tmp_path)["valid"]
    assert analyze_grounded(graph, tmp_path)["code_grounding"][0]["status"] == "source_matched"


def test_ambiguous_source_matches_remain_unresolved(tmp_path):
    graph = graph_for(tmp_path, "def first(d,t):\n    return d*t\ndef second(d,t):\n    return d*t\n", 1, 4)
    assert analyze_grounded(graph, tmp_path)["code_grounding"][0]["status"] == "unresolved"


def test_original_task_statement_can_be_cited_without_entering_patch_root(tmp_path):
    root = tmp_path / "task"
    context = tmp_path / "context"
    root.mkdir()
    context.mkdir()
    p = context / "task_statement.md"
    p.write_text("Preserve integrated mass.\n")
    graph = graph_for(root)
    graph["evidence"].append({"id": "e_task", "path": "@context/task_statement.md", "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                              "start_line": 1, "end_line": 1, "quote": "Preserve integrated mass."})
    assert not validate_graph(graph, root)["valid"]
    assert validate_graph(graph, root, context_root=context)["valid"]
    p.write_text("Changed requirement.\n")
    assert not validate_graph(graph, root, context_root=context)["valid"]


def test_checkpoint_performs_alignment_and_retains_raw_graph(tmp_path):
    graph = graph_for(tmp_path)
    p = tmp_path / "draft.json"
    p.write_text(json.dumps(graph))
    output = tmp_path / "checkpoints"
    result = checkpoint(p, tmp_path, output)
    assert result["saved"]
    saved = json.loads((output / result["checkpoint"]).read_text())
    assert saved["graph"] == graph
    assert saved["analysis"]["alignments"][0]["status"] == "mismatch"


@pytest.mark.parametrize("relative", ["outputs/model.py", "./outputs/model.py"])
def test_generated_probe_cannot_become_original_implementation_evidence(tmp_path, relative):
    output = tmp_path / "outputs"
    output.mkdir()
    graph = graph_for(output)
    graph["evidence"][0]["path"] = relative
    validation = validate_graph(graph, tmp_path)
    assert not validation["valid"]
    assert any("not immutable source evidence" in message for message in validation["errors"])
    # Grounding is defensive even if a caller omits graph validation.
    assert analyze_grounded(graph, tmp_path)["code_grounding"][0]["status"] == "unresolved"
    draft = tmp_path / "draft.json"
    draft.write_text(json.dumps(graph))
    result = checkpoint(draft, tmp_path, tmp_path / "checkpoints")
    assert result["saved"] is False
    assert not (tmp_path / "checkpoints").exists()
    with pytest.raises(ValueError, match="not immutable source evidence"):
        main(["cite", "--root", str(tmp_path), relative, "1", "1"])


def test_nested_outputs_package_remains_valid_citable_source(tmp_path, capsys):
    nested = tmp_path / "source" / "outputs"
    nested.mkdir(parents=True)
    graph = graph_for(nested)
    graph["evidence"][0]["path"] = "source/outputs/model.py"
    assert validate_graph(graph, tmp_path)["valid"]
    assert analyze_grounded(graph, tmp_path)["code_grounding"][0]["status"] == "source_matched"
    assert main(["cite", "--root", str(tmp_path), "source/outputs/model.py", "1", "1"]) == 0
    assert json.loads(capsys.readouterr().out)["path"] == "source/outputs/model.py"


def test_generated_output_paths_remain_available_for_probe_observations(tmp_path):
    graph = graph_for(tmp_path)
    graph["observations"] = [{"id": "o_probe", "claim_id": "c_speed",
        "description": "A public scratch probe reported its measurements.",
        "status": "reported", "artifact": "outputs/probe.json"}]
    result = validate_graph(graph, tmp_path)
    assert result["valid"]
    assert any("corroborating runner logs" in message for message in result["warnings"])
