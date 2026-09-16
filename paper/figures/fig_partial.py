"""Partial credit: how far each attempt got on the private test suite.

Binary solve parity hides grading detail. These panels show the per-attempt
private-test pass fraction for both arms on the held-out partition, and the
relation between partial credit and the binary outcome.

Reads verifier receipts through the shared attempts() loader.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

sys.path.insert(0, str(Path(__file__).resolve().parent))
from plotting import LOCKED_RUNS, RC, attempts, locked_receipt, save, scene  # noqa: E402
from theme import BLUE, GRID, INK_SOFT, LIGHT_BLUE, LIGHT_TEAL, TEAL  # noqa: E402

BINS = [index / 20 for index in range(21)]


def fractions(data: dict[str, Any], arm: str) -> list[float]:
    out = []
    for task in sorted(data):
        for record in data[task].get(arm, []):
            if record["reward"] is None or not record["private_collected"]:
                continue
            out.append(record["private_passed"] / record["private_collected"])
    return out


def panel_hist(ax: Any, data: dict[str, Any], letter: str, title: str) -> None:
    for arm, colour in (("baseline", BLUE), ("science", TEAL)):
        samples = fractions(data, arm)
        ax.hist(samples, bins=BINS, color=colour, alpha=0.45, zorder=2, edgecolor="white",
                linewidth=0.3, label=f"{arm} arm (n={len(samples)})")
        mean = sum(samples) / len(samples)
        ax.plot([mean], [ax.get_ylim()[1] * 0.9], marker="v", ms=5, color=colour, zorder=4)
    for index, (arm, colour) in enumerate((("baseline", BLUE), ("science", TEAL))):
        mean = sum(fractions(data, arm)) / len(fractions(data, arm))
        ax.text(0.03, 0.96 - index * 0.09, f"{arm} mean {mean * 100:.1f}%", transform=ax.transAxes,
                fontsize=6.6, color=colour, fontweight="bold", va="top")
    ax.set_xticks([0, 0.25, 0.5, 0.75, 1.0])
    ax.set_xticklabels(["0", "25", "50", "75", "100"])
    ax.set_xlabel("private tests passed per attempt (%)", fontsize=7.4)
    ax.set_ylabel("attempts", fontsize=7.4)
    ax.grid(axis="y", color=GRID, lw=0.45, zorder=0)
    ax.set_axisbelow(True)
    ax.tick_params(labelsize=7.2, length=2.5)
    ax.spines["bottom"].set_color(INK_SOFT)
    ax.spines["left"].set_visible(False)
    scene(ax, letter, title)


def panel_by_outcome(ax: Any, data: dict[str, Any], letter: str, title: str) -> None:
    groups = [("solved", True, 0), ("unsolved", False, 1)]
    width = 0.34
    for arm, colour, offset, alpha in (("baseline", BLUE, -width / 2, 0.45),
                                       ("science", TEAL, width / 2, 0.85)):
        means = []
        for _, solved, _ in groups:
            samples = [record["private_passed"] / record["private_collected"]
                       for task in data for record in data[task].get(arm, [])
                       if record["reward"] is not None and record["private_collected"]
                       and bool(record["reward"]) is solved]
            means.append(sum(samples) / len(samples) * 100 if samples else 0.0)
        ax.bar([index + offset for _, _, index in groups], means, width=width, color=colour,
               alpha=alpha, edgecolor="white", linewidth=0.5, zorder=2,
               label=f"{arm} arm")
        for (_, _, index), mean in zip(groups, means):
            ax.text(index + offset, mean + 1.6, f"{mean:.0f}", ha="center", va="bottom",
                    fontsize=6.6, color=colour, fontweight="bold")
    ax.set_xticks([index for _, _, index in groups])
    ax.set_xticklabels(["verifier solved", "verifier failed"], fontsize=7.0)
    ax.set_ylabel("private tests passed (%)", fontsize=7.4)
    ax.set_ylim(0, 112)
    ax.grid(axis="y", color=GRID, lw=0.45, zorder=0)
    ax.set_axisbelow(True)
    ax.tick_params(axis="y", labelsize=7.2, length=0)
    ax.tick_params(axis="x", length=0)
    ax.spines["bottom"].set_visible(False)
    ax.spines["left"].set_visible(False)
    ax.legend(fontsize=6.4, loc="upper center", ncol=2, handletextpad=0.4, columnspacing=0.8)
    scene(ax, letter, title)


def main() -> None:
    data = attempts(LOCKED_RUNS)
    receipt = locked_receipt()
    baseline_rate = receipt["totals"]["baseline"]["graded_test_rate"] * 100
    science_rate = receipt["totals"]["science"]["graded_test_rate"] * 100
    print(f"  pooled graded test rate: baseline {baseline_rate:.1f}% vs science {science_rate:.1f}%")

    with plt.rc_context(RC):
        fig, axes = plt.subplots(1, 2, figsize=(6.0, 2.5),
                                 gridspec_kw={"width_ratios": [1.25, 1.0], "wspace": 0.42})
        panel_hist(axes[0], data, "A", "Grading distribution, 522 attempts")
        panel_by_outcome(axes[1], data, "B", "Partial credit vs outcome")
        handles = [
            Line2D([0], [0], color=BLUE, lw=3, alpha=0.5, label="baseline arm"),
            Line2D([0], [0], color=TEAL, lw=3, alpha=0.8, label="science arm"),
            Line2D([0], [0], color=LIGHT_BLUE, lw=3, label="baseline (light)"),
            Line2D([0], [0], color=LIGHT_TEAL, lw=3, label="science (light)"),
        ]
        del handles
        fig.subplots_adjust(left=0.085, right=0.985, top=0.82, bottom=0.17)
        save(fig, "fig_partial")


if __name__ == "__main__":
    main()
