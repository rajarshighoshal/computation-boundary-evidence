"""Reasoning-effort matrix: what changes when test-time deliberation shrinks.

Panel A  dev-30 solve rates for the four effort x arm cells (30 tasks each)
Panel B  matched 20-task subset where both effort levels were evaluated
Panel C  per-attempt output tokens in each cell, i.e. what the effort knob did

Reads results/complete-30-task-2x2-matrix.json and
results/deepseek-2x2-matched-evaluation.json (both frozen receipts).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parent))

CLAIM = (
    "Reduced reasoning effort recovers exactly the tasks the evidence arm lost at high effort."
)
from plotting import RC, attempts, load_json, save, scene  # noqa: E402
from theme import BLUE, GRID, INK_SOFT, TEAL  # noqa: E402

CELLS = (("high_effort", "baseline", BLUE, "o"), ("high_effort", "science", TEAL, "s"),
         ("low_effort", "baseline", BLUE, "o"), ("low_effort", "science", TEAL, "s"))


def parse_fraction(text: str) -> tuple[int, int]:
    counts = text.split("(")[0].strip()
    solved, total = counts.split("/")
    return int(solved), int(total)


def panel_matrix(ax: Any, receipt: dict[str, Any], letter: str, title: str) -> None:
    positions = [0, 1, 2, 3]
    for x, (effort, arm, colour, _marker) in zip(positions, CELLS):
        solved, total = parse_fraction(receipt["matrix_results"][effort][arm])
        rate = solved / total * 100
        ax.bar([x], [rate], width=0.62, color=colour, alpha=0.85, edgecolor="white",
               linewidth=0.5, zorder=2)
        ax.text(x, rate + 1.2, f"{solved}/{total}", ha="center", va="bottom", fontsize=6.6,
                color=colour, fontweight="bold")
    ax.text(0.5, 51.0, "high effort", fontsize=7.0, color=INK_SOFT, ha="center", va="bottom")
    ax.text(2.5, 51.0, "low effort", fontsize=7.0, color=INK_SOFT, ha="center", va="bottom")
    ax.set_xlim(-0.6, 3.6)
    ax.set_ylim(0, 56)
    ax.set_xticks(positions)
    ax.set_xticklabels(["high\nbase", "high\nCBE", "low\nbase", "low\nCBE"], fontsize=6.4)
    ax.set_ylabel("tasks solved (% of 30)", fontsize=7.4)
    ax.grid(axis="y", color=GRID, lw=0.45, zorder=0)
    ax.set_axisbelow(True)
    ax.tick_params(axis="y", labelsize=7.2, length=0)
    ax.tick_params(axis="x", length=0)
    ax.spines["bottom"].set_visible(False)
    ax.spines["left"].set_visible(False)
    scene(ax, letter, title)


def panel_matched(ax: Any, receipt: dict[str, Any], letter: str, title: str) -> None:
    positions = [0, 1, 2, 3]
    for x, (effort, arm, colour, _marker) in zip(positions, CELLS):
        solved, total = parse_fraction(receipt["matrix_success_rates"][effort][arm])
        rate = solved / total * 100
        ax.bar([x], [rate], width=0.62, color=colour, alpha=0.85, edgecolor="white",
               linewidth=0.5, zorder=2)
        ax.text(x, rate + 1.2, f"{solved}/{total}", ha="center", va="bottom", fontsize=6.6,
                color=colour, fontweight="bold")
    ax.text(0.5, 56.5, "matched 20 tasks", fontsize=7.0, color=INK_SOFT, ha="center", va="bottom")
    ax.set_xlim(-0.6, 3.6)
    ax.set_ylim(0, 62)
    ax.set_xticks(positions)
    ax.set_xticklabels(["base", "CBE", "base", "CBE"], fontsize=6.8)
    ax.set_ylabel("tasks solved (% of 20)", fontsize=7.4)
    ax.grid(axis="y", color=GRID, lw=0.45, zorder=0)
    ax.set_axisbelow(True)
    ax.tick_params(axis="y", labelsize=7.2, length=0)
    ax.tick_params(axis="x", length=0)
    ax.spines["bottom"].set_visible(False)
    ax.spines["left"].set_visible(False)
    scene(ax, letter, title)


def mean_output_tokens(data: dict[str, Any], arm: str) -> float:
    samples = [float(record["out"]) for task in data for record in data[task].get(arm, [])
               if record["reward"] is not None]
    return sum(samples) / len(samples) if samples else 0.0


def panel_effort_tokens(ax: Any, means_k: list[float], letter: str, title: str) -> None:
    xs = [0, 1, 2, 3]
    means = means_k
    colours = [BLUE, TEAL, BLUE, TEAL]
    ax.bar(xs, means, width=0.62, color=colours, alpha=0.85, edgecolor="white", linewidth=0.5,
           zorder=2)
    for x, mean in zip(xs, means):
        ax.text(x, mean + 0.8, f"{mean:.0f}k", ha="center", va="bottom", fontsize=6.6,
                color=colours[x], fontweight="bold")
    ax.set_xticks(xs)
    ax.set_xticklabels(["high\nbase", "high\nCBE", "low\nbase", "low\nCBE"], fontsize=6.4)
    ax.set_ylabel("mean output tokens per attempt (k)", fontsize=7.4)
    ax.set_ylim(0, max(means) * 1.25)
    ax.grid(axis="y", color=GRID, lw=0.45, zorder=0)
    ax.set_axisbelow(True)
    ax.tick_params(axis="y", labelsize=7.2, length=0)
    ax.tick_params(axis="x", length=0)
    ax.spines["bottom"].set_visible(False)
    ax.spines["left"].set_visible(False)
    scene(ax, letter, title)


def main() -> None:
    full = load_json("results/complete-30-task-2x2-matrix.json")
    matched = load_json("results/deepseek-2x2-matched-evaluation.json")
    del matched  # the matched subset is reported in the table, not here

    high = attempts(["deepseek-development-e2e-40-v1"])
    low = attempts(["deepseek-development-e2e-40-low-v1", "deepseek-development-e2e-tail-10-low-v1"])
    means_k = [mean_output_tokens(high, "baseline") / 1000, mean_output_tokens(high, "science") / 1000,
               mean_output_tokens(low, "baseline") / 1000, mean_output_tokens(low, "science") / 1000]

    with plt.rc_context(RC):
        fig, axes = plt.subplots(1, 2, figsize=(5.5, 2.5),
                                 gridspec_kw={"wspace": 0.45})
        panel_matrix(axes[0], full, "A", "Dev-30, four cells")
        panel_effort_tokens(axes[1], means_k, "B", "Tokens per attempt")
        fig.subplots_adjust(left=0.075, right=0.99, top=0.80, bottom=0.16)
        save(fig, "fig_effort", claim=CLAIM)


if __name__ == "__main__":
    main()
