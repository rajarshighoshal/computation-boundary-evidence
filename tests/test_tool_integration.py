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
def test_compact_annotation_cli_builds_graph_without_model_owned_evidence(tmp_path, capsys):
    import json
    from scicontext.tool_cli import main
    root = tmp_path / "task"
    root.mkdir()
    (root / "model.py").write_text("def convert(x):\n    return x * 100\n")
    (root / "paper.md").write_text("Convert metres to centimetres by multiplying by 100.\n")
    context = tmp_path / "context"
    context.mkdir()
    (context / "task_statement.md").write_text("Inspect model.py and paper.md\n")
    packet_path, catalog = tmp_path / "packet.json", tmp_path / "catalog.md"
    assert main(["packet", "--root", str(root), "--context-root", str(context), "--task-id", "synthetic",
                 "--output", str(packet_path), "--catalog", str(catalog)]) == 0
    packet = json.loads(packet_path.read_text())
    entry = next(e for e in packet["entries"] if (e.get("expression") or {}).get("op") == "mul")
    annotation = {"schema_version": "annotations-1.0", "quantities": [], "claims": [
        {"id": "c1", "description": "The conversion follows the supplied multiplicative rule.",
         "formula": "x * 100", "implementation_id": entry["id"],
         "evidence": [{"path": "paper.md", "start_line": 1, "end_line": 1}]}]}
    annotation_path, output = tmp_path / "annotations.json", tmp_path / "bundle.json"
    annotation_path.write_text(json.dumps(annotation))
    assert main(["assemble", "--root", str(root), "--context-root", str(context),
                 "--packet", str(packet_path), "--annotations", str(annotation_path), "--output", str(output)]) == 0
    result = json.loads(output.read_text())
    assert result["assembly"]["usable"]
    assert result["graph"]["task_id"] == "synthetic"
    assert result["analysis"]["code_grounding"][0]["status"] == "source_matched"
    assert all(len(e["sha256"]) == 64 and e["quote"] for e in result["graph"]["evidence"])
    capsys.readouterr()


def test_invalid_annotation_cli_saves_explicit_fallback(tmp_path, capsys):
    import json
    from scicontext.tool_cli import main
    output = tmp_path / "bundle.json"
    assert main(["assemble", "--root", str(tmp_path), "--context-root", str(tmp_path),
                 "--packet", str(tmp_path / "missing-packet.json"),
                 "--annotations", str(tmp_path / "missing-annotations.json"), "--output", str(output)]) == 0
    assert json.loads(output.read_text())["assembly"]["status"] == "invalid_or_missing_annotations"
    capsys.readouterr()


def test_annotation_references_expand_late_computation_once(tmp_path, capsys, monkeypatch):
    import scicontext.packet as packet_module
    from scicontext.tool_cli import main
    root = tmp_path / "task"
    root.mkdir()
    (root / "model.py").write_text("\n".join(f"unused_{i} = {i}" for i in range(260)) +
                                    "\ndef volume(arrays):\n    V = -sum(arrays['rpvi'])\n    return V\n")
    context = tmp_path / "context"
    context.mkdir()
    (context / "task_statement.md").write_text("Inspect scientific computation.\n")
    packet_path, catalog = tmp_path / "packet.json", tmp_path / "catalog.md"
    main(["packet", "--root", str(root), "--context-root", str(context), "--task-id", "late",
          "--output", str(packet_path), "--catalog", str(catalog)])
    initial = json.loads(packet_path.read_text())
    assert not any(e["start_line"] == 262 for e in initial["entries"])
    ref = {"path": "model.py", "start_line": 262, "end_line": 262}
    annotation = {"schema_version": "annotations-1.0", "quantities": [
        {"id": "q_j", "meaning": "Unknown scientific definition", "status": "unresolved",
         "code_ref": {**ref, "symbol": "arrays[\"rpvi\"]"}}], "claims": [
        {"id": "c1", "description": "Conditional volume relation", "formula": "V = -sum(J)",
         "implementation_ref": ref, "quantities": ["q_j"], "bindings": {"J": "arrays['rpvi']"}}]}
    annotation_path, output = tmp_path / "annotations.json", tmp_path / "bundle.json"
    annotation_path.write_text(json.dumps(annotation))
    calls = []
    expand = packet_module.expand_packet
    def counted(*args, **kwargs):
        calls.append(1)
        return expand(*args, **kwargs)
    monkeypatch.setattr(packet_module, "expand_packet", counted)
    args = ["assemble", "--root", str(root), "--context-root", str(context),
            "--packet", str(packet_path), "--annotations", str(annotation_path), "--output", str(output)]
    main(args)
    main(args)
    assert calls == [1]
    result = json.loads(output.read_text())
    expanded = json.loads(packet_path.read_text())
    assert expanded["documents"] == initial["documents"] and expanded["task_id"] == "late"
    assert expanded["annotation_expansion_sha256"]
    assert result["assembly"]["usable"]
    assert result["graph"]["claims"][0]["actual"] is not None
    assert result["analysis"]["code_grounding"][0]["status"] == "source_matched"
    assert result["graph"]["quantities"][0]["code_symbol"] == "arrays['rpvi']"
    assert result["assembly"]["relations"][0]["actual_targets"] == ["V"]
    capsys.readouterr()
