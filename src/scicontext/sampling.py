"""Reproducible, outcome-independent sampling from the pinned public release."""
from __future__ import annotations

import hashlib

DEVELOPMENT_ANCHORS = ("001", "002", "004", "009", "010", "016", "019", "025", "051", "058", "077", "091", "114")
INTERACTIVE_SEED = "interactive-science-v1-20260914"


def split_tasks(rows, seed=INTERACTIVE_SEED, count=30):
    by_id = {r["task_id"]: r for r in rows}
    if len(by_id) != len(rows) or not set(DEVELOPMENT_ANCHORS) <= by_id.keys() or count < len(DEVELOPMENT_ANCHORS):
        raise ValueError("Invalid population or development size")
    eligible = [t for t, r in by_id.items() if t not in DEVELOPMENT_ANCHORS
                and str(r.get("restricted_license", "false")).lower() == "false"
                and r.get("license_gate", "none") == "none"]
    rank = lambda t: hashlib.sha256((seed + ":" + t).encode()).hexdigest()
    drawn = sorted(eligible, key=lambda t: (rank(t), t))[:count-len(DEVELOPMENT_ANCHORS)]
    if len(drawn) + len(DEVELOPMENT_ANCHORS) != count:
        raise ValueError("Not enough eligible development tasks")
    development = sorted([*DEVELOPMENT_ANCHORS, *drawn])
    evaluation = sorted(set(by_id) - set(development))
    order = {t: (["science", "baseline"] if int(rank(t), 16) % 2 else ["baseline", "science"]) for t in by_id}
    return {"schema_version": "study-split-1.0", "seed": seed,
            "algorithm": "Known design cases plus first remaining unrestricted IDs by SHA256(seed:task_id)",
            "development_task_ids": development, "locked_evaluation_task_ids": evaluation,
            "design_case_anchors": list(DEVELOPMENT_ANCHORS), "random_development_task_ids": drawn,
            "condition_order": order,
            "restricted_task_ids": sorted(t for t, r in by_id.items() if str(r.get("restricted_license", "false")).lower() != "false"),
            "missing_source_commit_task_ids": sorted(t for t, r in by_id.items() if not str(r.get("base_commit") or "").strip()),
            "policy": "Prior pipeline runs are recorded separately; no outcome-based replacement or claim of historically untouched evaluation."}


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
