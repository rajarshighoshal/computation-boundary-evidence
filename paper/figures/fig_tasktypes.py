"""Task-type stratification: language families and the knowledge-ablation split.

Same dumbbell grammar as the domain figure, read from the same receipt.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

sys.path.insert(0, str(Path(__file__).resolve().parent))
from plotting import (  # noqa: E402
    RC, domain_receipt, dotted_grid, save, scene, wilson,
)
from theme import BLUE, RUST, TEAL  # noqa: E402

RATE_MAX = 0.80
DATA_FRAC = 0.62

LANGUAGE_LABELS = {
    "python": "Python only",
    "python-cpp": "Python + C++",
    "python-c": "Python + C",
    "python-cython": "Python + Cython",
    "c": "C",
    "c++": "C++",
    "c-python": "C + Python",
    "fortran": "Fortran",
    "matlab-octave": "MATLAB/Octave",
}
ABLATION_LABELS = {
    "knowledge-ablated": "knowledge ablated",
    "knowledge-provided": "knowledge provided",
}


def panel(ax: Any, groups: dict[str, Any], order: list[str], labels: dict[str, str],
          letter: str, title: str, *, min_tasks: int) -> None:
    rows = []
    for key in order:
        row = groups.get(key)
        if row is None or row["n_tasks"] < min_tasks:
            continue
        rows.append((labels.get(key, key), row["baseline"], row["science"], row["n_tasks"]))
    rows.sort(key=lambda r: r[2]["rate"] - r[1]["rate"])

    ys = list(range(len(rows)))
    ax.set_yticks(ys)
    ax.set_yticklabels([f"{name} ({n})" for name, _, _, n in rows], fontsize=7.2)

    for x in (0.0, 0.2, 0.4, 0.6, 0.8):
        ax.plot([x / RATE_MAX * DATA_FRAC] * 2, [0.0, 1.0], transform=ax.transAxes,
                color="#D9D9D9", lw=0.45, zorder=0)
    ax.plot([0.66, 0.66], [0.0, 1.0], transform=ax.transAxes, color="#D9D9D9", lw=0.6)

    for y, (_, base, sci, _) in zip(ys, rows):
        delta = (sci["rate"] - base["rate"]) * 100
        colour = TEAL if delta > 0 else (RUST if delta < 0 else "#555555")
        ax.plot([base["rate"], sci["rate"]], [y, y], color=colour, lw=1.4, alpha=0.5, zorder=2)
        ax.plot([base["rate"]], [y], marker="o", ms=3.4, color=BLUE, zorder=3,
                markeredgecolor="white", markeredgewidth=0.5, ls="none")
        ax.plot([sci["rate"]], [y], marker="s", ms=3.4, color=colour, zorder=3,
                markeredgecolor="white", markeredgewidth=0.5, ls="none")
        lo, hi = wilson(sci["solved"], sci["verified"])
        ax.plot([lo, hi], [y, y], color=colour, lw=0.7, alpha=0.5, zorder=1)
        ax.text(0.68, y, f"{delta:+.1f}", fontsize=7.0, va="center", ha="left",
                color=colour, fontweight="bold", transform=ax.get_yaxis_transform())

    ax.set_xlim(0.0, RATE_MAX / DATA_FRAC)
    ax.set_ylim(-0.8, len(rows) - 0.2)
    ax.set_xticks([0.0, 0.2, 0.4, 0.6, 0.8])
    ax.set_xticklabels(["0", "20", "40", "60", "80"])
    ax.set_xlabel("official verifier solve rate per attempt (%)", fontsize=7.4)
    ax.text(0.68, len(rows) - 0.55, "$\\Delta$ pp", fontsize=7.2, color="#555555",
            fontweight="bold", transform=ax.get_yaxis_transform())
    ax.tick_params(axis="x", labelsize=7.2)
    dotted_grid(ax)
    scene(ax, letter, title)


def main() -> None:
    payload = domain_receipt()
    locked = payload["partitions"]["locked89_k3"]

    with plt.rc_context(RC):
        fig, axes = plt.subplots(1, 2, figsize=(7.0, 2.9),
                                 gridspec_kw={"width_ratios": [1.0, 0.72], "wspace": 0.52})
        panel(axes[0], locked["by_language"]["groups"],
              ["python", "c", "c++", "c-python", "python-c", "python-cpp", "python-cython",
               "fortran", "matlab-octave"],
              LANGUAGE_LABELS, "A", "Language families (locked-89, $k=3$)", min_tasks=1)
        panel(axes[1], locked["by_ablation"]["groups"],
              ["knowledge-ablated", "knowledge-provided"],
              ABLATION_LABELS, "B", "Knowledge-ablation split", min_tasks=1)

        handles = [
            Line2D([0], [0], marker="o", ms=3.4, ls="none", color=BLUE, markeredgecolor="white",
                   markeredgewidth=0.5, label="baseline arm"),
            Line2D([0], [0], marker="s", ms=3.4, ls="none", color=TEAL, markeredgecolor="white",
                   markeredgewidth=0.5, label="science arm, gain"),
            Line2D([0], [0], marker="s", ms=3.4, ls="none", color=RUST, markeredgecolor="white",
                   markeredgewidth=0.5, label="science arm, loss"),
        ]
        fig.legend(handles=handles, loc="upper center", ncol=3, frameon=False, fontsize=7.2,
                   bbox_to_anchor=(0.5, 1.10), handletextpad=0.4, columnspacing=1.2)
        fig.subplots_adjust(left=0.155, right=0.99, top=0.845, bottom=0.135)
        save(fig, "fig_tasktypes")


if __name__ == "__main__":
    main()
