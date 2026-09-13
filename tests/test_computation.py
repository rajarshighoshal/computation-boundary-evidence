"""Cross-domain mathematical identity, dependencies and actual handoff integration."""
import copy
import json
from pathlib import Path

import pytest

from scicontext.computation import build_computation, attach_computation, render_computation, conditions_for
from scicontext.evidence_packets import build_connected_input
from scicontext.object_context import enrichment_input, object_bundle
from scicontext.packet import build_packet
from scicontext.scientific_objects import extract_objects
from test_language_frontends import CASES


def python_payload(source):
    import ast
    tree = ast.parse(source)
    bodies = [{"id": f"body_{n.name}", "path": "model.py", "start_line": n.lineno,
               "end_line": n.end_lineno, "kind": "complete_function_body",
               "text": ast.get_source_segment(source, n)} for n in tree.body if isinstance(n, ast.FunctionDef)]
    return {"context": {"function_bodies": bodies, "code_passages": [], "scientific_passages": [], "helper_calls": []}}


def output_unit(model, name):
    quantities = {q["id"]: q for q in model["quantities"]}
    return next(u for u in model["transformations"] if quantities[u["output"]]["symbol"] == name)


def test_shared_identity_across_renamings_and_domains_not_function_grouping():
    payload = python_payload('def mechanics(mass, acceleration, drag, velocity):\n'
        '    force = mass * acceleration - drag * velocity\n    return force\n'
        'def circuit(voltage, conductance, offset, bias):\n'
        '    current = voltage * conductance - offset * bias\n    return current\n')
    model = build_computation(payload)
    a, b = output_unit(model, "force"), output_unit(model, "current")
    assert a["template_id"] == b["template_id"]
    assert a["bindings"] != b["bindings"]
    assert next(t for t in model["templates"] if t["id"] == a["template_id"])["family"] == "sum_or_difference_of_products"
    assert model["coverage"]["shared_templates"] > 0


def test_static_field_names_are_operand_bindings_not_different_mathematics():
    model = build_computation(python_payload('def f(a, b, data):\n'
        '    x = a*data["x"] + b*data["dx"]\n'
        '    y = a*data["y"] + b*data["dy"]\n    return x,y\n'))
    assert output_unit(model, "x")["template_id"] == output_unit(model, "y")["template_id"]
    assert any(q["symbol"] == "data['dx']" for q in model["quantities"])


def test_repeated_operands_order_constants_and_index_roles_are_preserved():
    model = build_computation(python_payload('def f(x,y):\n'
        '    square=x*x\n    product=x*y\n    a=(x+y)+1\n    b=x+(y+1)\n'
        '    c=x/2\n    d=x/3\n    e=x[:,0]\n    g=x[0,:]\n'))
    for a,b in [("square","product"),("a","b"),("c","d"),("e","g")]:
        assert output_unit(model,a)["template_id"] != output_unit(model,b)["template_id"]


def test_local_intermediate_expansion_preserves_original_dependency():
    model = build_computation(python_payload('def mass(rho, volume):\n'
        '    scaled = rho * volume\n    total = scaled + 2\n    return total\n'
        'def direct(density, size):\n    result = density * size + 2\n    return result\n'))
    total=output_unit(model,"total")
    assert total["resolved_intermediates"]
    assert total["template_id"] == output_unit(model,"result")["template_id"]
    assert any(e["source"]==output_unit(model,"scaled")["output"] and e["target"]==total["id"] for e in model["links"])


def test_branches_keep_conditions_and_do_not_inline_one_arm_as_truth():
    model=build_computation(python_payload('def f(x,flag):\n'
        '    if flag:\n        value=x*2\n    else:\n        value=x*3\n'
        '    result=value+1\n    return result\n'))
    assert not output_unit(model,"result")["resolved_intermediates"]
    conditional=[u for u in model["transformations"] if conditions_for(model,u)]
    assert {conditions_for(model,u)[0]["arm"] for u in conditional}=={"body","else"}
    assert any(e["status"]=="conditional_candidate" for e in model["links"])


def test_unknown_call_cannot_be_inlined_as_a_known_scientific_operator():
    model=build_computation(python_payload('def f(x):\n    y=sum(x)\n    z=y*2\n    return z\n'))
    assert not output_unit(model,"z")["resolved_intermediates"]
    assert any(g["reason"]=="opaque_operation_or_call" for g in model["gaps"])
    assert "scientific_law" not in json.dumps(model)


def test_document_symbol_matching_does_not_claim_semantic_entailment():
    payload=python_payload('def f(density,volume):\n    mass=density*volume\n    return mass\n')
    payload["context"]["scientific_passages"]=[{"id":"doc_mass", "quote":"mass is density times volume"}]
    model=build_computation(payload)
    doc=output_unit(model,"mass")["documentation"][0]
    assert doc["status"]=="symbol_reference_not_proven_meaning"
    assert doc["source_id"]=="doc_mass"


@pytest.mark.parametrize("path,language,source",CASES)
def test_existing_multilingual_frontends_feed_shared_representation(tmp_path,path,language,source):
    (tmp_path/path).write_text(source)
    packet=build_packet(tmp_path,multilingual=True)
    graph=extract_objects(tmp_path,packet)
    payload=build_connected_input(graph,packet,tmp_path)
    model=build_computation(payload)
    assert model["transformations"],language
    assert language in model["coverage"]["languages"]
    assert any(t["pattern"].get("op")=="sub" for t in model["templates"])


def test_code_owned_graph_survives_annotation_and_real_assembly(tmp_path):
    (tmp_path/"model.py").write_text('raise RuntimeError("must never execute")\n'
        'def storage(volume,flow,dt):\n    updated=volume-flow*dt\n    return updated\n')
    packet=build_packet(tmp_path,multilingual=True)
    graph=extract_objects(tmp_path,packet)
    old=copy.deepcopy((packet,graph))
    payload=enrichment_input(graph,packet,root=tmp_path,connected=True)
    unit=output_unit(payload["computation"],"updated")
    response={"schema_version":"object-enrichment-1.0","annotations":[
        {"object_id":unit["id"],"meaning":"Stored volume after outward transport."}]}
    bundle=object_bundle(graph,response,payload)
    assert bundle["assembly"]["interpretation_status"]=="enriched"
    assert bundle["graph"]["computation"]==payload["computation"]
    assert "Stored volume" in bundle["handoff"]
    assert "flow" in bundle["handoff"]
    assert (packet,graph)==old
    assert build_computation(payload)==payload["computation"]


def test_helper_argument_and_return_connections_are_preserved(tmp_path):
    (tmp_path/"model.py").write_text('def scale(x,factor):\n    return x*factor\n'
        'def calculate(a):\n    out=scale(a,2)\n    return out\n')
    packet=build_packet(tmp_path,multilingual=True)
    graph=extract_objects(tmp_path,packet)
    model=enrichment_input(graph,packet,root=tmp_path,connected=True)["computation"]
    assert any(e["role"]=="argument:x" for e in model["links"])
    assert any(e["role"]=="returned_value" for e in model["links"])
    assert all(e["status"]=="static_call_candidate" for e in model["links"] if e["role"].startswith("argument:"))


def test_all_graph_endpoints_exist_and_structure_is_byte_deterministic():
    payload=python_payload('def f(a,b):\n    x=a*b\n    y=x+1\n    return y\n')
    model=build_computation(payload)
    assert json.dumps(model,sort_keys=True)==json.dumps(build_computation(payload),sort_keys=True)
    ids={q["id"] for q in model["quantities"]}|{u["id"] for u in model["transformations"]}
    assert all({e["source"],e["target"]}<=ids for e in model["links"])


def test_early_return_and_exception_guards_remain_on_later_computations():
    model=build_computation(python_payload('def f(x,n):\n'
        '    if n==0:\n        return 0\n'
        '    if x==0:\n        raise ValueError("zero")\n'
        '    ratio=n/x\n    return ratio\n'))
    conditions=conditions_for(model,output_unit(model,"ratio"))
    assert [(c["expression"],c["arm"]) for c in conditions]==[("n == 0","else"),("x == 0","else")]
    assert model["guards"][0]["status"]=="source_validation_not_physical_law"


def test_unknown_call_blocks_expansion_across_possible_mutation():
    model=build_computation(python_payload('def f(x,y):\n'
        '    before=x*y\n    ignored=mutate(x)\n    after=before+1\n    return after\n'))
    assert not output_unit(model,"after")["resolved_intermediates"]


def test_field_binding_keeps_container_dependency_and_versions():
    model=build_computation(python_payload('def f(data,other):\n'
        '    first=data["x"]*2\n    data=other\n    second=data["x"]*2\n    return second\n'))
    fields=[q for q in model["quantities"] if q["symbol"]=="data['x']"]
    assert len(fields)==2
    assert all(any(e["target"]==q["id"] and e["role"]=="element_or_field_of" for e in model["links"]) for q in fields)


def test_same_line_definitions_are_distinct_versions():
    model=build_computation(python_payload('def f(a):\n    x=a*2; x=x+1\n    return x\n'))
    units=[u for u in model["transformations"] if not u["statement_role"]=="return"]
    assert len(units)==2 and units[0]["output"]!=units[1]["output"]
    assert any(e["source"]==units[0]["output"] and e["target"]==units[1]["id"] for e in model["links"])
