"""Reproducible, outcome-independent sampling from the pinned public release."""
from __future__ import annotations

import hashlib


def select_tasks(rows: list[dict], seed: str, count: int = 5,
                 excluded: tuple[str, ...] = ("002", "077")) -> dict:
    if not seed or type(count) is not int or not 1 <= count <= 5:
        raise ValueError("A public seed and a sample size from one to five are required")
    if len({r["task_id"] for r in rows}) != len(rows):
        raise ValueError("Duplicate task IDs in population")
    eligible, exclusions = [], []
    for row in sorted(rows, key=lambda r: r["task_id"]):
        task = row["task_id"]
        reason = ("development_task" if task in excluded else
                  "restricted_license" if str(row["restricted_license"]).lower() != "false"
                  or row.get("license_gate", "none") != "none" else None)
        if reason:
            exclusions.append({"task_id": task, "reason": reason})
        else:
            eligible.append(task)
    if len(eligible) < count:
        raise ValueError("Not enough eligible tasks")
    key = lambda task: hashlib.sha256((seed + ":" + task).encode()).hexdigest()
    selected = sorted(eligible, key=lambda task: (key(task), task))[:count]
    first_science = int(hashlib.sha256((seed + ":condition-order").encode()).hexdigest(), 16) % 2
    order = {task: (["science", "baseline"] if (i + first_science) % 2 else ["baseline", "science"])
             for i, task in enumerate(selected)}
    return {"algorithm": "SHA256(seed + colon + task_id) ranking; take first k",
            "seed": seed, "count": count, "eligible_task_ids": eligible,
            "excluded": exclusions, "task_ids": selected, "condition_order": order,
            "selection_scores": {task: key(task) for task in selected},
            "replacement_policy": "No outcome-based replacements; retain infrastructure failures"}
