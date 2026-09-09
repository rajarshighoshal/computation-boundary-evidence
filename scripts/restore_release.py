#!/usr/bin/env python3
"""Restore only explicit unrestricted development selections by default."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from scicontext.release import prepare

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--workspace", type=Path, default=Path.cwd())
parser.add_argument("--task-id", default="002,077")
parser.add_argument("--allow-restricted-licenses", action="store_true")
args = parser.parse_args()
print(json.dumps(prepare(args.workspace, args.task_id.split(","), allow_restricted=args.allow_restricted_licenses), indent=2))
