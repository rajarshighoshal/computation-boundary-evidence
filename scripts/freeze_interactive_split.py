"""Freeze the approved development/evaluation split without reading repair outcomes."""
import argparse
from pathlib import Path

from scicontext.io import digest_file, read_json, write_json
from scicontext.sampling import split_tasks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("configs/interactive-science.split.json"))
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Keep the frozen split; do not redraw")
    release_path = Path("data/full-119-release.json")
    release = read_json(release_path)
    split = split_tasks(release["tasks"])
    split.update(dataset_revision=release["dataset_revision"], release_commit=release["release_commit"],
                 release_receipt=str(release_path), release_receipt_sha256=digest_file(release_path),
                 extra_private_diagnostic_exposure_task_ids=["001"])
    history = Path("runs/full-119-repair/schedule.json")
    split["historical_pipeline_activity"] = {"extraction": "All119 had earlier pipeline runs; this is not private-test leakage or automatic design use."}
    if history.is_file():
        previous = read_json(history)
        split["historical_pipeline_activity"].update(repair_schedule=str(history), repair_schedule_sha256=digest_file(history),
            attempted_repair_task_ids=sorted({r["task_id"] for r in previous["schedule"] if r.get("started_at")}))
    write_json(args.output, split)
    print("Frozen:", len(split["development_task_ids"]), "development;", len(split["locked_evaluation_task_ids"]), "locked evaluation")


if __name__ == "__main__":
    main()
