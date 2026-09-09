import hashlib
import json
from pathlib import Path

import pytest

from scicontext.evidence import MAX_FILE_BYTES, extract_evidence
from scicontext import evidence


def index_code(tmp_path, code, name="model.py"):
    (tmp_path / name).write_text(code, encoding="utf-8")
    return extract_evidence(tmp_path, [name])


def by_expression(index, text):
    return next(entry for entry in index["entries"] if entry["expression_text"] == text)


def test_extracts_supported_statements_and_hashes(tmp_path):
    code = '"""Density integrated over volume."""\nimport numpy as np\ndef mass(rho, volume):\n    """Return mass."""\n    total = np.sum(rho * volume)\n    assert total >= 0\n    return total\n'
    result = index_code(tmp_path, code)
    assert {entry["kind"] for entry in result["entries"]} >= {
        "docstring", "import", "signature", "assignment", "assertion", "comparison", "return"}
    assignment = by_expression(result, "np.sum(rho * volume)")
    assert assignment["expression"]["op"] == "sum"
    assert assignment["text"] == "total = np.sum(rho * volume)"
    assert assignment["sha256"] == hashlib.sha256(code.encode()).hexdigest()
    assert assignment["scope"] == "<module>.mass@3"
    assert assignment["imports"] == {"np": "numpy"}
    assert assignment["symbol_scopes"] == {"rho": "<module>.mass@3", "volume": "<module>.mass@3"}
    assert result["coverage"]["files_parsed"] == 1
    assert result == extract_evidence(tmp_path, ["model.py"])
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize("code, expression, expected", [
    ("import numpy as np\nx = np.sqrt(y)\n", "np.sqrt(y)", "sqrt"),
    ("from math import sqrt as root\nx = root(y)\n", "root(y)", "sqrt"),
    ("from numpy.linalg import norm as length\nx = length(y)\n", "length(y)", "norm"),
    ("import numpy.linalg as la\nx = la.norm(y)\n", "la.norm(y)", "norm"),
    ("import math\nx = math.sqrt(y)\n", "math.sqrt(y)", "sqrt"),
    ("x = sum(y)\n", "sum(y)", "unknown"),
    ("def sum(x):\n    return 0\nx = sum(y)\n", "sum(y)", "unknown"),
    ("from .numpy import sqrt\nx = sqrt(y)\n", "sqrt(y)", "unknown"),
    ("import unknown as np\nx = np.sqrt(y)\n", "np.sqrt(y)", "unknown"),
    ("import numpy as np\nnp = object()\nx = np.sqrt(y)\n", "np.sqrt(y)", "unknown"),
    ("import numpy as np\nnp.sqrt = other\nx = np.sqrt(y)\n", "np.sqrt(y)", "unknown"),
    ("if flag:\n    import numpy as np\nx = np.sqrt(y)\n", "np.sqrt(y)", "unknown"),
    ("from other import *\nx = sum(y)\n", "sum(y)", "unknown"),
    ("exec(code)\nx = sum(y)\n", "sum(y)", "unknown"),
])
def test_call_provenance_and_shadowing(tmp_path, code, expression, expected):
    result = index_code(tmp_path, code)
    assert by_expression(result, expression)["expression"]["op"] == expected


def test_function_lexical_shadowing_and_independent_scopes(tmp_path):
    result = index_code(tmp_path,
        "import numpy as np\n"
        "def good(x):\n    return np.sqrt(x)\n"
        "def shadow(np, x):\n    return np.sqrt(x)\n"
        "def late(x):\n    result = np.sqrt(x)\n    np = other\n    return result\n")
    calls = [entry for entry in result["entries"] if entry["expression_text"] == "np.sqrt(x)"]
    assert [entry["expression"]["op"] for entry in calls] == ["sqrt", "unknown", "unknown"]
    assert len({entry["scope"] for entry in calls}) == 3


def test_method_does_not_inherit_class_attribute_as_lexical_name(tmp_path):
    result = index_code(tmp_path, "import numpy as np\nclass C:\n    np = other\n    def f(self, x):\n        return np.sqrt(x)\n")
    assert by_expression(result, "np.sqrt(x)")["expression"]["op"] == "sqrt"


def test_nested_function_keeps_enclosing_parameter_shadow(tmp_path):
    result = index_code(tmp_path, "import numpy as np\ndef outer(np):\n    def inner(x):\n        return np.sqrt(x)\n    return inner\n")
    assert by_expression(result, "np.sqrt(x)")["expression"]["op"] == "unknown"


def test_branches_and_augmented_assignment_do_not_claim_dataflow(tmp_path):
    result = index_code(tmp_path, "def f(x, flag):\n    if flag:\n        value = x * 2\n    else:\n        value = x / 2\n    value += x\n    return value\n")
    assert by_expression(result, "x * 2")["branch"] == ["if@2:body"]
    assert by_expression(result, "x / 2")["branch"] == ["if@2:else"]
    augmented = next(entry for entry in result["entries"] if entry["kind"] == "augmented_assignment")
    assert augmented["expression"] == {"op": "symbol", "name": "x"}
    assert "In-place" in augmented["limitations"][0]
    assert any("complete dataflow" in text for text in result["coverage"]["limitations"])


def test_unicode_byte_spans_and_multiline_signature(tmp_path):
    code = 'def force(\n    ρ: "mass:density",\n    v=1,\n):\n    α = ρ * v; β = α / 2\n    return β\n'
    result = index_code(tmp_path, code)
    signature = next(entry for entry in result["entries"] if entry["kind"] == "signature")
    assert signature["text"] == 'def force(\n    ρ: "mass:density",\n    v=1,\n):'
    assert signature["end_line"] == 4
    beta = by_expression(result, "α / 2")
    assert beta["text"] == "β = α / 2"
    assert beta["start_col"] == len("    α = ρ * v; ".encode())
    span = beta["expression_span"]
    raw_line = code.splitlines()[span["start_line"] - 1].encode()
    assert raw_line[span["start_col"]:span["end_col"]].decode() == "α / 2"


def test_ids_change_with_content_path_and_span(tmp_path):
    first = index_code(tmp_path, "x = 1\n")
    second = index_code(tmp_path, "x = 2\n")
    third = index_code(tmp_path, "x = 2\n", "other.py")
    assert len({item["entries"][0]["id"] for item in (first, second, third)}) == 3


def test_no_task_import_or_execution(tmp_path):
    result = index_code(tmp_path, "raise RuntimeError('must not execute')\nx = 2\n")
    assert result["coverage"]["files_parsed"] == 1


def test_unsupported_languages_parse_errors_and_limits(tmp_path):
    (tmp_path / "native.c").write_text("int x = 1;")
    (tmp_path / "broken.py").write_text("def bad(:")
    (tmp_path / "large.py").write_bytes(b"#" * (MAX_FILE_BYTES + 1))
    result = extract_evidence(tmp_path)
    assert {entry["reason"] for entry in result["coverage"]["skipped"]} == {
        "unsupported_language", "parse_or_read_failure", "file_size_limit"}
    for i in range(3):
        (tmp_path / f"file{i}.py").write_text("x = 1\ny = 2\n")
    result = extract_evidence(tmp_path, ["file0.py", "file1.py", "file2.py"], max_files=2)
    assert result["coverage"]["files_truncated"]
    result = extract_evidence(tmp_path, ["file0.py"], max_entries=1)
    assert result["coverage"]["entries_truncated"]
    assert len(result["entries"]) == 1


def test_hidden_verifier_credentials_traversal_and_symlink_paths(tmp_path):
    public = tmp_path / "task"
    public.mkdir()
    (public / "ok.py").write_text("x = 1\n")
    (tmp_path / "outside.py").write_text("secret = 2\n")
    (public / "link.py").symlink_to(tmp_path / "outside.py")
    (public / "linked_dir").symlink_to(tmp_path, target_is_directory=True)
    for name in [".hidden.py", "verifier.py", "private_tests.py", "credentials.py", "auth.py", "token.py"]:
        (public / name).write_text("secret = 2\n")
    result = extract_evidence(public, ["ok.py", "../outside.py", "link.py", "linked_dir/outside.py", ".hidden.py", "verifier.py", "private_tests.py", "credentials.py", "auth.py", "token.py", str(tmp_path / "outside.py")])
    assert {entry["path"] for entry in result["entries"]} == {"ok.py"}
    assert {entry["reason"] for entry in result["coverage"]["skipped"]} >= {"symlink", "excluded_path", "path_outside_root"}
    default = extract_evidence(public)
    assert {entry["path"] for entry in default["entries"]} == {"ok.py"}


def test_symlink_swap_between_validation_and_read_is_rejected(tmp_path, monkeypatch):
    task = tmp_path / "task"
    task.mkdir()
    target = task / "model.py"
    target.write_text("x = 1\n")
    outside = tmp_path / "outside.py"
    outside.write_text("secret = 2\n")
    safe_file = evidence._safe_file

    def swapped(root, relative):
        result = safe_file(root, relative)
        target.unlink()
        target.symlink_to(outside)
        return result

    monkeypatch.setattr(evidence, "_safe_file", swapped)
    result = extract_evidence(task, ["model.py"])
    assert not result["entries"]
    assert result["coverage"]["skipped"][0]["reason"] == "parse_or_read_failure"


def test_nonutf8_declared_source_is_hashed_as_original_bytes(tmp_path):
    raw = b"# coding: latin-1\n# caf\xe9\nx = 2\n"
    (tmp_path / "model.py").write_bytes(raw)
    result = extract_evidence(tmp_path, ["model.py"])
    assert result["entries"][0]["sha256"] == hashlib.sha256(raw).hexdigest()


def test_public_tests_included_and_private_directory_excluded(tmp_path):
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_public.py").write_text("assert 1 == 1\n")
    (tmp_path / "private_tests").mkdir()
    (tmp_path / "private_tests" / "test_hidden.py").write_text("assert 2 == 2\n")
    result = extract_evidence(tmp_path)
    assert {entry["path"] for entry in result["entries"]} == {"tests/test_public.py"}


def test_bad_limits_are_errors(tmp_path):
    with pytest.raises(ValueError):
        extract_evidence(tmp_path, max_files=0)
    with pytest.raises(ValueError):
        extract_evidence(tmp_path, max_entries=True)
    with pytest.raises(ValueError):
        extract_evidence(tmp_path, paths="model.py")
