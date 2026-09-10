#!/usr/bin/env python3
"""Freeze a random comparison draw before materialization or model outcomes."""
from __future__ import annotations

import argparse
import secrets
from pathlib import Path

from scicontext.io import digest_file, read_json, utc_now, write_json
from scicontext.release import DATASET_REVISION, RELEASE_COMMIT, task_rows
from scicontext.sampling import select_tasks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--config-output", type=Path, required=True)
    parser.add_argument("--receipt", required=True)
    parser.add_argument("--seed")
    args = parser.parse_args()
    if args.output.exists() or args.config_output.exists():
        raise FileExistsError("Preserve the original draw; output already exists")
    snapshot = args.workspace / "data/release"
    prior = read_json(args.workspace / "data/release-receipt.json")
    table_hash = digest_file(snapshot / "data/tasks.csv")
    if table_hash != prior["table_sha256"] or prior["dataset_revision"] != DATASET_REVISION:
        raise ValueError("Release table differs from the previously pinned receipt")
    rows = task_rows(snapshot)
    seed = args.seed or secrets.token_hex(16)
    draw = select_tasks(rows, seed)
    by_id = {r["task_id"]: r for r in rows}
    draw.update({"created_at": utc_now(), "table_sha256": table_hash,
                 "dataset_revision": DATASET_REVISION, "release_commit": RELEASE_COMMIT,
                 "selected_metadata": [{k: by_id[t][k] for k in
                    ("task_id", "title", "domain", "language", "base_commit", "environment_image", "verifier_image")}
                                       for t in draw["task_ids"]]})
    write_json(args.output, draw)
    config = read_json(args.workspace / "configs/pilot.json")
    config.update(task_ids=draw["task_ids"], condition_order=draw["condition_order"],
                  study_kind="random_five_comparison", release_receipt=args.receipt,
                  sampling_manifest=str(args.output), sampling_manifest_sha256=digest_file(args.output))
    write_json(args.config_output, config)
    print(f"Frozen seed: {seed}; eligible population: {len(draw['eligible_task_ids'])}")
    for row in draw["selected_metadata"]:
        print(f"{row['task_id']}: {row['title']} [{row['domain']}; {row['language']}]")


if __name__ == "__main__":
    main()
