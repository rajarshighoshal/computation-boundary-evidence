import copy
import hashlib

import pytest
from jsonschema import Draft202012Validator

from scicontext.annotations import annotation_schema, assemble_annotations
from scicontext.evidence import extract_evidence
from scicontext.expressions import parse_expression
from scicontext.io import digest_json


def annotations(claims=None, **fields):
    return {"schema_version": "annotations-1.0", "quantities": [],
            "claims": claims or [], **fields}


def backed_claim(identifier="c_speed", **fields):
    return {"id": identifier, "description": "Speed is displacement divided by elapsed time.",
            "evidence": ["doc_speed"], **fields}


@pytest.fixture
def source_packet(tmp_path):
    (tmp_path / "model.py").write_text("def speed(d, t):\n    return d * t\n", encoding="utf-8")
    readme = tmp_path / "README.md"
    readme.write_text("# Speed\nSpeed is displacement divided by elapsed time.\n", encoding="utf-8")
    index = extract_evidence(tmp_path)
    document = {"id": "doc_speed", "path": "README.md", "sha256": hashlib.sha256(readme.read_bytes()).hexdigest(),
                "start_line": 2, "end_line": 2, "quote": "Speed is displacement divided by elapsed time."}
    packet = {"schema_version": "packet-1.0", "task_id": "002", "entries": index["entries"],
              "documents": [document], "coverage": index["coverage"]}
    entry = next(entry for entry in index["entries"] if entry["kind"] == "return")
    return tmp_path, packet, entry


def test_schema_has_optional_annotation_fields_and_bounded_arrays():
    schema = annotation_schema()
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    minimal = annotations([{"id": "c_one", "description": "Scientific relationship"}],
                          quantities=[{"id": "q_one", "meaning": "Elapsed time"}])
    assert validator.is_valid(minimal)
    assert schema["properties"]["claims"]["maxItems"] == 5
    assert schema["properties"]["quantities"]["maxItems"] == 12
    assert schema["properties"]["probes"]["maxItems"] == 2
    assert "task_id" not in schema["properties"]
    assert not validator.is_valid({**minimal, "observations": []})
    assert not validator.is_valid(annotations([{"id": "c_one", "description": "x", "actual": {"op": "symbol", "name": "x"}}]))
    schema["properties"]["claims"]["maxItems"] = 99
    assert annotation_schema()["properties"]["claims"]["maxItems"] == 5


def test_assembly_copies_source_trees_and_reuses_grounded_alignment(source_packet):
    root, packet, entry = source_packet
    draft = annotations([backed_claim(formula="distance / time", implementation_id=entry["id"],
                                     bindings={"distance": "d", "time": "t"}, quantities=["q_time"])],
                        quantities=[{"id": "q_time", "meaning": "Elapsed time", "symbol": "t",
                                     "dimensions": {"T": 1, "L": "2/4"}, "scale": "2/4"}])
    originals = copy.deepcopy((draft, packet))
    bundle = assemble_annotations(draft, packet, root)
    assert bundle["validation"]["valid"]
    assert bundle["assembly"]["usable"] and not bundle["assembly"]["abstained"]
    claim = bundle["graph"]["claims"][0]
    assert claim["actual"] == entry["expression"]
    assert claim["actual"] is not entry["expression"]
    assert claim["relation"] == parse_expression("distance / time")
    assert claim["operation"] == "other" and claim["status"] == "inferred"
    quantity = bundle["graph"]["quantities"][0]
    assert quantity["name"] == "t" and quantity["scale"] == "1/2"
    assert quantity["dimensions"] == [{"dimension": "T", "exponent": "1"}, {"dimension": "L", "exponent": "1/2"}]
    assert bundle["analysis"]["alignments"][0]["status"] == "mismatch"
    assert bundle["analysis"]["code_grounding"][0]["status"] == "source_matched"
    assert "structural alignment" in bundle["handoff"]
    assert bundle["graph_sha256"] == digest_json(bundle["graph"])
    assert (draft, packet) == originals


def test_exact_full_source_lines_and_deduplicated_references(source_packet):
    root, packet, entry = source_packet
    explicit = {"path": "model.py", "start_line": 2, "end_line": 2}
    draft = annotations([backed_claim(evidence=[entry["id"], explicit, entry["id"]], implementation_id=entry["id"])])
    # Packet AST text can omit indentation; source code owns the final exact quote.
    assert entry["text"] == "return d * t"
    bundle = assemble_annotations(draft, packet, root)
    assert bundle["validation"]["valid"]
    assert len(bundle["graph"]["evidence"]) == 1
    assert bundle["graph"]["evidence"][0]["quote"] == "    return d * t"
    assert len(bundle["graph"]["claims"][0]["evidence_ids"]) == 1


def test_missing_evidence_and_quantities_do_not_discard_independent_claim(source_packet):
    root, packet, _ = source_packet
    draft = annotations([backed_claim("c_bad_ref", evidence=["invented"]),
                         backed_claim("c_bad_quantity", quantities=["q_missing"]),
                         backed_claim("c_usable", evidence=["invented", "doc_speed"])])
    bundle = assemble_annotations(draft, packet, root)
    assert bundle["validation"]["valid"]
    assert bundle["assembly"]["accepted_claim_ids"] == ["c_usable"]
    assert {item["id"] for item in bundle["assembly"]["rejected"]} == {"c_bad_ref", "c_bad_quantity"}
    assert "invented" in " ".join(bundle["assembly"]["unresolved"])
    assert len(bundle["graph"]["evidence"]) == 1


@pytest.mark.parametrize("implementation", ["missing_entry", "doc_speed", None])
def test_missing_implementation_is_unknown_not_invented(source_packet, implementation):
    root, packet, _ = source_packet
    bundle = assemble_annotations(annotations([backed_claim(implementation_id=implementation)]), packet, root)
    assert bundle["validation"]["valid"]
    assert bundle["graph"]["claims"][0]["actual"] is None
    assert bundle["analysis"]["alignments"][0]["status"] == "unknown"
    assert bundle["assembly"]["unresolved"]


def test_unsupported_formula_and_augmented_assignment_stay_unknown(source_packet):
    root, packet, _ = source_packet
    (root / "model.py").write_text("value += distance / time\n")
    packet["entries"] = extract_evidence(root)["entries"]
    bundle = assemble_annotations(annotations([backed_claim(formula="solve(distance, time)",
                                implementation_id=packet["entries"][0]["id"])]), packet, root)
    assert bundle["validation"]["valid"]
    assert bundle["graph"]["claims"][0]["relation"]["op"] == "unknown"
    assert bundle["graph"]["claims"][0]["actual"] is None
    assert bundle["analysis"]["alignments"][0]["status"] == "unknown"


def test_stale_source_prevents_copying_old_implementation(source_packet):
    root, packet, entry = source_packet
    (root / "model.py").write_text("def speed(d, t):\n    return d / t\n")
    bundle = assemble_annotations(annotations([backed_claim(implementation_id=entry["id"])]), packet, root)
    assert bundle["validation"]["valid"]
    assert bundle["graph"]["claims"][0]["actual"] is None
    assert "stale packet source hash" in " ".join(bundle["assembly"]["unresolved"])


def test_source_operands_and_equation_output_keep_science_unknown(tmp_path):
    (tmp_path / "model.py").write_text("def volume(arrays):\n    V = -sum(arrays['rpvi'])\n    return V\n")
    packet = {"task_id": "example", "entries": extract_evidence(tmp_path)["entries"], "documents": []}
    ref = {"path": "model.py", "start_line": 2, "end_line": 2}
    draft = annotations([{"id": "c_volume", "description": "Proposed signed volume relation",
                         "formula": "V = -sum(J)", "implementation_ref": ref,
                         "quantities": ["q_j"], "bindings": {"J": "arrays[\"rpvi\"]"},
                         "status": "unresolved"}],
                        quantities=[{"id": "q_j", "meaning": "Scientific definition unavailable",
                                     "status": "unresolved", "code_ref": {**ref, "symbol": 'arrays["rpvi"]'}}],
                        unresolved=["Projection frame and normalization are unspecified."])
    bundle = assemble_annotations(draft, packet, tmp_path)
    assert bundle["validation"]["valid"]
    quantity = bundle["graph"]["quantities"][0]
    assert quantity["code_symbol"] == "arrays['rpvi']"
    assert quantity["evidence_ids"] and quantity["status"] == "unresolved"
    assert quantity["dimensions"] is None and quantity["scale"] is None and quantity["shape"] is None
    record = bundle["assembly"]["relations"][0]
    assert record["target"] == "V" and record["actual_targets"] == ["V"]
    assert bundle["graph"]["claims"][0]["bindings"] == [{"expected": "J", "actual": "arrays['rpvi']"}]
    assert bundle["analysis"]["code_grounding"][0]["status"] == "source_matched"
    assert "scientific target='V'" in bundle["handoff"]
    assert "Projection frame and normalization are unspecified." in bundle["handoff"]


def test_unknown_cast_is_source_grounded_without_claiming_equivalence(tmp_path):
    (tmp_path / "model.py").write_text("import numpy as np\ndef volume(bjac_i):\n    V = -float(np.sum(bjac_i))\n")
    packet = {"entries": extract_evidence(tmp_path)["entries"]}
    draft = annotations([{"id": "c_v", "description": "Conditional volume formula", "formula": "V = -sum(J)",
                         "implementation_ref": {"path": "model.py", "start_line": 3, "end_line": 3},
                         "bindings": {"J": "bjac_i"}}])
    bundle = assemble_annotations(draft, packet, tmp_path)
    assert bundle["assembly"]["usable"]
    assert bundle["graph"]["claims"][0]["actual"]["args"][0]["op"] == "unknown"
    assert bundle["analysis"]["code_grounding"][0]["status"] == "source_matched"
    assert bundle["analysis"]["alignments"][0]["status"] == "unknown"


@pytest.mark.parametrize("reference", [
    {"path": "model.py", "start_line": 1, "end_line": 4, "symbol": "x"},
    {"path": "model.py", "start_line": 2, "end_line": 2, "symbol": "missing"},
    {"path": "model.py", "start_line": 2, "end_line": 2, "symbol": "x", "scope": "wrong"},
])
def test_ambiguous_or_unproven_operand_does_not_fall_back_to_model_symbol(tmp_path, reference):
    (tmp_path / "model.py").write_text("def first(x):\n    return x * 2\ndef second(x):\n    return x * 3\n")
    packet = {"entries": extract_evidence(tmp_path)["entries"]}
    draft = annotations(quantities=[{"id": "q_x", "meaning": "unknown", "symbol": "invented",
                                     "code_ref": reference}])
    bundle = assemble_annotations(draft, packet, tmp_path)
    assert bundle["graph"]["quantities"][0]["code_symbol"] is None
    assert bundle["assembly"]["code_bindings"][0]["status"] == "unknown"


def test_exact_scope_selects_operand_without_inventing_semantics(tmp_path):
    (tmp_path / "model.py").write_text("def first(x):\n    return x * 2\ndef second(x):\n    return x * 3\n")
    packet = {"entries": extract_evidence(tmp_path)["entries"]}
    ref = {"path": "model.py", "start_line": 4, "end_line": 4,
           "symbol": "x", "scope": "<module>.second@3"}
    bundle = assemble_annotations(annotations(quantities=[{"id": "q_x", "meaning": "unknown", "code_ref": ref}]), packet, tmp_path)
    assert bundle["graph"]["quantities"][0]["code_symbol"] == "x"
    assert bundle["assembly"]["code_bindings"][0]["start_line"] == 4


def test_quantity_meaning_does_not_cross_functions_with_the_same_operand(tmp_path):
    (tmp_path / "model.py").write_text("def length(x):\n    return x * 2\ndef duration(x):\n    return x * 3\n")
    packet = {"entries": extract_evidence(tmp_path)["entries"]}
    first = {"path": "model.py", "start_line": 2, "end_line": 2}
    second = {"path": "model.py", "start_line": 4, "end_line": 4}
    draft = annotations([
        {"id": "c_length", "description": "Length relation", "formula": "x * 2",
         "implementation_ref": first, "quantities": ["q_length"]},
        {"id": "c_duration", "description": "A different x is elapsed time", "formula": "x * 3",
         "implementation_ref": second, "quantities": ["q_length"]}],
        quantities=[{"id": "q_length", "name": "x", "meaning": "Length in the first function only",
                     "dimensions": {"L": 1}, "status": "explicit", "code_ref": {**first, "symbol": "x"}}])
    bundle = assemble_annotations(draft, packet, tmp_path)
    assert bundle["assembly"]["usable"]
    assert bundle["assembly"]["code_bindings"][0]["status"] == "source_matched"
    assert bundle["graph"]["quantities"][0]["status"] == "explicit"
    assert bundle["graph"]["claims"][0]["quantity_ids"] == ["q_length"]
    assert bundle["graph"]["claims"][1]["quantity_ids"] == []
    properties = {f["claim_id"]: f["properties"] for f in bundle["analysis"]["findings"]
                  if f["kind"] == "actual_properties"}
    assert properties["c_length"]["dimensions"] == {"L": "1"}
    assert properties["c_duration"]["dimensions"] is None
    assert bundle["assembly"]["scientific_binding_uses"][0]["status"] == "unknown"
    assert "q_length excluded from scientific propagation" in bundle["handoff"]


def test_selected_dependency_locations_reach_handoff_and_unknown_stays_unknown(tmp_path):
    (tmp_path / "model.py").write_text("def compute(external):\n    local = 2\n    result = local + external\n    return result\n")
    packet = {"entries": extract_evidence(tmp_path)["entries"]}
    draft = annotations([{"id": "c_local", "description": "Local computation",
                         "implementation_ref": {"path": "model.py", "start_line": 3, "end_line": 3}}])
    bundle = assemble_annotations(draft, packet, tmp_path)
    links = {link["read"]: link for link in bundle["assembly"]["selected_dependencies"]}
    assert links["local"]["status"] == "resolved"
    assert links["local"]["definition"]["start_line"] == 2
    assert links["external"]["status"] == "unknown"
    assert "read 'local' at model.py:3-3 -> model.py:2-2" in bundle["handoff"]
    assert "read 'external' at model.py:3-3 -> unknown" in bundle["handoff"]


def test_document_quote_is_read_from_source_but_snapshot_hash_is_enforced(source_packet):
    root, packet, _ = source_packet
    packet["documents"][0]["quote"] = "invented quotation"
    bundle = assemble_annotations(annotations([backed_claim()]), packet, root)
    assert bundle["graph"]["evidence"][0]["quote"] == "Speed is displacement divided by elapsed time."
    (root / "README.md").write_text("Different scientific specification\n")
    bundle = assemble_annotations(annotations([backed_claim()]), packet, root)
    assert bundle["assembly"]["abstained"]
    assert not bundle["handoff"]


@pytest.mark.parametrize("path", ["../README.md", "/etc/passwd", ".hidden.py", "private_tests/test.py",
                                 "outputs/probe.py", "tokens.json", "@context/other.md"])
def test_unsafe_or_generated_citations_are_rejected(source_packet, path):
    root, packet, _ = source_packet
    bundle = assemble_annotations(annotations([backed_claim(evidence=[{"path": path, "start_line": 1, "end_line": 1}])]), packet, root)
    assert bundle["validation"]["valid"]
    assert bundle["assembly"]["abstained"]
    assert bundle["assembly"]["rejected"]
    assert bundle["graph"]["evidence"] == []


def test_symlink_citations_do_not_resolve(source_packet):
    root, packet, _ = source_packet
    (root / "linked.md").symlink_to(root / "README.md")
    bundle = assemble_annotations(annotations([backed_claim(evidence=[{"path": "linked.md", "start_line": 1, "end_line": 1}])]), packet, root)
    assert bundle["assembly"]["abstained"]
    assert "symlink" in " ".join(bundle["assembly"]["unresolved"])


def test_task_context_comes_from_separate_explicit_root(source_packet, tmp_path):
    root, packet, _ = source_packet
    context = tmp_path / "context"
    context.mkdir()
    (context / "task_statement.md").write_text("Preserve the speed relationship.\n")
    reference = {"path": "@context/task_statement.md", "start_line": 1, "end_line": 1}
    draft = annotations([backed_claim(evidence=[reference])])
    assert assemble_annotations(draft, packet, root)["assembly"]["abstained"]
    bundle = assemble_annotations(draft, packet, root, context_root=context)
    assert bundle["validation"]["valid"] and bundle["assembly"]["usable"]
    assert bundle["graph"]["evidence"][0]["path"] == "@context/task_statement.md"
    assert bundle["graph"]["evidence"][0]["quote"] == "Preserve the speed relationship."


def test_malformed_quantity_does_not_poison_other_claims(source_packet):
    root, packet, _ = source_packet
    draft = annotations([backed_claim("c_bad", quantities=["q_bad"]), backed_claim("c_good")],
                        quantities=[{"id": "q_bad", "meaning": "Invalid rational", "scale": "0"},
                                    {"id": "q_explicit", "meaning": "Unsupported explicit quantity", "status": "explicit"},
                                    {"id": "q_good", "meaning": "Unknown time units"}])
    bundle = assemble_annotations(draft, packet, root)
    assert bundle["validation"]["valid"]
    assert bundle["assembly"]["accepted_quantity_ids"] == ["q_good"]
    assert bundle["assembly"]["accepted_claim_ids"] == ["c_good"]


def test_model_written_graph_nodes_are_rejected_per_claim(source_packet):
    root, packet, _ = source_packet
    draft = annotations([backed_claim("c_fabricated", actual=parse_expression("d/t")), backed_claim("c_good")])
    bundle = assemble_annotations(draft, packet, root)
    assert bundle["assembly"]["accepted_claim_ids"] == ["c_good"]
    assert "Additional properties" in bundle["assembly"]["rejected"][0]["reason"]


def test_annotation_caps_and_duplicate_ids_are_reported(source_packet):
    root, packet, _ = source_packet
    draft = annotations([backed_claim(f"c_{index}") for index in range(7)],
                        quantities=[{"id": f"q_{index}", "meaning": "Time"} for index in range(13)])
    bundle = assemble_annotations(draft, packet, root)
    assert bundle["validation"]["valid"]
    assert len(bundle["graph"]["claims"]) == 5 and len(bundle["graph"]["quantities"]) == 12
    assert len(bundle["assembly"]["rejected"]) == 3
    draft = annotations([backed_claim("same"), backed_claim("same"), backed_claim("other")])
    bundle = assemble_annotations(draft, packet, root)
    assert bundle["assembly"]["accepted_claim_ids"] == ["same", "other"]
    assert "duplicate annotation id" in bundle["assembly"]["rejected"][0]["reason"]


def test_global_graph_node_bound_preserves_smaller_independent_claim(source_packet):
    root, packet, _ = source_packet
    (root / "many.md").write_text("\n".join(f"Scientific statement {i}" for i in range(64)))
    many_refs = [{"path": "many.md", "start_line": i, "end_line": i} for i in range(1, 65)]
    draft = annotations([backed_claim("c_large", evidence=many_refs), backed_claim("c_small")])
    bundle = assemble_annotations(draft, packet, root)
    assert bundle["validation"]["valid"]
    assert bundle["assembly"]["accepted_claim_ids"] == ["c_small"]
    assert "graph node cap exceeded (64)" in bundle["assembly"]["rejected"][0]["reason"]
    assert len(bundle["graph"]["evidence"]) == 1


@pytest.mark.parametrize("draft", [annotations(), {}, {"schema_version": "annotations-1.0", "quantities": [], "claims": "bad"}])
def test_empty_or_malformed_artifact_abstains_without_usable_handoff(source_packet, draft):
    root, packet, _ = source_packet
    bundle = assemble_annotations(draft, packet, root)
    assert bundle["validation"]["valid"]
    assert bundle["assembly"]["abstained"] and not bundle["assembly"]["usable"]
    assert bundle["handoff"] == ""
    assert "Abstained" in " ".join(bundle["graph"]["unresolved"])


def probe(identifier="p_speed", **fields):
    return {"id": identifier, "claim_ids": ["c_speed"], "script": "probes/speed.py",
            "description": "Measure speed for a simple case.", **fields}


@pytest.mark.parametrize("path", ["/tmp/probe.py", "../probe.py", "probes/../probe.py", ".hidden/probe.py",
                                 "probes/.probe.py", "./probe.py", "probes//probe.py", "probe.sh", "probe.py;touch x"])
def test_unsafe_probe_paths_rejected(source_packet, path):
    root, packet, _ = source_packet
    bundle = assemble_annotations(annotations([backed_claim()], probes=[probe(script=path)]), packet, root)
    assert bundle["probes"] == []
    assert bundle["assembly"]["accepted_claim_ids"] == ["c_speed"]
    assert any(item["kind"] == "probe" for item in bundle["assembly"]["rejected"])


def test_probe_specs_are_bounded_sanitized_and_do_not_claim_execution(source_packet):
    root, packet, _ = source_packet
    draft = annotations([backed_claim()], probes=[probe(claim_ids=["c_speed", "missing"]),
                                                probe("p_unknown", claim_ids=["missing"]), probe("p_extra")])
    bundle = assemble_annotations(draft, packet, root)
    assert bundle["probes"] == [probe()]
    assert bundle["graph"]["observations"] == []
    assert bundle["analysis"]["probe_results"] == []
    assert len(bundle["assembly"]["rejected"]) == 2


def test_inline_probe_source_uses_existing_path_and_byte_limit(source_packet):
    root, packet, _ = source_packet
    inline = probe(source="print(2 / 1)\n")
    bundle = assemble_annotations(annotations([backed_claim()], probes=[inline]), packet, root)
    assert bundle["probes"] == [{**inline, "fingerprint": bundle["probes"][0]["fingerprint"]}]
    assert len(bundle["probes"][0]["fingerprint"]) == 64
    assert not (root / inline["script"]).exists()  # Assembly itself does not write/execute.
    for fields in ({"script": "../escape.py"}, {"source": "é" * 16385}):
        rejected = assemble_annotations(
            annotations([backed_claim()], probes=[{**inline, **fields}]), packet, root)
        assert rejected["probes"] == []
        assert rejected["assembly"]["accepted_claim_ids"] == ["c_speed"]


@pytest.mark.parametrize("exit_code,status", [(0, "completed"), (1, "completed"), (None, "timeout")])
def test_only_runner_receipts_create_observations_without_proving_science(source_packet, exit_code, status):
    root, packet, _ = source_packet
    draft = annotations([backed_claim()], probes=[probe()])
    receipt = {"id": "p_speed", "claim_ids": ["c_speed"], "description": "Speed measured.",
               "status": status, "exit_code": exit_code, "duration_seconds": 1.2,
               "script_sha256": "a" * 64, "artifact": "probes/p_speed.json", "stdout_excerpt": "Observed 2.0"}
    bundle = assemble_annotations(draft, packet, root, probe_results=[receipt])
    assert bundle["validation"]["valid"]
    assert bundle["analysis"]["probe_results"] == [receipt]
    observation = bundle["graph"]["observations"][0]
    assert "Observed 2.0" in observation["description"]
    assert observation["claim_id"] == "c_speed" and observation["status"] == "reported"
    assert "not scientific proof" in observation["description"]
    assert "failure does not disprove" in observation["description"]
    assert bundle["graph"]["claims"][0]["status"] == "inferred"


def test_foreign_and_unsafe_receipts_preserved_but_not_attached(source_packet):
    root, packet, _ = source_packet
    draft = annotations([backed_claim()], probes=[probe()])
    receipt = {"id": "p_other", "claim_ids": ["c_speed"], "description": "Measured speed.",
               "status": "completed", "exit_code": 0, "duration_seconds": 1,
               "script_sha256": "a" * 64, "artifact": "probes/p_other.json"}
    receipts = [receipt, {**receipt, "id": "p_speed", "artifact": "../receipt.json"}]
    bundle = assemble_annotations(draft, packet, root, probe_results=receipts)
    assert bundle["analysis"]["probe_results"] == receipts
    assert bundle["graph"]["observations"] == []
    assert len(bundle["assembly"]["rejected"]) == 2
