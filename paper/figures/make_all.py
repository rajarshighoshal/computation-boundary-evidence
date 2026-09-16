"""Render every candidate figure from the frozen receipts.

Usage: PYTHONPATH=. .venv/bin/python paper/figures/make_all.py [module ...]

Each module reads only frozen receipts and asserts its own layout before writing
into paper/figures/out.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

MODULES = [
    "fig_parity",
    "fig_grounding_flow",
    "fig_domains",
    "fig_tasktypes",
    "fig_stability",
    "fig_resources",
    "fig_effort",
    "fig_representation",
    "fig_partial",
]


def main() -> None:
    names = sys.argv[1:] or MODULES
    for name in names:
        print(f"[{name}]")
        module = importlib.import_module(name)
        module.main()
    print(f"\n{len(names)} figure set(s) written to {(HERE / 'out').relative_to(HERE.parent.parent)}")


if __name__ == "__main__":
    main()
