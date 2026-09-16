"""Replicate structure: task stability, pass@k, and the paired per-task outcome map.

Panels
------
A  distribution of tasks by how many replicate runs solved them, per arm
B  pass@k curves, k = 1..replicates, per arm
C  paired per-task rate scatter (baseline vs science) on the held-out tasks
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

sys.path.insert(0, str(Path(__file__).resolve().parent))
from plotting import (  # noqa: E402
    DEV_RUNS, LOCKED_RUNS, RC, attempts, save, scene,
)
from theme import BLUE, GRID, INK_SOFT, RUST, TEAL  # noqa: E402

JITTER = (-0.09, -0.03, 0.03, 0.09)


def solve_counts(data: dict[str, dict[str, list[dict[str, Any]]]], arm: str) -> list[int]:
    counts = []
    for task in sorted(data):
        rewards = [r["reward"] for r in data[task].get(arm, [])]
        verified = [int(r) for r in rewards if r is not None]
        counts.append(sum(verified))
    return counts


def pass_at_k(data: dict[str, dict[str, list[dict[str, Any]]]], arm: str, k: int) -> float:
    solved = 0
    tasks = 0
    for task in sorted(data):
        rewards = [r["reward"] for r in data[task].get(arm, [])][:k]
        verified = [int(r) for r in rewards if r is not None]
        if not verified:
            continue
        tasks += 1
        solved += any(verified)
    return solved / tasks if tasks else 0.0


def panel_counts(ax: Any, data: dict[str, Any], replicates: int, letter: str, title: str) -> None:
    width = 0.34
    for offset, arm, colour, marker in ((-width / 2, "baseline", BLUE, "o"),
                                        (width / 2, "science", TEAL, "s")):
        counts = solve_counts(data, arm)
        counter = Counter(counts)
        xs = list(range(replicates + 1))
        ys = [counter.get(x, 0) for x in xs]
        ax.bar([x + offset for x in xs], ys, width=width, color=colour, alpha=0.85,
               edgecolor="white", linewidth=0.5, zorder=2,
               label="baseline arm" if arm == "baseline" else "science arm")
        del marker
    ax.set_xticks(list(range(replicates + 1)))
    ax.set_xticklabels([str(x) for x in range(replicates + 1)])
    ax.set_xlabel(f"replicate runs that solved the task (of {replicates})", fontsize=7.4)
    ax.set_ylabel("tasks", fontsize=7.4)
    ax.set_ylim(0, max(Counter(solve_counts(data, "baseline") + solve_counts(data, "science")).values()) * 1.28)
    ax.grid(axis="y", color=GRID, lw=0.45, zorder=0)
    ax.set_axisbelow(True)
    ax.tick_params(axis="x", length=2.5, labelsize=7.2)
    ax.tick_params(axis="y", length=0, labelsize=7.2)
    ax.spines["bottom"].set_color(INK_SOFT)
    ax.spines["left"].set_visible(False)
    scene(ax, letter, title)


def panel_pass_at_k(ax: Any, datasets: list[tuple[str, dict[str, Any], int]], letter: str, title: str) -> None:
    ends: list[dict[str, Any]] = []
    for name, data, replicates in datasets:
        for arm, dash in (("baseline", (0, (4, 2))), ("science", "-")):
            colour = BLUE if arm == "baseline" else TEAL
            ks = list(range(1, replicates + 1))
            ys = [pass_at_k(data, arm, k) * 100 for k in ks]
            marker = "o" if arm == "baseline" else "s"
            ax.plot(ks, ys, color=colour, lw=1.3, ls=dash, marker=marker, ms=3.2,
                    markeredgecolor="white", markeredgewidth=0.5, zorder=3)
            ends.append({"x": ks[-1], "y": ys[-1], "colour": colour,
                         "text": f"{name} {arm} {ys[-1]:.0f}"})
    ends.sort(key=lambda item: item["y"])
    gap = 4.2
    for index in range(1, len(ends)):
        if ends[index]["y"] - ends[index - 1]["y"] < gap:
            ends[index]["y"] = ends[index - 1]["y"] + gap
    for item in ends:
        ax.text(item["x"] + 0.14, item["y"], item["text"], ha="left", va="center",
                fontsize=6.0, color=item["colour"])
    ax.set_xticks([1, 2, 3, 4])
    ax.set_xlabel("k (replicate runs pooled, any solve counts)", fontsize=7.4)
    ax.set_ylabel("tasks solved by at least one run (%)", fontsize=7.4)
    ax.set_xlim(0.7, 6.3)
    ax.set_ylim(0, 62)
    ax.grid(axis="y", color=GRID, lw=0.45, zorder=0)
    ax.set_axisbelow(True)
    ax.tick_params(labelsize=7.2, length=2.5)
    ax.spines["bottom"].set_color(INK_SOFT)
    ax.spines["left"].set_visible(False)
    scene(ax, letter, title)


def panel_pairing(ax: Any, data: dict[str, Any], replicates: int, letter: str, title: str) -> None:
    xs: list[float] = []
    ys: list[float] = []
    labels: list[str] = []
    for task in sorted(data):
        base = [r["reward"] for r in data[task].get("baseline", [])]
        sci = [r["reward"] for r in data[task].get("science", [])]
        base_ok = [int(r) for r in base if r is not None]
        sci_ok = [int(r) for r in sci if r is not None]
        if not base_ok or not sci_ok:
            continue
        xs.append(sum(base_ok) / len(base_ok) * 100)
        ys.append(sum(sci_ok) / len(sci_ok) * 100)
        labels.append(task)

    ax.plot([-6, 106], [-6, 106], color=GRID, lw=0.9, zorder=1)
    gained = sum(1 for x, y in zip(xs, ys) if y > x)
    lost = sum(1 for x, y in zip(xs, ys) if y < x)
    tie = len(xs) - gained - lost
    for x, y, task in zip(xs, ys, labels):
        colour = TEAL if y > x else (RUST if y < x else INK_SOFT)
        offset = JITTER[abs(hash(task)) % len(JITTER)]
        ax.scatter(x + offset, y - offset, s=14, color=colour, alpha=0.85, zorder=3,
                   edgecolors="white", linewidths=0.4)
    ax.set_xlim(-6, 106)
    ax.set_ylim(-6, 106)
    ax.set_xticks([0, 25, 50, 75, 100])
    ax.set_yticks([0, 25, 50, 75, 100])
    ax.set_xlabel(f"baseline solve rate per task (%, {replicates} attempts)", fontsize=7.4)
    ax.set_ylabel("science solve rate per task (%)", fontsize=7.4)
    ax.text(99, 6, f"science-only gain: {gained}", fontsize=6.6, color=TEAL, fontweight="bold",
            ha="right", va="bottom")
    ax.text(3, 99, f"baseline-only: {lost}   tied: {tie}", fontsize=6.6, color=RUST,
            fontweight="bold", ha="left", va="top")
    ax.grid(color=GRID, lw=0.4)
    ax.set_axisbelow(True)
    ax.tick_params(labelsize=7.2, length=2.5)
    ax.spines["bottom"].set_color(INK_SOFT)
    ax.spines["left"].set_color(INK_SOFT)
    scene(ax, letter, title)


def main() -> None:
    locked = attempts(LOCKED_RUNS)
    dev = attempts(DEV_RUNS)

    with plt.rc_context(RC):
        fig, axes = plt.subplots(1, 3, figsize=(7.0, 2.5),
                                 gridspec_kw={"width_ratios": [1.0, 0.86, 0.94], "wspace": 0.62})
        panel_counts(axes[0], locked, 3, "A", "Solve replication (locked-89)")
        panel_pass_at_k(axes[1], [("locked-89", locked, 3), ("dev-30", dev, 4)], "B", "pass@$k$")
        panel_pairing(axes[2], locked, 3, "C", "Paired per-task outcome")
        handles = [
            Line2D([0], [0], marker="o", ms=3.4, ls="-", color=BLUE, markeredgecolor="white",
                   markeredgewidth=0.5, label="baseline arm"),
            Line2D([0], [0], marker="s", ms=3.4, ls="--", color=TEAL, markeredgecolor="white",
                   markeredgewidth=0.5, label="science arm"),
        ]
        fig.legend(handles=handles, loc="upper center", ncol=2, frameon=False, fontsize=7.2,
                   bbox_to_anchor=(0.5, 1.10), handletextpad=0.4, columnspacing=1.4)
        fig.subplots_adjust(left=0.07, right=0.99, top=0.83, bottom=0.16)
        save(fig, "fig_stability")


if __name__ == "__main__":
    main()
