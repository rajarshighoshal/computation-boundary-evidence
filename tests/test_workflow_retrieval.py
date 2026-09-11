"""Workflow retrieval is source evidence, not runtime-dispatch or scientific truth."""
import json

from scicontext import packet as packet_module
from scicontext.language_frontends import extract_native_evidence
from scicontext.packet import build_packet
from scicontext.scientific_objects import extract_objects
from scicontext.workflow_retrieval import retrieve


def put(root, path, text):
    destination = root / path
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text)


def targets(graph):
    return [t for op in graph["operations"] for t in op["properties"].get("retrieved_targets", [])]


def test_imported_class_value_and_receiver_method_reach_correct_owner(tmp_path):
    put(tmp_path, "source/pkg/regions.py", 'class SparseTrack:\n    """Half-open intervals."""\n    def refine(self, x):\n        return x*2\nclass DenseTrack:\n    def refine(self,x):\n        return x*3\n')
    put(tmp_path, "reproduce.py", "from pkg.regions import SparseTrack\ndef types():\n    return {'sparse': SparseTrack}\ndef run(x):\n    track=types()['sparse']()\n    track.refine(x)\n")
    for i in range(30):
        put(tmp_path, f"unrelated/a{i}.c", "double log(double x){return x;}\n")
    packet = build_packet(tmp_path, multilingual=True)
    graph = extract_objects(tmp_path, packet)
    refs = packet["coverage"]["workflow_retrieval"]["references"]
    assert any(r["symbol"] == "SparseTrack.refine" for r in refs)
    assert not any(r["symbol"] == "DenseTrack.refine" for r in refs)
    match = next(t for t in targets(graph) if t["symbol"] == "SparseTrack.refine")
    assert match["runtime_invocation"] == "not_established"
    assert match["argument_and_return_equivalence"] == "not_derived"
    assert any(l["relation"] == "possible_callee_body" for l in graph["links"])
    assert graph == extract_objects(tmp_path, packet)


def test_multiple_imported_receiver_candidates_are_not_collapsed_into_proven_dispatch(tmp_path):
    for name in ["A", "B"]:
        put(tmp_path, f"pkg/{name}.py", f"class {name}:\n    def advance(self,x):\n        return x*2\n")
    put(tmp_path, "reproduce.py", "from pkg.A import A\nfrom pkg.B import B\nclasses=[A,B]\ndef run(track,x):\n    return track.advance(x)\n")
    graph = extract_objects(tmp_path, build_packet(tmp_path, multilingual=True))
    call = next(o for o in graph["operations"] if o["properties"].get("wrapper", {}).get("function") == "track.advance")
    assert {t["symbol"] for t in call["properties"]["retrieved_targets"]} == {"A.advance", "B.advance"}
    assert call["properties"]["wrapper"]["status"] == "unresolved"
    for o in graph["objects"]:
        if o["id"] in call["output_ids"]:
            assert o["properties"]["dimensions"] is None and o["properties"]["shape"] is None


def test_reassigned_import_is_not_used_to_choose_receiver_class(tmp_path):
    put(tmp_path, "pkg/track.py", "class Track:\n    def advance(self,x):\n        return x*2\n")
    put(tmp_path, "reproduce.py", "from pkg.track import Track\nTrack=external_factory\nx=Track()\nx.advance(2)\n")
    packet = build_packet(tmp_path, multilingual=True)
    refs = packet["coverage"]["workflow_retrieval"]["references"]
    assert not any(r["symbol"] == "Track.advance" for r in refs)


def test_fortran_program_calls_reach_body_and_not_declaration(tmp_path):
    put(tmp_path, "reproduce.py", "driver='fixtures/study.f90'\n")
    put(tmp_path, "fixtures/study.f90", "program study\nreal :: x,y\ncall ADVANCE(x,y)\nend program\n")
    put(tmp_path, "source/advance.f90", "subroutine advance(x,y)\nreal, intent(in) :: x\nreal, intent(out) :: y\ny=x*2\nend subroutine\n")
    put(tmp_path, "source/interface.f90", "module api\ninterface\nsubroutine advance(x,y)\nreal :: x,y\nend subroutine\nend interface\nend module\n")
    packet = build_packet(tmp_path, multilingual=True)
    graph = extract_objects(tmp_path, packet)
    assert any(t["path"] == "source/advance.f90" for t in targets(graph))
    assert not any(t["path"] == "source/interface.f90" for t in targets(graph))
    declarations = extract_native_evidence(tmp_path, ["source/interface.f90"])["entries"]
    signature = next(e for e in declarations if e["kind"] == "signature")
    assert signature["native"]["declaration_only"]


def test_duplicate_native_definitions_keep_both_as_candidates(tmp_path):
    put(tmp_path, "reproduce.f90", "program study\ncall advance()\nend program\n")
    for folder in ["a", "b"]:
        put(tmp_path, f"{folder}/advance.f90", "subroutine advance()\nx=2\nend subroutine\n")
    graph = extract_objects(tmp_path, build_packet(tmp_path, multilingual=True))
    assert {t["path"] for t in targets(graph)} == {"a/advance.f90", "b/advance.f90"}
    assert all(t["status"] == "source_reference_only" for t in targets(graph))


def test_embedded_call_retrieves_math_body_without_claiming_host_executes_it(tmp_path):
    put(tmp_path, "reproduce.py", 'driver="""function y=driver(x)\ny=normalize(x);\nend\n"""\n')
    put(tmp_path, "source/normalize.m", "function y=normalize(x)\n% Scale a measured amplitude.\ny=x*2;\nend\n")
    packet = build_packet(tmp_path, multilingual=True)
    graph = extract_objects(tmp_path, packet)
    assert any(o["kind"] == "code_interface" and o["path"] == "source/normalize.m" for o in graph["objects"])
    assert any(o["kind"] == "source_binary" for o in graph["operations"])
    assert not targets(graph)  # Embedded source is not a Python call.


def test_generated_matlab_definition_is_not_misread_as_call(tmp_path):
    put(tmp_path, "reproduce.py", 'shims={"normalize.m":"function y=normalize(x)\\ny=x;\\nend\\n"}\n')
    put(tmp_path, "source/normalize.m", "function y=normalize(x)\ny=x*2;\nend\n")
    refs, _ = retrieve(tmp_path, {"reproduce.py", "source/normalize.m"}, {"reproduce.py"})
    assert not any(r["symbol"] == "normalize" for r in refs)


def test_function_documentation_ranks_task_relevant_candidate(tmp_path):
    put(tmp_path, "reproduce.f90", "program study\ncall alpha()\ncall zeta()\nend program\n")
    put(tmp_path, "alpha.f90", "subroutine alpha()\n! Print unrelated logging messages.\nx=2\nend subroutine\n")
    put(tmp_path, "zeta.f90", "subroutine zeta()\n! Magnetic potential tensor in a local coordinate frame.\nx=2\nend subroutine\n")
    refs, _ = retrieve(tmp_path, {"reproduce.f90", "alpha.f90", "zeta.f90"}, {"reproduce.f90"}, "Magnetic potential tensor coordinate frame")
    assert next(r for r in refs if r["symbol"] == "zeta")["relevance_score"] > next(r for r in refs if r["symbol"] == "alpha")["relevance_score"]


def test_workflow_limits_are_unchanged_and_call_target_absence_is_not_success(tmp_path, monkeypatch):
    put(tmp_path, "reproduce.py", "from pkg.model import absent\nabsent(2)\n")
    put(tmp_path, "pkg/model.py", "from pkg.other import unrelated\ndef harmless(x):\n    return unrelated(x)\n")
    put(tmp_path, "pkg/other.py", "def unrelated(x):\n    return x*2\n")
    monkeypatch.setattr(packet_module, "MAX_ENTRIES", 12)
    packet = build_packet(tmp_path, multilingual=True)
    assert len(packet["entries"]) <= 12
    workflow = packet["coverage"]["workflow_retrieval"]
    assert any(u["reason"] == "requested_definition_not_found" for u in workflow["unresolved"])
    assert not any(r["symbol"] == "unrelated" for r in workflow["references"])


def test_two_calls_on_one_line_have_separate_source_references(tmp_path):
    put(tmp_path, "pkg/model.py", "def transform(x):\n    return x*2\n")
    put(tmp_path, "reproduce.py", "from pkg.model import transform\ndef run(x,y):\n    return transform(x) + transform(y)\n")
    packet = build_packet(tmp_path, multilingual=True)
    graph = extract_objects(tmp_path, packet)
    calls = [op for op in graph["operations"] if op["properties"].get("retrieved_targets") and
             op["source"]["path"] == "reproduce.py"]
    assert len(calls) == 2
    assert len({op["call_site"]["start_col"] for op in calls}) == 2
    for op in calls:
        assert op["call_site"]["start_col"] == op["properties"]["retrieved_targets"][0]["caller"]["start_col"]


def test_stale_target_signature_cannot_gain_a_synthetic_call_link(tmp_path):
    put(tmp_path, "pkg/model.py", "def transform(x):\n    return x*2\n")
    put(tmp_path, "reproduce.py", "from pkg.model import transform\ny=transform(2)\n")
    packet = build_packet(tmp_path, multilingual=True)
    put(tmp_path, "pkg/model.py", "different=42\n")
    graph = extract_objects(tmp_path, packet)
    assert not targets(graph)
    assert any(u["reason"] == "stale_or_unreadable_source" for u in graph["unsupported"])


def test_parameter_shadowing_import_stays_unresolved(tmp_path):
    put(tmp_path, "pkg/model.py", "def transform(x):\n    return x*2\n")
    put(tmp_path, "reproduce.py", "from pkg.model import transform\ndef run(transform,x):\n    return transform(x)\n")
    graph = extract_objects(tmp_path, build_packet(tmp_path, multilingual=True))
    assert not targets(graph)


def test_import_in_sibling_scope_cannot_supply_a_call_target(tmp_path):
    put(tmp_path, "pkg/model.py", "def transform(x):\n    return x*2\n")
    put(tmp_path, "reproduce.py", "def unrelated():\n    from pkg.model import transform\ndef run(x):\n    return transform(x)\n")
    graph = extract_objects(tmp_path, build_packet(tmp_path, multilingual=True))
    assert not targets(graph)


def test_same_file_parameter_shadowing_cannot_bypass_original_binding_check(tmp_path):
    put(tmp_path, "reproduce.py", "def transform(x):\n    return x*2\ndef run(transform,x):\n    return transform(x)\n")
    graph = extract_objects(tmp_path, build_packet(tmp_path, multilingual=True))
    assert not targets(graph)


def test_retrieval_depth_omission_is_visible(tmp_path, monkeypatch):
    import scicontext.workflow_retrieval as module
    put(tmp_path, "reproduce.f90", "program test\ncall advance()\nend program\n")
    put(tmp_path, "advance.f90", "subroutine advance()\nx=2\nend subroutine\n")
    monkeypatch.setattr(module, "MAX_DEPTH", 0)
    refs, report = retrieve(tmp_path, {"reproduce.f90", "advance.f90"}, {"reproduce.f90"})
    assert not any(r["symbol"] == "advance" for r in refs)
    assert report["truncated"] and any(u["reason"] == "workflow_depth_limit" for u in report["unresolved"])


def test_boundary_predicate_has_a_code_anchor_without_becoming_a_scientific_rule(tmp_path):
    put(tmp_path, "reproduce.py", "def overlap(left,right):\n    if left < right:\n        return left\n    return right\n")
    graph = extract_objects(tmp_path, build_packet(tmp_path, multilingual=True))
    predicate = next(o for o in graph["objects"] if o["kind"] == "source_predicate")
    comparison = next(o for o in graph["operations"] if o["kind"] == "source_comparison")
    assert comparison["properties"]["expression"] == "left < right"
    assert comparison["properties"]["scientific_semantics"] == "unknown"
    assert predicate["properties"]["dimensions"] is None
    assert graph["coverage"]["recognized_scientific_operations"] == 0


def test_unpacked_statement_is_context_not_a_binding_for_each_target(tmp_path):
    put(tmp_path, "reproduce.py", "def f(x):\n    left,right=x\n    return left*2\n")
    graph = extract_objects(tmp_path, build_packet(tmp_path, multilingual=True))
    statement = next(o for o in graph["objects"] if o["kind"] == "source_statement")
    assert statement["properties"]["binding"] == "not_resolved"
    product = next(o for o in graph["operations"] if o["kind"] == "arithmetic")
    assert product["inputs"][0]["object_id"] is None
