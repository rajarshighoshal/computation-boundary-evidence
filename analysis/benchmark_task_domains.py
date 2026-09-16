"""Extract the benchmark's authoritative task -> scientific-domain mapping.

Primary source: the SWE-bench Science paper (arXiv 2608.19799v2), Appendix Table 5
("Task-level scientific-domain, provenance, and scientific-knowledge inventory"),
which assigns every task ID (001-119) to one of the 20 scientific domains listed in
Appendix Table 4.

The table is extracted from the PDF with `pdftotext -layout`; long domain names wrap
inside the narrow column, so truncated prefixes are resolved against the canonical
20-domain list. The extraction is validated by reproducing the exact per-domain task
counts published in Table 4; any mismatch is a hard error.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PDF = REPO / "2608.19799v2.pdf"
OUT = REPO / "results" / "benchmark-task-domains.json"

# Canonical domain list with the published counts (paper Appendix Table 4).
CANONICAL_COUNTS: dict[str, int] = {
    "Chemistry": 24,
    "Materials Science and Engineering": 16,
    "Biology": 13,
    "Biomedical Engineering": 12,
    "Physics": 11,
    "Mathematics": 7,
    "Astronomy": 7,
    "Atmospheric Science": 5,
    "Civil Engineering": 5,
    "Surveying and Mapping Science and Technology": 3,
    "Geophysics": 3,
    "Mechanics": 3,
    "Electrical Engineering": 2,
    "Marine Science": 2,
    "Geography": 1,
    "Aeronautical and Astronautical Science and Technology": 1,
    "Nuclear Science and Technology": 1,
    "Computer Science and Technology": 1,
    "Statistics": 1,
    "Information and Communication Engineering": 1,
}

# Prefix -> canonical name. Extraction yields the left-most cell content, which may be
# truncated where the cell wraps. Every published prefix is unique across the 20 domains.
PREFIX_TO_CANONICAL: dict[str, str] = {
    "Chemistry": "Chemistry",
    "Materials Science": "Materials Science and Engineering",
    "Biology": "Biology",
    "Biomedical": "Biomedical Engineering",
    "Physics": "Physics",
    "Mathematics": "Mathematics",
    "Astronomy": "Astronomy",
    "Atmospheric": "Atmospheric Science",
    "Civil": "Civil Engineering",
    "Surveying and": "Surveying and Mapping Science and Technology",
    "Surveying and Mapping": "Surveying and Mapping Science and Technology",
    "Geophysics": "Geophysics",
    "Mechanics": "Mechanics",
    "Electrical": "Electrical Engineering",
    "Marine": "Marine Science",
    "Geography": "Geography",
    "Aeronautical and": "Aeronautical and Astronautical Science and Technology",
    "Aeronautical and Astronautical": "Aeronautical and Astronautical Science and Technology",
    "Nuclear": "Nuclear Science and Technology",
    "Computer": "Computer Science and Technology",
    "Statistics": "Statistics",
    "Information and": "Information and Communication Engineering",
    "Information and Communication": "Information and Communication Engineering",
}

ROW = re.compile(r"^(\d{3})\s{2,}(\S.*?)\s{2,}(\S.*)$")


def extract() -> dict[str, str]:
    text = subprocess.run(
        ["pdftotext", "-layout", str(PDF), "-"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout

    mapping: dict[str, str] = {}
    for line in text.splitlines():
        match = ROW.match(line)
        if match is None:
            continue
        task_id, first_cell = match.group(1), match.group(2).strip()
        if not task_id.isdigit() or int(task_id) > 119:
            continue
        # Resolve the (possibly truncated) domain cell; longest prefix wins.
        candidates = [
            prefix for prefix in PREFIX_TO_CANONICAL if first_cell == prefix or first_cell.startswith(prefix)
        ]
        if not candidates:
            continue
        domain = PREFIX_TO_CANONICAL[max(candidates, key=len)]
        # A task ID appears once in Table 5; later rows for the same ID would be a bug.
        if task_id in mapping and mapping[task_id] != domain:
            raise SystemExit(f"conflicting domain for task {task_id}: {mapping[task_id]} vs {domain}")
        mapping[task_id] = domain

    return mapping


def main() -> int:
    mapping = extract()
    counts = Counter(mapping.values())

    problems: list[str] = []
    if len(mapping) != 119:
        problems.append(f"expected 119 tasks, extracted {len(mapping)}")
    for domain, expected in CANONICAL_COUNTS.items():
        if counts.get(domain, 0) != expected:
            problems.append(f"{domain}: expected {expected}, extracted {counts.get(domain, 0)}")
    unexpected = set(counts) - set(CANONICAL_COUNTS)
    if unexpected:
        problems.append(f"unexpected domains: {sorted(unexpected)}")

    if problems:
        print("EXTRACTION VALIDATION FAILED:", file=sys.stderr)
        for problem in problems:
            print(" -", problem, file=sys.stderr)
        return 1

    receipt = {
        "kind": "swe-bench-science-task-domain-mapping",
        "source": "arXiv:2608.19799v2 Appendix Table 5 (task-level inventory)",
        "pdf_sha256": hashlib.sha256(PDF.read_bytes()).hexdigest(),
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "validation": "per-domain counts reproduce Appendix Table 4 exactly over 119 tasks",
        "canonical_counts": CANONICAL_COUNTS,
        "tasks": {task: {"domain": domain} for task, domain in sorted(mapping.items())},
        "domain_counts": dict(sorted(counts.items())),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(receipt, indent=1) + "\n")
    print(f"Wrote {OUT.relative_to(REPO)} with {len(mapping)} tasks across {len(counts)} domains")
    for domain, count in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
        print(f"  {count:3d}  {domain}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
