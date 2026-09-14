"""The staged run is exactly the approved30 pairs, not extra attempts or evaluation tasks."""
from pathlib import Path

from scicontext.io import digest_file, read_json


def test_e2e_configs_cover_development_once_with_matched_settings():
    root = Path(__file__).resolve().parents[1]
    split_path = root / "configs/interactive-science.split.json"
    split = read_json(split_path)
    check = read_json(root / "configs/development-e2e-check.json")
    wide = read_json(root / "configs/development-e2e-40.json")
    assert check["task_ids"] == ["009"] and check["concurrency"] == 2
    assert wide["concurrency"] == 40  # Total across both arms, not40 per arm.
    ids = check["task_ids"] + wide["task_ids"]
    assert len(ids) == len(set(ids)) == 30
    assert set(ids) == set(split["development_task_ids"])
    assert not set(ids) & set(split["locked_evaluation_task_ids"])
    for config in (check, wide):
        assert config["study_split_sha256"] == digest_file(split_path)
        assert config["development_task_ids"] == split["development_task_ids"]
        assert config["study_partition"] == "development"
        assert config["agent"] == "deepseek"
        assert config["model"] == "deepseek-flash"
        assert config["reasoning_effort"] == "high"
        assert config["attempts"] == 1
        assert config["total_seconds"] == config["verifier_seconds"] == 1800
        assert config["conditions"] == ["baseline", "science"]
        assert config["extractor"] == "interactive_science"
        assert not config.get("extraction_only")
        for task in config["task_ids"]:
            assert config["condition_order"][task] == split["condition_order"][task]
            assert sorted(config["condition_order"][task]) == ["baseline", "science"]
    runtime_settings = ("agent", "model", "reasoning_effort", "total_seconds", "extraction_seconds",
                        "verifier_seconds", "extractor", "handoff", "release_receipt",
                        "release_commit", "dataset_revision", "pier_version")
    assert {k: check[k] for k in runtime_settings} == {k: wide[k] for k in runtime_settings}
