"""Shared helpers for every figure in the report.

All figures read frozen receipts; no figure invents numbers. Each renderer calls
``save`` which asserts the layout before writing (no text leaves the canvas, no
two text artists overlap) so exported PDFs cannot silently overflow.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.transforms as transforms
from matplotlib.figure import Figure

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from theme import GRID, INK, INK_SOFT, RC  # noqa: E402

REPO = HERE.parent.parent
OUT = HERE / "out"
RUNS = REPO / "runs"
RESULTS = REPO / "results"

LOCKED_RUNS = [
    "deepseek-locked89-k1-v2",
    "deepseek-locked89-k2-v2",
    "deepseek-locked89-k3-clean-v1",
]
DEV_RUNS = [
    "deepseek-development-e2e-40-v1",
    "deepseek-development-e2e-40-low-v1",
    "deepseek-development-e2e-tail-10-low-v1",
    "deepseek-dev30-contracts-low-v1",
    "deepseek-dev30-v3",
]

Z95 = 1.959963984540054


def load_json(path: Path | str) -> Any:
    return json.loads((REPO / path if not Path(path).is_absolute() else Path(path)).read_text())


def locked_receipt() -> dict[str, Any]:
    return load_json(RESULTS / "locked89-k3-clean-analysis.json")


def domain_receipt() -> dict[str, Any]:
    return load_json(RESULTS / "domain-arm-analysis.json")


def attempts(run_names: list[str]) -> dict[str, dict[str, list[dict[str, Any]]]]:
    """task -> arm -> per-attempt records (reward, tokens, seconds, private tests)."""
    sys.path.insert(0, str(REPO / "scripts"))
    from analyze_locked_k3 import load_runs

    return load_runs([RUNS / name for name in run_names])


def wilson(solved: int, verified: int) -> tuple[float, float]:
    if verified == 0:
        return (0.0, 0.0)
    phat = solved / verified
    denom = 1 + Z95**2 / verified
    center = (phat + Z95**2 / (2 * verified)) / denom
    spread = (Z95 / denom) * math.sqrt(phat * (1 - phat) / verified + Z95**2 / (4 * verified**2))
    return (max(0.0, center - spread), min(1.0, center + spread))


def scene(ax: Any, letter: str, title: str, *, x: float = 0.0, y: float = 1.02) -> None:
    """Panel letter above a left-anchored title; offset in points so it holds at any panel size."""
    ax.text(x, y, title, transform=ax.transAxes, ha="left", va="bottom",
            fontsize=8.0, fontweight="bold", color=INK)
    lifted = transforms.offset_copy(ax.transAxes, fig=ax.figure, x=0, y=9, units="points")
    ax.text(x, y, letter, transform=lifted, ha="left", va="bottom",
            fontsize=8.6, fontweight="bold", color=INK)


def assert_layout(fig: Figure) -> None:
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    canvas = fig.bbox
    problems: list[str] = []
    for ax in fig.axes:
        texts = [t for t in ax.texts if t.get_visible() and t.get_text().strip()]
        if ax.axison:
            texts += [t for t in ax.get_yticklabels() + ax.get_xticklabels()
                      if t.get_visible() and t.get_text().strip()]
        boxes = [(t.get_text().strip(), t.get_window_extent(renderer)) for t in texts]
        for text, box in boxes:
            if (box.x0 < canvas.x0 - 0.5 or box.x1 > canvas.x1 + 0.5
                    or box.y0 < canvas.y0 - 0.5 or box.y1 > canvas.y1 + 0.5):
                problems.append(f"outside canvas: {text!r}")
        for index, (text_a, box_a) in enumerate(boxes):
            for text_b, box_b in boxes[index + 1:]:
                if box_a.overlaps(box_b):
                    problems.append(f"text overlap: {text_a!r} vs {text_b!r}")
    for text in fig.texts:
        if not text.get_visible() or not text.get_text().strip():
            continue
        box = text.get_window_extent(renderer)
        if box.x0 < canvas.x0 - 0.5 or box.x1 > canvas.x1 + 0.5:
            problems.append(f"outside canvas (figure text): {text.get_text()!r}")
    if problems:
        raise SystemExit("figure layout problems:\n  " + "\n  ".join(problems))


def save(fig: Figure, name: str, *, dpi: int = 300, claim: str = "") -> None:
    import requirements

    assert_layout(fig)
    problems = requirements.check(fig, name, claim)
    if problems:
        raise SystemExit(f"{name} fails figure requirements:\n  " + "\n  ".join(problems))
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / f"{name}.pdf", format="pdf")
    fig.savefig(OUT / f"{name}.png", format="png", dpi=dpi)
    plt.close(fig)
    print(f"  saved {name}.pdf")


def dotted_grid(ax: Any, *, axis: str = "x", frac: float = 1.0) -> None:
    ax.grid(axis=axis, color=GRID, lw=0.45, ls="-", zorder=0)
    ax.grid(axis=axis, color="none")
    del frac
    ax.set_axisbelow(True)
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_visible(False)
    ax.spines["bottom"].set_color(INK_SOFT)


__all__ = [
    "OUT",
    "REPO",
    "RESULTS",
    "RUNS",
    "LOCKED_RUNS",
    "DEV_RUNS",
    "RC",
    "assert_layout",
    "attempts",
    "dotted_grid",
    "domain_receipt",
    "load_json",
    "locked_receipt",
    "save",
    "scene",
    "wilson",
]
