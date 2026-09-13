import hashlib

from scicontext import packet
from scicontext.evidence import extract_evidence
from scicontext.packet import build_packet, render_catalog


def write(root, path, text):
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    return target


def test_entries_unchanged_deterministic_and_target_never_executed(tmp_path):
    write(tmp_path, "model.py", "raise RuntimeError('must not run')\nx = density * volume\n")
    result = build_packet(tmp_path)
    assert result == build_packet(tmp_path)
    assert result["schema_version"] == "packet-1.0"
    assert result["entries"] == extract_evidence(tmp_path, ["model.py"])["entries"]
    assert result["coverage"]["files_parsed"] == 1


def test_capped_reference_allocation_preserves_later_body_and_parameters(tmp_path, monkeypatch):
    import ast

    parameters = ", ".join(f"p{i}" for i in range(150))
    source = (f"def early({parameters}):\n" +
              "".join(f"    x{i} = p0 + {i}\n" for i in range(160)) +
              "    return x159\n" +
              f"def later({parameters}):\n" +
              "".join(f"    y{i} = p0 + {i}\n" for i in range(10)) +
              "    selected = scientific_transform(y9)\n    return selected\n" +
              "def last(value):\n    return value\n")
    write(tmp_path, "model.py", source)
    functions = ast.parse(source).body
    references = [{"path": "model.py", "start_line": f.lineno, "end_line": f.end_lineno}
                  for f in functions]
    monkeypatch.setattr(packet, "seed_references", lambda *args: (references, {"references": references}))
    result = build_packet(tmp_path)
    entries = result["entries"]
    assert len(entries) == packet.MAX_ENTRIES_PER_FILE == 128
    assert len(entries) <= packet.MAX_ENTRIES == 512
    assert result["coverage"]["entries_truncated"]
    assert any(e["expression_text"] == "scientific_transform(y9)" for e in entries)
    for function in functions:
        scoped = [e for e in entries if e["scope"] == f"<module>.{function.name}@{function.lineno}"]
        assert any(e["kind"] == "parameter" for e in scoped)
        assert any(e["kind"] in {"assignment", "return"} for e in scoped)
    complete = {e["id"]: e for e in extract_evidence(tmp_path)["entries"]}
    assert all(e["id"] in complete for e in entries)
    assert all(e["text"] == complete[e["id"]]["text"] for e in entries)
    assert build_packet(tmp_path) == result
    # A repeated broad reference cannot buy its function extra allocation.
    repeated = extract_evidence(tmp_path, ["model.py"], max_entries=128,
                                 references=[*references, references[0]])
    assert [e["id"] for e in repeated["entries"]] == [e["id"] for e in entries]


def test_scientific_packet_retains_defining_interfaces_and_scientific_docstrings(tmp_path, monkeypatch):
    import ast
    from scicontext.object_context import enrichment_input
    from scicontext.scientific_objects import extract_objects

    source = '"""Scientific storage model."""\nclass Model:\n    """Positive flow leaves the reservoir."""\n'
    for name in ("advance", "report"):
        source += f'    def {name}(self, volume):\n        """Volume is stored water, not flow rate."""\n'
        source += "".join(f"        temp{i} = volume * {i}\n" for i in range(60))
        source += "        return temp59\n"
    write(tmp_path, "model.py", source)
    methods = [n for n in ast.walk(ast.parse(source)) if isinstance(n, ast.FunctionDef)]
    refs = [{"path": "model.py", "start_line": f.lineno, "end_line": f.end_lineno} for f in methods]
    monkeypatch.setattr(packet, "seed_references", lambda *args: (refs, {"references": refs}))
    monkeypatch.setattr(packet, "MAX_ENTRIES_PER_FILE", 20)
    legacy = build_packet(tmp_path)
    assert not any(e["kind"] == "signature" for e in legacy["entries"])
    scientific = build_packet(tmp_path, multilingual=True)
    assert len(scientific["entries"]) <= 20 and scientific["coverage"]["entries_truncated"]
    graph = extract_objects(tmp_path, scientific)
    for method in methods:
        assert any(o["kind"] == "code_interface" and o["scope"].endswith(f".{method.name}@{method.lineno}") for o in graph["objects"])
    payload = str(enrichment_input(graph, scientific))
    assert "Positive flow leaves" in payload and "stored water, not flow rate" in payload
    assert build_packet(tmp_path) == legacy  # The scientific opt-in does not change historical selection.
    assert build_packet(tmp_path, multilingual=True) == scientific


def test_documents_validate_exact_lines_hashes_and_explicit_context(tmp_path):
    root, context = tmp_path / "root", tmp_path / "context"
    root.mkdir()
    write(root, "README.md", "# Scientific model\n\nDensity is mass / volume.\n")
    target = write(context, "task_statement.md", "Required units: kg / m^3.\nKeep the return shape.\n")
    write(context, "unrelated.md", "Must not index this.\n")
    result = build_packet(root, context)
    assert {d["path"] for d in result["documents"]} == {"README.md", "@context/task_statement.md"}
    cited = next(d for d in result["documents"] if d["path"].startswith("@context/"))
    assert cited["sha256"] == hashlib.sha256(target.read_bytes()).hexdigest()
    assert cited["quote"] == "Required units: kg / m^3.\nKeep the return shape."
    assert not any(d["path"].startswith("@context/") for d in build_packet(root)["documents"])
    old_id = cited["id"]
    target.write_text("Changed statement\n", encoding="utf-8")
    assert build_packet(root, context)["documents"][0]["id"] != old_id


def test_linked_scientific_documents_survive_discovery_and_document_caps(tmp_path, monkeypatch):
    write(tmp_path, "paper.md", "Model definition: source/docs/conventions.rst\n")
    write(tmp_path, "a_table.txt", "Incidental lookup table\n")
    write(tmp_path, "source/docs/conventions.rst", "Velocity uses metres per second.\n")
    monkeypatch.setattr(packet, "MAX_SCAN_DIRECTORIES", 1)
    monkeypatch.setattr(packet, "MAX_DOCUMENT_FILES", 2)
    result = build_packet(tmp_path, multilingual=True)
    assert result["coverage"]["directories_truncated"]
    assert result["coverage"]["selected_document_paths"][0] == "source/docs/conventions.rst"
    assert any(d["quote"] == "Velocity uses metres per second." for d in result["documents"])
    assert result["coverage"]["document_references"] == [
        {"path": "source/docs/conventions.rst", "via": "paper.md"}]
    assert result == build_packet(tmp_path, multilingual=True)


def test_document_links_are_one_hop_relative_and_public_only(tmp_path, monkeypatch):
    root, context = tmp_path / "root", tmp_path / "context"
    write(context, "task_statement.md", "See docs/overview.md.\n")
    write(root, "docs/overview.md", "[contract](../source/model.rst)\n"
          "../private/secret.md\n../../outside.md\n../alias.md\n")
    write(root, "source/model.rst", "Preserve the normalization. More: deeper/extra.md\n")
    write(root, "source/deeper/extra.md", "Third hop, not selected.\n")
    write(root, "private/secret.md", "Private text.\n")
    outside = write(tmp_path, "outside.md", "Outside text.\n")
    (root / "alias.md").symlink_to(outside)
    monkeypatch.setattr(packet, "MAX_SCAN_DIRECTORIES", 1)
    result = build_packet(root, context, multilingual=True)
    assert {d["path"] for d in result["documents"]} == {
        "@context/task_statement.md", "docs/overview.md", "source/model.rst"}
    assert result["coverage"]["document_references"] == [
        {"path": "source/model.rst", "via": "docs/overview.md"}]


def test_both_retrievers_receive_body_allocation_before_fallback(tmp_path, monkeypatch):
    from scicontext import workflow_retrieval

    write(tmp_path, "reproduce.py", "def main():\n    return 0\n")
    write(tmp_path, "source/model.py", 'def advance(x):\n    """x is stored volume."""\n' +
          "".join(f"    v{i} = x * {i}\n" for i in range(40)) + "    return v39\n")
    for i in range(24):
        write(tmp_path, f"a{i}.py", "unused = 0\n")
    refs = [{"path": "source/model.py", "start_line": 1, "end_line": 43, "depth": 1}]
    workflow = [{"path": "reproduce.py", "start_line": 1, "end_line": 2, "depth": 0}]
    monkeypatch.setattr(packet, "seed_references", lambda *args: (refs, {"references": refs}))
    monkeypatch.setattr(workflow_retrieval, "retrieve", lambda *args: (workflow, {"references": workflow}))
    result = build_packet(tmp_path, multilingual=True)
    selected = result["coverage"]["selected_source_paths"]
    assert selected[:2] == ["reproduce.py", "source/model.py"]
    allocations = result["coverage"]["entry_allocations"]
    assert allocations["source/model.py"] > 10 * allocations["a0.py"]
    assert any(e["path"] == "source/model.py" and e["text"] == "return v39"
               for e in result["entries"])
    assert sum(e["path"] == "source/model.py" for e in result["entries"]) > 40
    assert len(result["entries"]) <= packet.MAX_ENTRIES


def test_task_and_reproducer_paths_outrank_root_and_deep_files(tmp_path, monkeypatch):
    root, context = tmp_path / "root", tmp_path / "context"
    write(root, "a.py", "unused = 1\n")
    write(root, "reproduce.py", "# Examine source/physics/solver.py\nx = 2\n")
    write(root, "source/physics/solver.py", "answer = 3\n")
    write(root, "source/physics/requested.py", "answer = 4\n")
    write(context, "task_statement.md", "Fix `source/physics/requested.py`.\n")
    monkeypatch.setattr(packet, "MAX_SOURCE_FILES", 3)
    result = build_packet(root, context)
    assert result["coverage"]["selected_source_paths"] == [
        "source/physics/requested.py", "reproduce.py", "source/physics/solver.py"]
    assert result["coverage"]["files_truncated"]
    assert {e["path"] for e in result["entries"]} == set(result["coverage"]["selected_source_paths"])


def test_explicit_task_path_survives_traversal_budget(tmp_path, monkeypatch):
    root, context = tmp_path / "root", tmp_path / "context"
    write(root, "a.py", "x = 1\n")
    write(root, "b.py", "x = 2\n")
    write(root, "src/target.py", "x = 3\n")
    write(context, "task_statement.md", "Read src/target.py.\n")
    monkeypatch.setattr(packet, "MAX_SCAN_FILES", 1)
    result = build_packet(root, context)
    assert result["coverage"]["scan_files_truncated"]
    assert result["coverage"]["files_scanned"] == 1
    assert result["coverage"]["selected_source_paths"][0] == "src/target.py"


def test_private_generated_symlink_and_shadow_context_excluded(tmp_path):
    root, context = tmp_path / "root", tmp_path / "context"
    write(root, "model.py", "x = 1\n")
    write(root, "source/outputs/public.py", "x = 2\n")
    for path in ["outputs/probe.py", "outputs/receipt.md", "private/README.md", ".hidden.md",
                 "credentials.txt", "verifier.py", "@context/task_statement.md"]:
        write(root, path, "secret = 99\n")
    outside = write(tmp_path, "outside.md", "Secret outside source.\n")
    (root / "link.md").symlink_to(outside)
    (root / "linked_dir").symlink_to(tmp_path, target_is_directory=True)
    context.mkdir()
    (context / "task_statement.md").symlink_to(outside)
    result = build_packet(root, context)
    assert {e["path"] for e in result["entries"]} == {"model.py", "source/outputs/public.py"}
    assert result["documents"] == []
    reasons = {row["reason"] for row in result["coverage"]["skipped"]}
    assert reasons >= {"symlink", "excluded_path", "excluded_directory"}


def test_document_read_rejects_symlink_swap(tmp_path, monkeypatch):
    root = tmp_path / "root"
    target = write(root, "README.md", "Public text.\n")
    outside = write(tmp_path, "outside.md", "Secret text.\n")
    safe = packet.evidence._safe_file
    reads = 0

    def swapped(root, relative):
        nonlocal reads
        result = safe(root, relative)
        reads += 1
        if reads == 2:  # First is discovery, second is the document read.
            target.unlink()
            target.symlink_to(outside)
        return result

    monkeypatch.setattr(packet.evidence, "_safe_file", swapped)
    result = build_packet(root)
    assert result["documents"] == []
    assert result["coverage"]["skipped"][-1]["reason"] == "parse_or_read_failure"


def test_preserves_parse_unsupported_and_entry_limit_coverage(tmp_path, monkeypatch):
    write(tmp_path, "model.py", "x = custom(y)\na = 1\nb = 2\n")
    write(tmp_path, "broken.py", "def bad(:\n")
    write(tmp_path, "native.c", "int x = 1;\n")
    monkeypatch.setattr(packet, "MAX_ENTRIES_PER_FILE", 1)
    result = build_packet(tmp_path)
    coverage = result["coverage"]
    assert coverage["entries_truncated"]
    assert coverage["unsupported_expressions"] == 1
    assert {row["reason"] for row in coverage["skipped"]} >= {"unsupported_language", "parse_or_read_failure"}
    assert result["entries"][0]["limitations"]


def test_document_chunks_never_cut_lines_and_report_omissions(tmp_path, monkeypatch):
    write(tmp_path, "README.md", "a line\n" + "x" * 50 + "\nthird line\nfourth line\n")
    monkeypatch.setattr(packet, "MAX_DOCUMENT_CHARS", 20)
    monkeypatch.setattr(packet, "MAX_DOCUMENT_LINES", 1)
    monkeypatch.setattr(packet, "MAX_DOCUMENTS_PER_FILE", 2)
    result = build_packet(tmp_path)
    assert [d["quote"] for d in result["documents"]] == ["a line", "third line"]
    assert [(d["start_line"], d["end_line"]) for d in result["documents"]] == [(1, 1), (3, 3)]
    assert result["coverage"]["documents_truncated"]
    assert {row["reason"] for row in result["coverage"]["skipped"]} == {"document_line_limit", "document_span_limit"}


def test_catalog_is_compact_bounded_and_represents_each_source(tmp_path, monkeypatch):
    write(tmp_path, "a.py", "\n".join(f"x{i} = {i}" for i in range(30)))
    write(tmp_path, "b.py", "def physics(x):\n    return x * 100\n")
    write(tmp_path, "README.md", "A description " * 2000)
    result = build_packet(tmp_path)
    monkeypatch.setattr(packet, "MAX_CATALOG_ROWS", 3)
    catalog = render_catalog(result)
    assert len(catalog) <= packet.MAX_CATALOG_CHARS
    assert "a.py" in catalog and "b.py" in catalog
    assert "Catalog truncated:" in catalog
    assert '"op"' not in catalog
    assert "A description " * 100 not in catalog
    assert catalog == render_catalog(result)


def test_utf8_only_documents_and_missing_context_have_explicit_coverage(tmp_path):
    (tmp_path / "README.md").write_bytes(b"not utf8: \xff")
    result = build_packet(tmp_path, tmp_path / "absent")
    assert result["documents"] == []
    assert {(row["path"], row["reason"]) for row in result["coverage"]["skipped"]} == {
        ("README.md", "parse_or_read_failure"), ("@context/task_statement.md", "unreadable_path")}
