"""Real-source, no-model checks of the finite scientific-object extractor."""

import json

import pytest

from scicontext.evidence import extract_evidence
from scicontext.scientific_objects import extract_objects


def graph(tmp_path, source):
    (tmp_path / "calculation.py").write_text(source)
    packet = extract_evidence(tmp_path)
    result = extract_objects(tmp_path, packet)
    assert json.loads(json.dumps(result)) == result
    entries = {e["id"] for e in packet["entries"]}
    ids = {o["id"] for o in result["objects"] + result["operations"]}
    assert all(set(o["source_entry_ids"]) <= entries for o in result["objects"])
    assert all(o["source_entry_id"] in entries for o in result["operations"])
    assert all(l["source"] in ids and l["target"] in ids for l in result["links"])
    assert all(i["object_id"] is None or i["object_id"] in ids for op in result["operations"] for i in op["inputs"])
    assert result == extract_objects(tmp_path, packet)
    return result


def op(result, kind):
    return next(o for o in result["operations"] if o["kind"] == kind)


def objects(result):
    return {o["id"]: o for o in result["objects"]}


def binding(result, symbol):
    return next(o for o in result["objects"] if o["symbol"] == symbol)


@pytest.mark.parametrize("alias,one,two,output", [("np", "matrix", "rhs", "solution"), ("xx", "cat", "dog", "bird")])
def test_linear_solve_recovers_roles_not_domain_names(tmp_path, alias, one, two, output):
    result = graph(tmp_path, f"import numpy as {alias}\n"
        f"{one} = {alias}.array([[2, 0], [0, 3]])\n"
        f"{two} = {alias}.asarray([4, 9])\n"
        f"{output} = {alias}.linalg.solve({one}, {two})\n"
        f"returned = {output} * 2\n")
    solve = op(result, "linear_solve")
    assert solve["properties"]["relation"] == "A @ x = b"
    assert solve["properties"]["coefficient_square_from_literal_shape"] is True
    assert {i["role"]: objects(result)[i["object_id"]]["symbol"] for i in solve["inputs"]} == {
        "coefficient_operator": one, "right_hand_side": two}
    assert "returned" in {o["symbol"] for o in result["objects"]}
    assert binding(result, one)["properties"]["shape"] == [2, 2]
    assert binding(result, output)["properties"]["dimensions"] is None
    assert "rank is not inferred" in " ".join(solve["assumptions"])


def test_scoped_parameters_and_alias_composition(tmp_path):
    result = graph(tmp_path, "from numpy.linalg import solve as invert\n"
        "def fit(coeff, signal):\n"
        "    same = coeff\n"
        "    answer = invert(same, signal)\n"
        "    return answer\n")
    solve = op(result, "linear_solve")
    assert all(i["object_id"] is not None for i in solve["inputs"])
    assert binding(result, "coeff")["properties"]["binding"] == "parameter"
    assert any(l["relation"] == "returned_as" for l in result["links"])
    assert any(l["source"] == binding(result, "coeff")["id"] and l["target"] == binding(result, "same")["id"] for l in result["links"])


@pytest.mark.parametrize("source", [
    "def solve(a, b):\n    return a\nx = solve(1, 2)\n",
    "import numpy as np\nnp = replacement\nx = np.linalg.solve(1, 2)\n",
    "from numpy.linalg import solve\ndef f(solve):\n    return solve(1, 2)\n",
    "import numpy as np\nx = np.made_up_science(1, 2)\n",
])
def test_names_shadowing_and_unknown_api_do_not_create_science(tmp_path, source):
    result = graph(tmp_path, source)
    assert result["coverage"]["recognized_scientific_operations"] == 0
    assert result["objects"] == []
    assert any(u["reason"] in {"unrecognized_or_shadowed_call", "uninterpreted_wrapper_call"} for u in result["unsupported"])


@pytest.mark.parametrize("source,reason", [
    ("import numpy as n\na = [[1]]\nif condition:\n    a = [[2]]\nx = n.linalg.solve(a, [1])\n", "branch_or_dynamic_binding"),
    ("import numpy as n\na = [[1]]\ndef f():\n    return n.linalg.solve(a, [1])\n", "nonlocal_or_external"),
    ("import numpy as n\na = [[1]]\na = [[2]]; x = n.linalg.solve(a, [1])\n", "same_line_binding_ambiguity"),
])
def test_ambiguous_dataflow_stays_null(tmp_path, source, reason):
    result = graph(tmp_path, source)
    assert op(result, "linear_solve")["inputs"][0]["object_id"] is None
    assert any(u.get("binding_reason") == reason for u in result["unsupported"])


def test_sequential_rebinding_uses_latest_source_definition(tmp_path):
    result = graph(tmp_path, "import numpy as n\na = [[1]]\na = [[2, 0], [0, 2]]\nx = n.linalg.solve(a, [1, 2])\n")
    coefficient = objects(result)[op(result, "linear_solve")["inputs"][0]["object_id"]]
    assert coefficient["properties"]["shape"] == [2, 2]


def test_quadrature_keeps_order_axis_and_x_precedence(tmp_path):
    result = graph(tmp_path, "from scipy.integrate import trapezoid as integrate\n"
        "samples = [4, 8, 9]\npositions = [2, 1, 0]\n"
        "total = integrate(samples, x=positions, dx=100, axis=0)\n")
    operation = op(result, "sampled_integration")
    assert operation["properties"]["axis"] == 0
    assert operation["properties"]["coordinates_sorted"] is False
    assert operation["properties"]["dx_ignored_if_x_not_none"] is True
    assert {i["role"]: i["object_id"] for i in operation["inputs"]}["sample_spacing"] is None
    assert objects(result)[operation["inputs"][1]["object_id"]]["properties"]["literal"] == [2, 1, 0]
    assert binding(result, "total")["kind"] == "integral"


def test_quadrature_default_spacing_and_unknown_axis(tmp_path):
    result = graph(tmp_path, "import scipy.integrate as si\ndef f(y, ax):\n    return si.trapezoid(y, x=None, dx=0.5, axis=ax)\n")
    operation = op(result, "sampled_integration")
    assert operation["properties"]["axis"] is None
    assert operation["properties"]["axis_expression"] == "ax"
    spacing = objects(result)[operation["inputs"][2]["object_id"]]
    assert spacing["properties"]["literal"] == .5


@pytest.mark.parametrize("constructor,directed", [("Graph", False), ("DiGraph", True)])
def test_graph_constructor_and_partition_share_object(tmp_path, constructor, directed):
    result = graph(tmp_path, f"import networkx as networks\ntopology = networks.{constructor}([(1, 2), (3, 4)])\n"
        "same = topology\nparts = networks.connected_components(same)\n")
    g = binding(result, "topology")
    assert g["kind"] == "graph"
    assert g["properties"]["directed"] is directed
    assert g["properties"]["topology"]["edges"] == [[1, 2], [3, 4]]
    partition = op(result, "connected_component_partition")
    assert partition["inputs"][0]["object_id"] == binding(result, "same")["id"]
    assert partition["properties"]["directedness_conflict"] is directed
    assert partition["properties"]["requires_undirected"]
    assert g["properties"]["topology"]["later_mutation"] == "not_modelled"


def test_quantity_scale_dimensions_and_composition(tmp_path):
    result = graph(tmp_path, "from astropy import units as u\n"
        "distance = u.Quantity(100, 'cm')\nother = u.Quantity(1, u.m)\n"
        "duration = u.Quantity(2, 's')\n"
        "combined = distance + other\nspeed = combined / duration\n"
        "twice = 2 * speed\n")
    assert binding(result, "distance")["properties"]["dimensions"] == {"length": 1}
    assert binding(result, "combined")["properties"]["right_to_left_unit_factor"] == "100"
    assert binding(result, "speed")["properties"]["dimensions"] == {"length": 1, "time": -1}
    assert binding(result, "speed")["properties"]["scale_to_si"] == "1/100"
    assert binding(result, "twice")["properties"]["scale_to_si"] == "1/100"
    assert sum(o["kind"] == "quantity_arithmetic" for o in result["operations"]) == 3


def test_unsupported_units_and_conflicting_addition_remain_explicit(tmp_path):
    result = graph(tmp_path, "from astropy.units import Quantity as Q\n"
        "a = Q(2, 'm')\nb = Q(3, 's')\nc = a + b\n"
        "unknown = Q(10, 'deg_C')\nuncertain = a * unknown\n"
        "zero = a + 0\n")
    assert binding(result, "c")["properties"]["dimensional_conflict"] is True
    assert binding(result, "c")["properties"]["dimensions"] is None
    assert binding(result, "uncertain")["properties"]["dimensions"] is None
    assert "dimensional_conflict" not in binding(result, "zero")["properties"]
    assert any(u["reason"] == "unsupported_or_implicit_quantity_unit" for u in result["unsupported"])


def test_nested_operations_connect_without_assigned_intermediates(tmp_path):
    result = graph(tmp_path, "import scipy.integrate as i\nfrom astropy.units import Quantity\n"
        "integrated = i.trapezoid(Quantity([1, 2, 3], 'W'), x=Quantity([0, 1, 2], 's'))\n")
    integration = op(result, "sampled_integration")
    byid = objects(result)
    assert byid[integration["inputs"][0]["object_id"]]["properties"]["dimensions"] == {"mass": 1, "length": 2, "time": -3}
    assert byid[integration["inputs"][1]["object_id"]]["properties"]["dimensions"] == {"time": 1}
    assert integration["output_ids"][0] in byid


def test_candidate_code_is_never_imported_and_stale_packet_is_rejected(tmp_path):
    source = tmp_path / "calculation.py"
    source.write_text("raise RuntimeError('must not run')\nfrom numpy.linalg import solve\nx = solve([[1]], [2])\n")
    packet = extract_evidence(tmp_path)
    assert extract_objects(tmp_path, packet)["coverage"]["recognized_scientific_operations"] == 1
    source.write_text("print('changed')\n")
    result = extract_objects(tmp_path, packet)
    assert result["objects"] == []
    assert all(u["reason"] == "stale_or_unreadable_source" for u in result["unsupported"])


def test_unrecognized_consumer_keeps_real_dataflow_without_claiming_meaning(tmp_path):
    result = graph(tmp_path, "from numpy.linalg import solve\nx = solve([[1]], [2])\ny = mystery(x)\n")
    consumer = op(result, "uninterpreted_call")
    assert consumer["inputs"][0]["object_id"] == binding(result, "x")["id"]
    assert consumer["properties"]["scientific_semantics"] == "unknown"
    assert consumer["documentation_url"] is None


def test_branch_local_operation_has_conditional_provenance(tmp_path):
    result = graph(tmp_path, "from numpy.linalg import solve\nif flag:\n    x = solve([[1]], [2])\n")
    assert op(result, "linear_solve")["properties"]["source_branch"]


def test_different_functions_never_share_same_named_parameter(tmp_path):
    result = graph(tmp_path, "from numpy.linalg import solve\ndef first(a):\n    return solve(a, [1])\ndef second(a):\n    return solve(a, [2])\n")
    params = [o for o in result["objects"] if o["symbol"] == "a"]
    assert len(params) == 2
    assert params[0]["id"] != params[1]["id"]
    assert params[0]["scope"] != params[1]["scope"]


@pytest.mark.parametrize("call,reason", [
    ("solve([[1]])", "missing_required_arguments"),
    ("solve(*inputs)", "unsupported_call_arguments"),
    ("solve([[1]], [2], invented=True)", "unsupported_call_keyword"),
])
def test_unsupported_call_signatures_are_visible(tmp_path, call, reason):
    result = graph(tmp_path, f"from numpy.linalg import solve\nx = {call}\n")
    assert result["coverage"]["recognized_scientific_operations"] == 0
    assert any(u["reason"] == reason for u in result["unsupported"])


def test_unknown_method_consumer_retains_receiver_but_does_not_propagate_units(tmp_path):
    result = graph(tmp_path, "from astropy.units import Quantity\ndistance = Quantity(1, 'm')\nconverted = distance.to('cm')\n")
    consumer = op(result, "uninterpreted_call")
    assert consumer["inputs"][0] == {"role": "receiver", "object_id": binding(result, "distance")["id"]}
    assert binding(result, "converted")["properties"]["dimensions"] is None


def test_array_options_and_nonliteral_graph_data_do_not_gain_invented_structure(tmp_path):
    result = graph(tmp_path, "import numpy as np\nimport networkx as nx\na = np.array([1, 2], ndmin=3)\n"
        "x = np.linalg.solve(a, [1, 2])\ng = nx.Graph(adjacency)\nparts = nx.connected_components(g)\n")
    assert binding(result, "a")["properties"]["shape"] is None
    assert binding(result, "g")["properties"]["topology"]["edges"] is None
    assert any(u["reason"] == "graph_topology_not_literal_edge_pairs" for u in result["unsupported"])


def test_parameter_rebound_by_unpacking_is_not_original_parameter(tmp_path):
    result = graph(tmp_path, "from numpy.linalg import solve\ndef f(a, pair):\n"
        "    a, other = pair\n    return solve(a, [1])\n")
    assert op(result, "linear_solve")["inputs"][0]["object_id"] is None
    assert any(u["reason"] == "unresolved_dataflow" and u.get("symbol") == "a" for u in result["unsupported"])


def test_dynamic_coordinates_retain_conditional_spacing_producer(tmp_path):
    result = graph(tmp_path, "from scipy.integrate import trapezoid\nfrom astropy.units import Quantity\n"
        "def f(x):\n    return trapezoid([1, 2], x=x, dx=Quantity(2, 's'))\n")
    integration = op(result, "sampled_integration")
    assert integration["properties"]["coordinate_mode"] == "conditional_x_or_spacing"
    inputs = {i["role"]: i["object_id"] for i in integration["inputs"]}
    assert inputs["integration_coordinates"] == binding(result, "x")["id"]
    assert objects(result)[inputs["sample_spacing"]]["properties"]["dimensions"] == {"time": 1}
    assert integration["properties"]["input_applicability"]["sample_spacing"] == "x is None"
    assert op(result, "quantity_construction")["output_ids"] == [inputs["sample_spacing"]]


def test_known_coordinates_keep_evaluated_but_ignored_spacing_without_using_it(tmp_path):
    result = graph(tmp_path, "from scipy.integrate import trapezoid\nfrom astropy.units import Quantity\n"
        "v = trapezoid([1, 2], x=[0, 1], dx=Quantity(2, 's'))\n")
    integration = op(result, "sampled_integration")
    inputs = {i["role"]: i["object_id"] for i in integration["inputs"]}
    assert integration["properties"]["coordinate_mode"] == "explicit_coordinates"
    assert inputs["sample_spacing"] is None
    assert inputs["evaluated_but_ignored_spacing"] == op(result, "quantity_construction")["output_ids"][0]


def test_none_coordinate_binding_selects_spacing(tmp_path):
    result = graph(tmp_path, "from scipy.integrate import trapezoid\ncoordinates = None\nx = trapezoid([1, 2], x=coordinates, dx=2)\n")
    integration = op(result, "sampled_integration")
    assert integration["properties"]["coordinate_mode"] == "uniform_spacing"
    assert integration["inputs"][1]["object_id"] is None
    assert objects(result)[integration["inputs"][2]["object_id"]]["properties"]["literal"] == 2


def test_indexed_wrapper_chain_has_source_targets_and_body_links(tmp_path):
    result = graph(tmp_path, "from numpy.linalg import solve\n"
        "def inside(a, b):\n    return solve(a, b)\n"
        "def outside(coeff, rhs):\n    return inside(coeff, rhs)\n"
        "answer = outside([[1]], [2])\n")
    wrappers = [o for o in result["operations"] if o["kind"] == "uninterpreted_call"]
    assert len(wrappers) == 2
    assert {o["properties"]["wrapper"]["function"] for o in wrappers} == {"inside", "outside"}
    for wrapper in wrappers:
        target = wrapper["properties"]["wrapper"]
        assert target["status"] == "lexical_target_only"
        assert target["path"] == "calculation.py"
        assert target["source_entry_id"].startswith("ev_")
        assert target["argument_and_return_equivalence"] == "not_derived"
        assert target["indexed_body_operation_ids"]
        assert any(l["source"] == wrapper["id"] and l["relation"] == "may_invoke_body" for l in result["links"])
    assert binding(result, "answer")["properties"]["dimensions"] is None


@pytest.mark.parametrize("extra,call", [
    ("inside = replacement\n", "inside([[1]], [2])"),
    ("def run(inside, a, b):\n    return inside(a, b)\n", "run([[1]], [2], [3])"),
])
def test_rebound_or_shadowed_wrappers_do_not_link_wrong_body(tmp_path, extra, call):
    result = graph(tmp_path, "from numpy.linalg import solve\ndef inside(a, b):\n    return solve(a, b)\n" + extra + f"answer = {call}\n")
    assert not any(l["relation"] == "may_invoke_body" and
                   l["target"] == op(result, "linear_solve")["id"] for l in result["links"])


def test_omitted_function_signature_does_not_gain_wrapper_link(tmp_path):
    (tmp_path / "calculation.py").write_text("from numpy.linalg import solve\ndef inside(a, b):\n    return solve(a, b)\nanswer = inside([[1]], [2])\n")
    packet = extract_evidence(tmp_path)
    packet["entries"] = [e for e in packet["entries"] if e["kind"] != "signature"]
    result = extract_objects(tmp_path, packet)
    assert not any(l["relation"] == "may_invoke_body" for l in result["links"])
    # Unconnected unknown calls may be omitted from graph, but their coverage
    # and unsupported-call records still expose the omitted wrapper boundary.
    assert result["coverage"]["totals"]["uninterpreted_calls"] == 1
    assert any(u.get("wrapper", {}).get("reason") == "function_signature_not_in_packet" for u in result["unsupported"])


def test_per_file_call_coverage_exposes_denominator_and_unknown_files(tmp_path):
    (tmp_path / "first.py").write_text("from numpy.linalg import solve\nx = solve([[1]], [2])\ny = mystery(x)\n")
    (tmp_path / "second.py").write_text("import numpy as np\nx = np.array([1])\ny = other(x)\n")
    (tmp_path / "empty.py").write_text("x = 1\n")
    result = extract_objects(tmp_path, extract_evidence(tmp_path))
    rows = {r["path"]: r for r in result["coverage"]["per_file"]}
    assert rows["first.py"]["inspected_calls"] == 2
    assert rows["first.py"]["scientific_call_fraction"] == .5
    assert rows["second.py"]["scientific_call_fraction"] == 0
    assert rows["second.py"]["support_operations"] == 1
    assert rows["empty.py"]["scientific_call_fraction"] is None
    total = result["coverage"]["totals"]
    assert total["inspected_calls"] == 4
    assert total["scientific_api_calls"] == 1
    assert total["uninterpreted_calls"] == 2
    assert total["scientific_call_fraction"] == .25


def test_arithmetic_does_not_inflate_scientific_api_call_coverage(tmp_path):
    result = graph(tmp_path, "from astropy.units import Quantity\na = Quantity(1, 'm')\nb = a * 2\nc = b / 3\n")
    totals = result["coverage"]["totals"]
    assert totals["scientific_operations"] == 3
    assert totals["scientific_api_calls"] == 1
    assert totals["inspected_calls"] == 1
    assert totals["scientific_call_fraction"] == 1


def test_quantity_reciprocal_and_division_invert_dimensions_and_unit_scale(tmp_path):
    result = graph(tmp_path, "from astropy.units import Quantity\n"
        "duration = Quantity(2, 'ms')\nfrequency = 1 / duration\n"
        "distance = Quantity(10, 'm')\nsmall = Quantity(2, 'cm')\nratio = distance / small\n")
    assert binding(result, "frequency")["properties"]["dimensions"] == {"time": -1}
    assert binding(result, "frequency")["properties"]["scale_to_si"] == "1000"
    assert binding(result, "ratio")["properties"]["dimensions"] == {}
    assert binding(result, "ratio")["properties"]["scale_to_si"] == "100"
