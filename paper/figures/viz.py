"""Shared visual language for every figure in the report.

Inspired by the plot style of the author's earlier manuscript (STIX serif type, semantic
colour, redundant shape encoding, left-anchored panel titles, no chart junk) but rebuilt for
this paper's data. Nothing here draws a confidence interval: at these sample sizes the honest
annotation is the absolute count.

Rules
-----
- Baseline arm is always a circle in BLUE; the CBE arm is always a square, TEAL on a gain and
  RUST on a loss. Shape and colour both carry the encoding.
- Panels are labelled with a bold letter above a bold left-aligned title.
- Values are annotated as counts (``8/44 -> 12/43``), never as bare percentages.
- Gridlines are horizontal hairlines only; top and right spines are removed.
"""

from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from theme import BLUE, GRID, INK, INK_SOFT, RUST, TEAL, TIE

BASELINE_MARKER = "o"
CBE_MARKER = "s"

COLOUR = {
    "baseline": BLUE,
    "gain": TEAL,
    "loss": RUST,
    "tie": INK_SOFT,   # readable neutral for parity rows and their text
    "line": TIE,       # pale neutral, connector lines only
}

__all__ = [
    "BASELINE_MARKER",
    "CBE_MARKER",
    "COLOUR",
    "Blue",
    "bar_pair",
    "bottom_row",
    "baseline_axis",
    "count_label",
    "dot",
    "figure",
    "hairline",
    "panel",
    "row_grid",
]

Blue = BLUE


def figure(width: float = 5.5, height: float = 2.5, **kwargs):
    """A figure on the shared canvas; 5.5in designs print at 6.5in with 1.18x type."""
    return plt.figure(figsize=(width, height), **kwargs)


def panel(ax, letter: str, title: str, *, y: float = 1.02) -> None:
    """Bold letter above a bold, left-anchored title."""
    import matplotlib.transforms as transforms

    ax.text(0.0, y, title, transform=ax.transAxes, ha="left", va="bottom",
            fontsize=8.4, fontweight="bold", color=INK)
    lifted = transforms.offset_copy(ax.transAxes, fig=ax.figure, x=0, y=9, units="points")
    ax.text(0.0, y, letter, transform=lifted, ha="left", va="bottom",
            fontsize=8.6, fontweight="bold", color=INK)


def dot(ax, x: float, y: float, kind: str, *, size: float = 3.6, zorder: int = 3) -> None:
    """Baseline circle or CBE square, coloured by outcome kind."""
    marker = BASELINE_MARKER if kind == "baseline" else CBE_MARKER
    ax.plot([x], [y], marker=marker, ms=size, ls="none", color=COLOUR[kind], zorder=zorder,
            markeredgecolor="white", markeredgewidth=0.5)


def count_label(ax, x: float, y: float, text: str, kind: str = "tie", *,
                ha: str = "left", size: float = 7.0) -> None:
    ax.text(x, y, text, fontsize=size, color=COLOUR[kind], ha=ha, va="center", fontweight="bold")


def arrow(ax, start: tuple[float, float], end: tuple[float, float], kind: str) -> None:
    ax.annotate("", xy=end, xytext=start,
                arrowprops={"arrowstyle": "-|>", "color": COLOUR[kind], "lw": 1.1,
                            "shrinkA": 0, "shrinkB": 0},
                zorder=2)


def hairline(ax, x: float) -> None:
    ax.axvline(x, color=GRID, lw=0.6, zorder=1)


def row_grid(ax, values: list[float]) -> None:
    for value in values:
        ax.axhline(value, color=GRID, lw=0.45, zorder=0)


def baseline_axis(ax) -> None:
    """House furniture: hairline gridlines, no left spine, ticks shortened."""
    ax.set_axisbelow(True)
    ax.tick_params(axis="y", length=0)
    ax.tick_params(axis="x", length=2.2)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(False)
    ax.spines["bottom"].set_color(INK_SOFT)


def bar_pair(ax, x: float, baseline: float, cbe: float, *, width: float = 0.62) -> None:
    """Two adjacent bars: baseline in BLUE, CBE coloured by direction."""
    kind = "gain" if cbe >= baseline else "loss"
    ax.bar([x - width / 2], [baseline], width=width, color=BLUE, edgecolor="white", linewidth=0.5,
           zorder=2)
    ax.bar([x + width / 2], [cbe], width=width, color=COLOUR[kind], edgecolor="white", linewidth=0.5,
           zorder=2)


def bottom_row(ax, ys: list[int]) -> None:
    del ax, ys
