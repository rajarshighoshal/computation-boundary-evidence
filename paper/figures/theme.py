"""Visual contract for every figure in the report.

Mirrors the plot language used in the author's ICLR submission
(``lie-geometry-probes/experiments/iclr2027_paper_theme.py``): STIX serif type,
semantic colours, redundant shape/colour encoding, left-anchored panel titles,
and no chart junk. Every figure script imports this module; no figure defines
its own colours or fonts.
"""

from __future__ import annotations

FIGURE_WIDTH = 5.5  # inches; the report text block is 6.5 in wide

# Semantic palette. Marks carry colour plus a redundant positional/shape cue.
BLUE = "#2468A0"
ORANGE = "#C36547"
GRAY = "#6E6E6E"
TEAL = "#408F83"
RUST = "#B5523A"
INK = "#171717"
INK_SOFT = "#555555"
GRID = "#D9D9D9"
WHITE = "#FFFFFF"

LIGHT_BLUE = "#EAF4FA"
LIGHT_ORANGE = "#FBEEE8"
LIGHT_GRAY = "#F3F3F3"
LIGHT_TEAL = "#EAF6F4"

RC = {
    "font.family": "serif",
    "font.serif": ["STIXGeneral", "DejaVu Serif"],
    "mathtext.fontset": "stix",
    "font.size": 8.0,
    "text.color": INK,
    "figure.facecolor": WHITE,
    "savefig.facecolor": WHITE,
    "axes.facecolor": WHITE,
    "axes.edgecolor": INK_SOFT,
    "axes.linewidth": 0.55,
    "axes.labelsize": 8.0,
    "axes.labelcolor": INK,
    "axes.titlesize": 8.5,
    "axes.titleweight": "semibold",
    "axes.titlelocation": "left",
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.axisbelow": True,
    "grid.color": GRID,
    "grid.linewidth": 0.45,
    "grid.linestyle": "-",
    "xtick.labelsize": 7.5,
    "ytick.labelsize": 7.5,
    "xtick.color": INK_SOFT,
    "ytick.color": INK_SOFT,
    "xtick.major.size": 2.5,
    "ytick.major.size": 0,
    "legend.frameon": False,
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
}

__all__ = [
    "BLUE",
    "FIGURE_WIDTH",
    "GRAY",
    "GRID",
    "INK",
    "INK_SOFT",
    "LIGHT_BLUE",
    "LIGHT_GRAY",
    "LIGHT_ORANGE",
    "LIGHT_TEAL",
    "ORANGE",
    "RC",
    "RUST",
    "TEAL",
    "WHITE",
]
