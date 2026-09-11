"""Scientific-context anchors across source languages; no candidate execution."""
import copy
import json

import pytest

from scicontext import packet as packet_module
from scicontext.cli import main
from scicontext.language_frontends import extract_native_evidence, source_language
from scicontext.object_context import enrichment_input, enrich_objects
from scicontext.packet import build_packet
from scicontext.scientific_objects import extract_objects


CASES = [
    ("model.c", "c", "double step(double volume, double flow, double dt) { double updated=volume-flow*dt; return updated; }\n"),
    ("model.cpp", "cpp", "namespace water { double step(double volume, double flow, double dt) { return volume-flow*dt; } }\n"),
    ("model.f90", "fortran", "function step(VOLUME, FLOW, DT) result(updated)\nreal :: volume, flow, dt, updated\nupdated=volume-flow*dt\nend function\n"),
    ("model.m", "matlab", "function updated=step(volume,flow,dt)\nupdated=volume-flow.*dt;\nend\n"),
    ("model.pyx", "cython", "cdef double step(double volume, double flow, double dt):\n    cdef double updated = volume-flow*dt\n    return updated\n"),
]


@pytest.mark.parametrize("path,language,source", CASES)
def test_native_calculation_has_interfaces_objects_and_real_expression_links(tmp_path, path, language, source):
    (tmp_path / path).write_text(source)
    (tmp_path / "README.md").write_text("Flow is positive for outward water transport; the updated storage is smaller.\n")
    packet = build_packet(tmp_path, multilingual=True)
    assert not any(r["reason"] in {"partial_parse", "parse_error", "cython_parse_error"} for r in packet["coverage"]["skipped"])
    graph = extract_objects(tmp_path, packet)
    assert graph["coverage"]["languages"] == [language]
    assert graph["coverage"]["recognized_scientific_operations"] == 0  # Syntax is not scientific understanding.
    operations = [o for o in graph["operations"] if o["kind"] == "source_binary"]
    assert {o["properties"]["syntax_operator"] for o in operations} == {"-", ".*" if language == "matlab" else "*"}
    assert all(i["object_id"] is not None for o in operations for i in o["inputs"])
    assert any(o["kind"] == "code_interface" for o in graph["objects"])
    assert any(l["relation"] == "parameter_of" for l in graph["links"])
    assert any(l["relation"] == "returns_from" for l in graph["links"])
    flow = next(o for o in graph["objects"] if (o["symbol"] or "").lower() == "flow")
    combined = enrich_objects(graph, {"schema_version": "object-enrichment-1.0", "annotations": [{
        "object_id": flow["id"], "meaning": "Positive-outward transport rate from README.md."}]})
    assert combined["enrichment"]["applied_object_ids"] == [flow["id"]]
    assert "outward water" in json.dumps(enrichment_input(graph, packet)["context"])
    assert graph == extract_objects(tmp_path, packet)


def test_default_packet_stays_python_only_but_scientific_mode_keeps_mixed_sources(tmp_path):
    (tmp_path / "model.py").write_text("def f(x):\n    return x*2\n")
    (tmp_path / "model.c").write_text("double f(double x) {return x*2;}\n")
    old = build_packet(tmp_path)
    assert {e["path"] for e in old["entries"]} == {"model.py"}
    assert any(s["path"] == "model.c" and s["reason"] == "unsupported_language" for s in old["coverage"]["skipped"])
    mixed = build_packet(tmp_path, multilingual=True)
    assert [e for e in mixed["entries"] if e["path"] == "model.py"] == old["entries"]
    graph = extract_objects(tmp_path, mixed)
    assert set(graph["coverage"]["languages"]) == {"python", "c"}
    assert len({o["id"] for o in graph["objects"]}) == len(graph["objects"])
    assert {r["path"] for r in graph["coverage"]["per_file"]} == {"model.py", "model.c"}


def test_explicit_native_task_path_survives_discovery_limit(tmp_path, monkeypatch):
    task, context = tmp_path / "task", tmp_path / "context"
    (task / "source/deep").mkdir(parents=True)
    context.mkdir()
    (task / "source/deep/model.cpp").write_text("double f(double q) { return q*2; }\n")
    (context / "task_statement.md").write_text("Investigate source/deep/model.cpp.\n")
    monkeypatch.setattr(packet_module, "MAX_SCAN_DIRECTORIES", 1)
    result = build_packet(task, context, multilingual=True)
    assert any(e["path"] == "source/deep/model.cpp" for e in result["entries"])
    assert result["coverage"]["directories_truncated"]


def test_native_branches_do_not_turn_conditional_definition_into_unconditional_value(tmp_path):
    (tmp_path / "model.c").write_text("double f(double x) { if (x>0) x=2; else x=3; return x*4; }\n")
    result = extract_objects(tmp_path, build_packet(tmp_path, multilingual=True))
    multiply = next(o for o in result["operations"] if o["kind"] == "source_binary")
    assert multiply["inputs"][0]["object_id"] is None
    assert any(u["reason"] == "conditional_native_binding" for u in result["unsupported"])


def test_native_same_named_parameters_in_different_functions_are_separate(tmp_path):
    (tmp_path / "model.c").write_text("double f(double x){return x*2;}\ndouble g(double x){return x*3;}\n")
    result = extract_objects(tmp_path, build_packet(tmp_path, multilingual=True))
    params = [o for o in result["objects"] if o["symbol"] == "x"]
    assert len(params) == 2 and len({o["scope"] for o in params}) == 2
    operators = [o for o in result["operations"] if o["kind"] == "source_binary"]
    assert {o["inputs"][0]["object_id"] for o in operators} == {o["id"] for o in params}


def test_compound_assignment_retains_old_value_and_rhs_not_rhs_alone(tmp_path):
    (tmp_path / "model.c").write_text("double f(double x, double y){ x+=y; return x; }\n")
    result = extract_objects(tmp_path, build_packet(tmp_path, multilingual=True))
    update = next(o for o in result["operations"] if o["kind"] == "uninterpreted_update")
    assert {i["role"] for i in update["inputs"]} == {"previous_target", "right_operand"}
    assert all(i["object_id"] for i in update["inputs"])


def test_array_write_is_not_treated_as_unchanged_parameter_value(tmp_path):
    (tmp_path / "model.c").write_text("double f(double *x){ x[0]=2; return consume(x); }\n")
    result = extract_objects(tmp_path, build_packet(tmp_path, multilingual=True))
    call = next(o for o in result["operations"] if o["kind"] == "uninterpreted_call")
    assert call["inputs"][0]["object_id"] is None
    assert any(u["reason"] == "native_mutation_not_resolved" for u in result["unsupported"])


def test_cython_compile_time_code_and_includes_are_not_evaluated(tmp_path):
    source = "DEF X = MUST_NOT_CALL()\nIF MUST_NOT_CALL():\n    include 'must-not-open.pxi'\n" + CASES[-1][2]
    (tmp_path / "model.pyx").write_text(source)
    packet = build_packet(tmp_path, multilingual=True)
    assert any(e["kind"] == "signature" for e in packet["entries"])
    assert any(s["reason"] == "cython_compile_time_region_not_evaluated" for s in packet["coverage"]["skipped"])
    assert not any(s["reason"] == "cython_parse_error" for s in packet["coverage"]["skipped"])


def test_cython_pointer_and_pxd_interfaces_are_retained(tmp_path):
    (tmp_path / "model.pxd").write_text("cdef double *lookup(double *x)\n")
    result = extract_objects(tmp_path, build_packet(tmp_path, multilingual=True))
    assert any(o["kind"] == "code_interface" for o in result["objects"])


def test_parse_errors_and_stale_native_source_do_not_look_like_complete_extraction(tmp_path):
    (tmp_path / "bad.c").write_text("double broken( {\n")
    result = extract_native_evidence(tmp_path, ["bad.c"])
    assert any(s["reason"] == "partial_parse" for s in result["coverage"]["skipped"])
    (tmp_path / "good.c").write_text(CASES[0][2])
    packet = build_packet(tmp_path, multilingual=True, source_paths=["good.c"])
    (tmp_path / "good.c").write_text("int different;\n")
    graph = extract_objects(tmp_path, packet)
    assert not graph["objects"]
    assert any(u["reason"] == "stale_or_unreadable_source" for u in graph["unsupported"])


def test_native_parse_omissions_reach_the_scientific_reader(tmp_path):
    (tmp_path / "bad.c").write_text("double broken( {\n")
    packet = build_packet(tmp_path, multilingual=True)
    graph = extract_objects(tmp_path, packet)
    payload = enrichment_input(graph, packet)
    assert any(u["reason"] == "partial_parse" for u in payload["unsupported"])
    assert any(r["path"] == "bad.c" and r["unsupported_cases"] > 0 for r in graph["coverage"]["per_file"])


def test_offline_command_exposes_native_code_and_scientific_context(tmp_path, capsys):
    (tmp_path / "model.f90").write_text(CASES[2][2])
    (tmp_path / "README.md").write_text("Outward flow depletes water volume.\n")
    main(["scientific-objects", "--root", str(tmp_path), "model.f90", "--output", str(tmp_path / "objects.json"),
          "--llm-input", str(tmp_path / "context.json")])
    capsys.readouterr()
    result = json.loads((tmp_path / "context.json").read_text())
    assert any(c["language"] == "fortran" for c in result["context"]["code_passages"])
    assert "depletes water" in json.dumps(result["context"]["scientific_passages"])


def test_extension_dispatch_includes_mixed_language_variants():
    assert source_language("model.C") == "cpp"
    assert source_language("model.F90") == "fortran"
    assert source_language("model.pyx") == source_language("model.pxd") == "cython"
    assert source_language("data.csv") is None


def test_member_call_retains_the_receiving_object_without_inventing_dispatch(tmp_path):
    (tmp_path / "model.cpp").write_text("double f(Record *record) { return record->length(); }\n")
    result = extract_objects(tmp_path, build_packet(tmp_path, multilingual=True))
    call = next(o for o in result["operations"] if o["kind"] == "uninterpreted_call")
    receiver = next(i["object_id"] for i in call["inputs"] if i["role"] == "receiver")
    assert next(o for o in result["objects"] if o["id"] == receiver)["symbol"] == "record"
    assert call["properties"]["wrapper"]["status"] == "unresolved"


def test_c_prototype_does_not_shadow_the_real_function_body(tmp_path):
    (tmp_path / "model.c").write_text("double helper(double x);\ndouble f(double x){return helper(x);}\ndouble helper(double x){return x*2;}\n")
    result = extract_objects(tmp_path, build_packet(tmp_path, multilingual=True))
    call = next(o for o in result["operations"] if o["kind"] == "uninterpreted_call")
    assert call["properties"]["wrapper"]["status"] == "lexical_target_only"
    assert any(l["source"] == call["id"] and l["relation"] == "may_invoke_body" for l in result["links"])


def test_function_pointer_variable_does_not_become_a_function_declaration(tmp_path):
    (tmp_path / "model.c").write_text("double f(double (*callback)(double), double x){return callback(x);}\n")
    result = extract_objects(tmp_path, build_packet(tmp_path, multilingual=True))
    callback = next(o for o in result["objects"] if o["symbol"] == "callback")
    assert callback["kind"] != "code_interface"
    call = next(o for o in result["operations"] if o["kind"] == "uninterpreted_call")
    assert call["properties"]["wrapper"]["status"] == "unresolved"


def test_matlab_index_or_call_keeps_the_source_value(tmp_path):
    (tmp_path / "model.m").write_text("function y=take(x)\ny=x(1);\nend\n")
    result = extract_objects(tmp_path, build_packet(tmp_path, multilingual=True))
    call = next(o for o in result["operations"] if o["kind"] == "uninterpreted_call")
    assert call["properties"]["call_or_index"] is True
    source = next(i["object_id"] for i in call["inputs"] if i["role"] == "indexed_or_callable_value")
    assert next(o for o in result["objects"] if o["id"] == source)["symbol"] == "x"


def test_scientific_passage_interfaces_and_computation_survive_entry_budget(tmp_path, monkeypatch):
    # Source documentation states science; the parser must expose it, not assert it is true.
    comments = "! Magnetic field tensor: X points NORTH, Y points WEST, Z points UPWARD.\n"
    comments += "! Laplace's equation gives Vxx + Vyy + Vzz = 0; output units nT / m.\n"
    comments += "! Additional scientific explanation.\n" * 150
    declarations = "".join(f"real :: scratch{i}\n" for i in range(100))
    (tmp_path / "tensor.f90").write_text("subroutine tensor(vxx, vyy, vzz)\n" + comments +
        "real, intent(in) :: vxx, vyy\nreal, intent(out) :: vzz\n" + declarations +
        "vzz = -vxx - vyy\nend subroutine\n")
    monkeypatch.setattr(packet_module, "MAX_ENTRIES_PER_FILE", 24)
    packet = build_packet(tmp_path, multilingual=True)
    assert packet["coverage"]["entries_truncated"]
    comments = [e for e in packet["entries"] if e["kind"] == "docstring"]
    assert len(comments) == 1 and "Vxx + Vyy + Vzz" in comments[0]["text"]
    graph = extract_objects(tmp_path, packet)
    payload = enrichment_input(graph, packet)
    assert "Y points WEST" in json.dumps(payload["context"])
    assert any(o["kind"] == "source_binary" for o in graph["operations"])
    vzz = next(o for o in graph["objects"] if o["symbol"] == "vzz" and o["properties"].get("binding") == "parameter")
    assert "intent(out)" in vzz["properties"]["declaration_text"]
    assert vzz["properties"]["dimensions"] is None  # Context is not machine-inferred units.
    assert any(u["reason"] == "native_entry_limit" for u in payload["unsupported"])


def test_truncation_does_not_skip_a_shadowing_binding_and_reuse_outer_parameter(tmp_path):
    source = "double f(double x){ {\n" + "".join(f"double spare{i};\n" for i in range(30)) + "double x; return x*4;\n} }\n"
    (tmp_path / "model.c").write_text(source)
    packet = extract_native_evidence(tmp_path, ["model.c"], max_entries=6)
    assert packet["coverage"]["entries_truncated"]
    graph = extract_objects(tmp_path, packet)
    multiply = next(o for o in graph["operations"] if o["kind"] == "source_binary")
    assert multiply["inputs"][0]["object_id"] is None
    assert any(u["reason"] == "omitted_native_binding" for u in graph["unsupported"])


def test_fortran_output_calculation_is_not_crowded_out_by_setup_statements(tmp_path):
    (tmp_path / "tensor.f90").write_text("subroutine tensor(x,y)\nreal, intent(in) :: x\nreal, intent(out) :: y\n" +
        "real :: scratch\n" + "scratch=0\n" * 150 + "y = x*2\nend subroutine\n")
    packet = extract_native_evidence(tmp_path, ["tensor.f90"], max_entries=12)
    assert packet["coverage"]["entries_truncated"]
    assert any(e["kind"] == "assignment" and e["native"].get("target") == "y" for e in packet["entries"])
    graph = extract_objects(tmp_path, packet)
    multiply = next(o for o in graph["operations"] if o["kind"] == "source_binary")
    assert all(i["object_id"] for i in multiply["inputs"])


@pytest.mark.parametrize("body,changed", [("{ x=2; }", True), ("{ double x=2; }", False)])
def test_c_block_write_ownership_distinguishes_shadowing(tmp_path, body, changed):
    (tmp_path / "model.c").write_text(f"double f(double x) {{ {body} return x*4; }}\n")
    graph = extract_objects(tmp_path, build_packet(tmp_path, multilingual=True))
    multiply = next(o for o in graph["operations"] if o["kind"] == "source_binary")
    operand = next(o for o in graph["objects"] if o["id"] == multiply["inputs"][0]["object_id"])
    assert (operand["properties"].get("binding") == "parameter") is not changed


@pytest.mark.parametrize("write", ["x++", "--x"])
def test_c_increment_cannot_disappear_before_later_read(tmp_path, write):
    (tmp_path / "model.c").write_text(f"double f(double x){{ {write}; return x*4; }}\n")
    graph = extract_objects(tmp_path, build_packet(tmp_path, multilingual=True))
    multiply = next(o for o in graph["operations"] if o["kind"] == "source_binary")
    assert multiply["inputs"][0]["object_id"] is None
    assert any(u["reason"] == "native_mutation_not_resolved" for u in graph["unsupported"])


@pytest.mark.parametrize("target", ["x[0]", "x.field"])
def test_cython_compound_write_invalidates_later_read(tmp_path, target):
    (tmp_path / "model.pyx").write_text(f"def f(x):\n    {target}=2\n    return consume(x)\n")
    graph = extract_objects(tmp_path, build_packet(tmp_path, multilingual=True))
    call = next(o for o in graph["operations"] if o["kind"] == "uninterpreted_call")
    assert call["inputs"][0]["object_id"] is None
    assert any(u["reason"] == "native_mutation_not_resolved" for u in graph["unsupported"])


def test_cython_classes_keep_scientific_docs_fields_and_untyped_self(tmp_path):
    (tmp_path / "model.pyx").write_text('''"""Magnetic tensor conventions.
IF/include are words inside this documentation, not directives.
"""
cdef class Tensor:
    """Components use north-west-up axes."""
    cdef double value
    cpdef double read(self, double scale):
        return self.value * scale
cdef class Spectrum:
    """Coefficients use Schmidt semi-normalization."""
    cdef double value
    cpdef double read(self, double scale):
        return self.value * scale
def caller(x):
    return read(x)
''')
    packet = build_packet(tmp_path, multilingual=True)
    assert not any(s["reason"] == "cython_compile_time_region_not_evaluated" for s in packet["coverage"]["skipped"])
    fields = [e for e in packet["entries"] if e["kind"] == "declaration" and e["entity_symbols"] == ["value"]]
    assert len(fields) == 2 and len({e["scope"] for e in fields}) == 2
    assert all(e["function_scope"] is None for e in fields)
    assert sum(e["entity_symbols"] == ["self"] for e in packet["entries"]) == 2
    graph = extract_objects(tmp_path, packet)
    context = json.dumps(enrichment_input(graph, packet)["context"])
    assert "Magnetic tensor" in context and "north-west-up" in context and "Schmidt" in context
    call = next(o for o in graph["operations"] if o["kind"] == "uninterpreted_call")
    assert call["properties"]["wrapper"]["status"] == "unresolved"


def test_nonlexical_method_is_not_a_unique_free_function_target(tmp_path):
    (tmp_path / "model.cpp").write_text("struct A { double helper(double x) {return x*2;} };\ndouble f(double x){return helper(x);}\n")
    graph = extract_objects(tmp_path, build_packet(tmp_path, multilingual=True))
    call = next(o for o in graph["operations"] if o["kind"] == "uninterpreted_call")
    assert call["properties"]["wrapper"]["status"] == "unresolved"


def test_cython_method_body_does_not_lexically_inherit_class_namespace(tmp_path):
    (tmp_path / "model.pyx").write_text("class Tensor:\n    def evaluate(self, y):\n        return y*2\n    def caller(self,x):\n        return evaluate(x)\n")
    graph = extract_objects(tmp_path, build_packet(tmp_path, multilingual=True))
    call = next(o for o in graph["operations"] if o["kind"] == "uninterpreted_call")
    assert call["properties"]["wrapper"]["status"] == "unresolved"


def test_matlab_implicit_output_uses_function_exit_binding_not_whole_body_as_return(tmp_path):
    source = "function y=scale(x)\ny=x*2;\nend\n"
    (tmp_path / "model.m").write_text(source)
    packet = extract_native_evidence(tmp_path, ["model.m"])
    returned = next(e for e in packet["entries"] if e["kind"] == "return")
    assert "x*2" not in returned["text"]
    assert returned["native"]["binding_at"] == "function_exit"
    assert returned["native"]["order_start"][0] >= 3
    graph = extract_objects(tmp_path, packet)
    assignment = next(o for o in graph["objects"] if o["symbol"] == "y")
    assert any(l["source"] == assignment["id"] and l["relation"] == "returned_as" for l in graph["links"])


def test_native_budget_retains_calculations_in_later_scientific_components(tmp_path):
    (tmp_path / "model.m").write_text("function y=setup(x)\n" + "padding=0;\n" * 100 +
        "y=x;\nend\nfunction y=quantify(x)\n% x is a measured amplitude; convert using a reference scale.\ny=x*2;\nend\n")
    packet = extract_native_evidence(tmp_path, ["model.m"], max_entries=14)
    assert packet["coverage"]["entries_truncated"]
    graph = extract_objects(tmp_path, packet)
    multiply = next(o for o in graph["operations"] if o["kind"] == "source_binary")
    assert ".quantify@" in multiply["source"]["scope"]
    assert all(i["object_id"] for i in multiply["inputs"])
