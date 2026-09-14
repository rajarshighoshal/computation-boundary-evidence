"""Aggregate saved execution evidence; source parsing determines callable identity."""
from __future__ import annotations

import gzip
import json
from collections import defaultdict
from pathlib import Path

TRACE_FILENAME = "trace.jsonl.gz"


def read_execution(trace_dir):
    trace_dir = Path(trace_dir)
    records = {}
    status = "complete"
    try:
        with gzip.open(trace_dir / TRACE_FILENAME, "rt", encoding="utf-8") as stream:
            for line in stream:
                try:
                    row = json.loads(line)
                except ValueError:
                    status = "partial"
                    continue
                if not isinstance(row, dict) or type(row.get("seq")) is not int or type(row.get("line")) is not int:
                    continue
                if not isinstance(row.get("name"), str) or not isinstance(row.get("file"), str):
                    continue
                pid = row.get("pid", 0)  # Older single-process records lacked pid.
                if type(pid) is not int:
                    continue
                identity = (pid, row["seq"])
                parent = row.get("parent_seq")
                records[identity] = ((pid, parent) if type(parent) is int else None,
                                     (row["file"], row["name"], row["line"]))
    except FileNotFoundError:
        status = "missing"
    except (OSError, EOFError, UnicodeError):
        status = "partial" if records else "unreadable"
    depths = {}
    for start in sorted(records):
        chain, seen, current = [], set(), start
        while current not in depths:
            if current in seen:
                for key in chain:
                    depths[key] = None  # Corrupt ancestry is unknown, not a root.
                break
            seen.add(current)
            parent = records[current][0]
            if parent not in records:
                depths[current] = 0  # Depth within the observed trace only.
                break
            chain.append(current)
            current = parent
        base = depths.get(current)
        for key in reversed(chain):
            if key in depths:
                base = depths[key]
                continue
            base = base + 1 if base is not None else None
            depths[key] = base
    grouped = defaultdict(list)
    for identity, (_, key) in records.items():
        grouped[key].append(identity)
    functions = []
    for (file, name, line), identities in grouped.items():
        known = [depths[i] for i in identities if depths[i] is not None]
        functions.append({"file": file, "name": name, "line": line, "count": len(identities),
                          "min_depth": min(known) if known else None,
                          "first_seq": min(i[1] for i in identities),
                          "pids": sorted({i[0] for i in identities})})
    functions.sort(key=lambda r: (r["min_depth"] is None, r["min_depth"] or 0,
                                  -r["count"], r["file"], r["name"], r["line"]))
    try:
        run = json.loads((trace_dir / "run.json").read_text())
    except (OSError, ValueError):
        run = {}
    try:
        report = json.loads((trace_dir / "script_report.json").read_text())
    except (OSError, ValueError):
        report = {}
    return {"functions": functions, "trace_status": status,
            "reproduction_status": report.get("status") or run.get("script_status") or "unknown",
            "reproduction_error": report.get("error") or run.get("script_traceback"),
            "scope": "Completed observed frames; not proof that unrecorded code did not execute."}


def executed_functions(trace_dir):
    return read_execution(trace_dir)["functions"]


def seed_summary(seed):
    depths = [r["min_depth"] for r in seed if r.get("min_depth") is not None]
    return {"observed_frames": len(seed), "files": len({r["file"] for r in seed}),
            "max_observed_depth": max(depths, default=0)}
