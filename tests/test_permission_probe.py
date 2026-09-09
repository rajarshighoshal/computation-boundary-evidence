from scicontext.permission_probe import process_information


def test_process_view_must_match_actual_pid(tmp_path):
    (tmp_path / "2").mkdir()
    (tmp_path / "2/statm").write_text("100 20 0 0 0 0 0\n")
    (tmp_path / "self").symlink_to("2")
    assert process_information(tmp_path, 2)[0]
    (tmp_path / "self").unlink()
    (tmp_path / "self").symlink_to("123")
    ok, diagnostics = process_information(tmp_path, 2)
    assert not ok and not diagnostics["proc_self_matches_pid"]


def test_missing_or_unreadable_proc_fails_closed(tmp_path, monkeypatch):
    assert process_information(tmp_path, 2) == (False, {"process_info_errno": 2})
    (tmp_path / "2").mkdir()
    (tmp_path / "self").symlink_to("2")
    def denied(*args, **kwargs):
        raise PermissionError(13, "denied")
    monkeypatch.setattr(type(tmp_path), "read_text", denied)
    assert process_information(tmp_path, 2) == (False, {"process_info_errno": 13})


def test_malformed_memory_information_is_not_a_pass(tmp_path):
    (tmp_path / "2").mkdir()
    (tmp_path / "self").symlink_to("2")
    (tmp_path / "2/statm").write_text("not memory information")
    assert not process_information(tmp_path, 2)[0]
