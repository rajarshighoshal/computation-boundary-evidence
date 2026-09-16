"""Shared visual theme and styling primitives for scientific paper figures.

Ensures consistent palettes, typography, spines, margins, and output formats
across all figures embedded in the LaTeX report.
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from matplotlib.figure import Figure
import matplotlib.pyplot as plt

# Column widths in inches for two-column article (margin=0.72in, colsep=0.22in on 8.5in page)
COL_WIDTH: float = 3.40
FULL_WIDTH: float = 7.06

# Colorblind-safe palette (Tol-muted inspired)
# Baseline: neutral slate; Science: vibrant teal
COLOR_BASELINE: str = "#4C72B0"
COLOR_SCIENCE: str = "#2B9C82"
COLOR_NEUTRAL: str = "#7F7F7F"
COLOR_ACCENT: str = "#C44E52"

# Paradigm palette
COLOR_ISSUE: str = "#2B5C8F"        # Deep blue
COLOR_EXPLORE: str = "#D97724"      # Rust amber
COLOR_INTEGRATE: str = "#2E7D32"    # Forest green

# Stability categories
COLOR_SOLVED_BOTH: str = "#2B9C82"
COLOR_UNSOLVED: str = "#7F7F7F"
COLOR_FLIP: str = "#D97724"

FIG_DIR: Path = Path(__file__).parent / "out"


def apply_theme() -> None:
    """Configure matplotlib rcParams to match LaTeX document typography."""
    plt.rcParams.update({
        # Typography: serif to match Latin Modern / Computer Modern
        "font.family": "serif",
        "font.serif": ["DejaVu Serif", "Times New Roman", "Computer Modern Roman"],
        "mathtext.fontset": "dejavuserif",
        "font.size": 8.0,
        "axes.titlesize": 8.5,
        "axes.titleweight": "bold",
        "axes.labelsize": 8.0,
        "xtick.labelsize": 7.0,
        "ytick.labelsize": 7.0,
        "legend.fontsize": 7.0,
        "legend.title_fontsize": 7.5,
        "figure.titlesize": 9.0,
        # Spines and grid
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.spines.left": True,
        "axes.spines.bottom": True,
        "axes.linewidth": 0.6,
        "axes.edgecolor": "#333333",
        "axes.grid": True,
        "axes.grid.axis": "y",
        "grid.color": "#E5E5E5",
        "grid.linestyle": ":",
        "grid.linewidth": 0.5,
        "grid.alpha": 0.8,
        # Ticks
        "xtick.direction": "out",
        "ytick.direction": "out",
        "xtick.major.size": 2.5,
        "ytick.major.size": 2.5,
        "xtick.major.width": 0.6,
        "ytick.major.width": 0.6,
        # Legend
        "legend.frameon": True,
        "legend.framealpha": 0.95,
        "legend.edgecolor": "#D0D0D0",
        "legend.fancybox": False,
        # Vector output: Type 42 (TrueType) fonts for clean PDF embedding
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "figure.autolayout": False,
    })


def new_figure(
    cols: int = 1,
    height: float = 2.4,
    sharey: bool = False,
    sharex: bool = False,
    nrows: int = 1,
    ncols: int = 1,
    gridspec_kw: dict[str, Any] | None = None,
) -> tuple[Figure, Any]:
    """Create a new figure sized to document column widths."""
    apply_theme()
    width = COL_WIDTH if cols == 1 else FULL_WIDTH
    fig, axes = plt.subplots(
        nrows,
        ncols,
        figsize=(width, height),
        sharey=sharey,
        sharex=sharex,
        gridspec_kw=gridspec_kw,
    )
    return fig, axes


def save_figure(fig: Figure, stem: str) -> tuple[Path, Path]:
    """Save figure as both PDF (for LaTeX embedding) and PNG (for preview)."""
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    pdf_path = FIG_DIR / f"{stem}.pdf"
    png_path = FIG_DIR / f"{stem}.png"
    fig.savefig(pdf_path, bbox_inches="tight", pad_inches=0.04, dpi=300)
    fig.savefig(png_path, bbox_inches="tight", pad_inches=0.04, dpi=300)
    plt.close(fig)
    return pdf_path, png_path


def wilson_ci(k: int, n: int) -> tuple[float, float]:
    """Compute 95% Wilson score interval for a binomial proportion."""
    if n == 0:
        return (0.0, 0.0)
    z = 1.95996  # 95% confidence
    p = k / n
    denom = 1.0 + (z**2) / n
    center = (p + (z**2) / (2 * n)) / denom
    spread = (z / denom) * math.sqrt((p * (1 - p) / n) + (z**2) / (4 * (n**2)))
    return max(0.0, center - spread), min(1.0, center + spread)
