"""Replication structure: how often a task moves between identical runs.

Panel A  tasks by number of replicate runs that solved them, per arm
Panel B  pass@k: share of tasks solved by at least one of k pooled runs, per arm

No intervals are drawn; the replicate counts themselves are the uncertainty statement.
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parent))
from plotting import LOCKED_RUNS, RC, attempts, save
from theme import GRID, INK_SOFT
import viz

CLAIM = ("Most held-out tasks are solved by neither arm or by every replicate; about a fifth flip "
         "between identical runs, which is the resolution limit of a single-run comparison.")

PANELS = (("baseline", "baseline", viz.COLOUR["baseline"]),
          ("science", "CBE", viz.COLOUR["gain"]))
WIDTH = 0.34


def solve_counts(data: dict[str, Any], arm: str) -> list[int]:
    counts = []
    for task in sorted(data):
        rewards = [int(r["reward"]) for r in data[task].get(arm, []) if r["reward"] is not None]
        counts.append(sum(rewards))
    return counts


def pass_at_k(data: dict[str, Any], arm: str, k: int) -> float:
    solved = total = 0
    for task in sorted(data):
        rewards = [r["reward"] for r in data[task].get(arm, [])][:k]
        verified = [int(r) for r in rewards if r is not None]
        if not verified:
            continue
        total += 1
        solved += any(verified)
    return solved / total if total else 0.0


def panel_counts(ax: Any, data: dict[str, Any], replicates: int) -> Counter:
    for index, (arm, label, colour) in enumerate(PANELS):
        offset = (index - 0.5) * WIDTH
        counter = Counter(solve_counts(data, arm))
        xs = list(range(replicates + 1))
        ax.bar([x + offset for x in xs], [counter.get(x, 0) for x in xs], width=WIDTH,
               color=colour, edgecolor="white", linewidth=0.5, zorder=2)
        for x in xs:
            value = counter.get(x, 0)
            if not value:
                continue
            ax.text(x + offset, value + 1.6, str(value), ha="center", va="bottom", fontsize=6.6,
                    color=colour, fontweight="bold")
        del label
    ax.set_xticks(list(range(replicates + 1)))
    ax.set_xlabel(f"replicates that solved the task (of {replicates})", fontsize=7.2)
    ax.set_ylabel("tasks", fontsize=7.2)
    ax.set_ylim(0, 72)
    ax.grid(axis="y", color=GRID, lw=0.45, zorder=0)
    viz.baseline_axis(ax)


def panel_pass(ax: Any, datasets: list[tuple[str, dict[str, Any], int]]) -> None:
    ends: list[dict[str, Any]] = []
    for name, data, replicates in datasets:
        for arm, label, colour in PANELS:
            xs = list(range(1, replicates + 1))
            ys = [pass_at_k(data, arm, k) * 100 for k in xs]
            marker = "o" if arm == "baseline" else "s"
            ax.plot(xs, ys, color=colour, lw=1.2, marker=marker, ms=3.4, zorder=3,
                    markeredgecolor="white", markeredgewidth=0.5)
            ends.append({"x": xs[-1] + 0.10, "y": ys[-1], "colour": colour,
                         "text": f"{label} {ys[-1]:.1f}%"})
    ends.sort(key=lambda item: item["y"])
    for index in range(1, len(ends)):
        if ends[index]["y"] - ends[index - 1]["y"] < 3.4:
            ends[index]["y"] = ends[index - 1]["y"] + 3.4
    for item in ends:
        ax.text(item["x"], item["y"], item["text"], fontsize=6.6, color=item["colour"],
                va="center", ha="left")
    ax.set_xticks([1, 2, 3])
    ax.set_xlim(0.75, 4.0)
    ax.set_ylim(20, 40)
    ax.set_xlabel("k: pooled replicate runs, solved at least once", fontsize=7.2)
    ax.set_ylabel("tasks solved (%)", fontsize=7.2)
    ax.grid(axis="y", color=GRID, lw=0.45, zorder=0)
    viz.baseline_axis(ax)


def main() -> None:
    locked = attempts(LOCKED_RUNS)
    with plt.rc_context(RC):
        fig = viz.figure(5.5, 2.5)
        left = fig.add_axes((0.115, 0.185, 0.375, 0.640))
        right = fig.add_axes((0.640, 0.185, 0.245, 0.640))
        panel_counts(left, locked, 3)
        panel_pass(right, [("locked", locked, 3)])
        viz.panel(left, "A", "Solve replication, held out")
        viz.panel(right, "B", "pass@k")
        for x0, (_, label, colour) in zip((0.30, 0.58), PANELS):
            left.add_patch(plt.Rectangle((x0, 0.44), 0.045, 0.055, transform=left.transAxes,
                                         facecolor=colour, edgecolor="none", zorder=4))
            left.text(x0 + 0.06, 0.467, label, transform=left.transAxes, fontsize=6.8,
                      color=INK_SOFT, va="center", ha="left")
        save(fig, "fig_stability", claim=CLAIM)


if __name__ == "__main__":
    main()
