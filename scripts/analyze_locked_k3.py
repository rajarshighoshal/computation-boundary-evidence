"""Load verifier outcomes and recorded usage from a run tree.

``load_runs`` returns ``data[task][arm]`` -> list of attempt records, one per
trial, with the fields the evidence-packet exporter consumes:

  reward             official verifier reward, or None when no verdict exists
  in, out            tokens recorded by the run's own stages
  work_seconds       summed stage wall time
  private_passed     private tests passed, private_collected tests collected

Arms keep the run-directory names: ``baseline`` and ``science``.

A slot with no verdict (infrastructure failure, timeout, missing record) is
filled from ``gap_fill`` when that run directory is supplied: the whole record
is replaced by the gap-fill trial's record, so the attempt still counts once.
"""
from __future__ import annotations

import json
from pathlib import Path

ARMS = ("baseline", "science")
REPLACED = ("reward", "in", "out", "work_seconds", "private_passed", "private_collected")


def _read(path: Path) -> dict:
    return json.loads(path.read_text()) if path.is_file() else {}


def _trial(trial: Path) -> tuple[str, str, dict] | None:
    parts = trial.parent.name.split("-", 2)
    if len(parts) != 3 or parts[0] != "task" or parts[2] not in ARMS:
        return None
    task, arm = parts[1], parts[2]
    run = _read(trial / "run.json")
    verifier = _read(trial / "verifier" / "reward.json")
    stages = run.get("stages", [])
    private = verifier.get("private") or {}
    return task, arm, {
        "reward": verifier.get("reward"),
        "in": sum((s.get("usage") or {}).get("input_tokens") or 0 for s in stages),
        "out": sum((s.get("usage") or {}).get("output_tokens") or 0 for s in stages),
        "work_seconds": sum(s.get("work_seconds") or 0.0 for s in stages),
        "private_passed": private.get("passed") or 0,
        "private_collected": private.get("collected") or 0,
    }


def load_runs(paths, gap_fill: Path | None = None) -> dict[str, dict[str, list[dict]]]:
    data: dict[str, dict[str, list[dict]]] = {}
    unfilled: dict[tuple[str, str], dict] = {}
    for run in paths:
        for trial in sorted((Path(run) / "jobs").glob("task-*/task_*")):
            parsed = _trial(trial)
            if parsed is None:
                continue
            task, arm, record = parsed
            data.setdefault(task, {}).setdefault(arm, []).append(record)
            if record["reward"] is None:
                unfilled[(task, arm)] = record
    if gap_fill is not None and unfilled:
        for trial in sorted((Path(gap_fill) / "jobs").glob("task-*/task_*")):
            parsed = _trial(trial)
            if parsed is None:
                continue
            task, arm, record = parsed
            slot = unfilled.get((task, arm))
            if slot is not None and record["reward"] is not None:
                slot.update({key: record[key] for key in REPLACED})
                unfilled.pop((task, arm))
        if unfilled:
            raise ValueError(f"No gap-fill verdict for {sorted(unfilled)}")
    return data
