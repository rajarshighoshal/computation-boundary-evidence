"""Resource use at matched solve rates.

Panels
------
A  pooled token composition per arm on the held-out partition
B  per-attempt output-token distributions (ECDF) per arm
C  output tokens per *solved* attempt, per arm (locked + dev)
D  wall-clock work per attempt per arm

All values come from run.json usage records attached to verifier receipts.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

sys.path.insert(0, str(Path(__file__).resolve().parent))
from plotting import (  # noqa: E402
    DEV_RUNS, LOCKED_RUNS, RC, attempts, locked_receipt, save, scene,
)
from theme import BLUE, GRID, INK_SOFT, LIGHT_BLUE, LIGHT_TEAL, RUST, TEAL  # noqa: E402

COLORS = {"baseline": BLUE, "science": TEAL}
LIGHT = {"baseline": LIGHT_BLUE, "science": LIGHT_TEAL}


def values(data: dict[str, Any], arm: str, key: str, *, solved_only: bool = False) -> list[float]:
    out = []
    for task in sorted(data):
        for record in data[task].get(arm, []):
            if record["reward"] is None:
                continue
            if solved_only and not record["reward"]:
                continue
            out.append(float(record[key]))
    return out


def ecdf(ax: Any, samples: list[float], colour: str, *, ls: str = "-", label: str = "") -> None:
    xs = sorted(samples)
    if not xs:
        return
    ys = [(index + 1) / len(xs) * 100 for index in range(len(xs))]
    ax.step(xs, ys, where="post", color=colour, lw=1.3, ls=ls, label=label, zorder=3)


def panel_tokens(ax: Any, receipt: dict[str, Any], letter: str, title: str) -> None:
    arms = ["baseline", "science"]
    keys = [("input_tokens", "input, uncached"), ("cached_input_tokens", "input, cached"),
            ("output_tokens", "output")]
    bottoms = [0.0, 0.0]
    for key, label in keys:
        heights = [receipt["totals"][arm][key] / 1e6 for arm in arms]
        ax.bar([0, 1], heights, bottom=bottoms, width=0.52,
               color={"input, uncached": "#9CC3DE", "input, cached": LIGHT_BLUE,
                      "output": TEAL}[label],
               edgecolor="white", linewidth=0.5, zorder=2, label=label)
        bottoms = [b + h for b, h in zip(bottoms, heights)]
    for index, arm in enumerate(arms):
        total = sum(receipt["totals"][arm][key] for key, _ in keys) / 1e6
        ax.text(index, total + 30, f"{total:.0f}M", ha="center", va="bottom", fontsize=7.0,
                fontweight="bold", color=COLORS[arm])
        out_tokens = receipt["totals"][arm]["output_tokens"] / 1e6
        verified = receipt["totals"][arm]["attempts_verified"]
        ax.text(index, total * 0.5, f"{out_tokens * 1e6 / verified / 1000:.0f}k\noutput\nper\nattempt",
                ha="center", va="center", fontsize=6.2, color="white", linespacing=1.3)
    ax.set_xticks([0, 1])
    ax.set_xticklabels(["baseline", "science"], fontsize=7.6)
    ax.set_ylabel("tokens over 522 verified attempts (M)", fontsize=7.4)
    ax.set_ylim(0, 1900)
    ax.tick_params(axis="y", labelsize=7.2, length=0)
    ax.tick_params(axis="x", length=0)
    ax.grid(axis="y", color=GRID, lw=0.45, zorder=0)
    ax.set_axisbelow(True)
    ax.spines["bottom"].set_visible(False)
    ax.spines["left"].set_visible(False)
    scene(ax, letter, title)


def panel_output_ecdf(ax: Any, data: dict[str, Any], letter: str, title: str) -> None:
    for arm, ls in (("baseline", (0, (4, 2))), ("science", "-")):
        samples = values(data, arm, "out")
        median = sorted(samples)[len(samples) // 2] / 1000
        ecdf(ax, samples, COLORS[arm], ls=ls, label=f"{arm} arm (median {median:.0f}k)")
    ax.set_xscale("log")
    ax.set_xlim(2, 900)
    ax.set_ylim(0, 102)
    ax.set_xticks([3, 10, 30, 100, 300])
    ax.set_xticklabels(["3k", "10k", "30k", "100k", "300k"])
    ax.set_xlabel("output tokens per attempt (log scale)", fontsize=7.4)
    ax.set_ylabel("attempts at or below (%)", fontsize=7.4)
    ax.grid(color=GRID, lw=0.45, zorder=0)
    ax.set_axisbelow(True)
    ax.tick_params(labelsize=7.2, length=2.5)
    ax.spines["bottom"].set_color(INK_SOFT)
    ax.spines["left"].set_visible(False)
    ax.legend(fontsize=6.2, loc="lower right", handletextpad=0.4)
    scene(ax, letter, title)


def panel_solved_cost(ax: Any, groups: list[tuple[str, dict[str, Any]]], letter: str, title: str) -> None:
    positions = []
    labels = []
    for index, (name, data) in enumerate(groups):
        for arm in ("baseline", "science"):
            samples = values(data, arm, "out", solved_only=True)
            mean = sum(samples) / len(samples) / 1000 if samples else 0.0
            x = index * 2 + (0 if arm == "baseline" else 1)
            ax.bar([x], [mean], width=0.62, color=COLORS[arm], edgecolor="white", linewidth=0.5,
                   zorder=2)
            ax.text(x, mean + 1.6, f"{mean:.0f}k", ha="center", va="bottom", fontsize=6.4,
                    color=COLORS[arm], fontweight="bold")
            ax.text(x, 3, f"n={len(samples)}", ha="center", va="bottom", fontsize=5.8, color="white")
            positions.append(x)
            labels.append("base" if arm == "baseline" else "sci")
    ax.set_xticks(positions)
    ax.set_xticklabels(labels, fontsize=6.4)
    ax.set_xlim(-0.55, 3.55)
    ax.text(0.256, 0.965, "locked-89", transform=ax.transAxes, ha="center", va="top", fontsize=6.6,
            color=INK_SOFT)
    ax.text(0.744, 0.965, "dev-30", transform=ax.transAxes, ha="center", va="top", fontsize=6.6,
            color=INK_SOFT)
    ax.set_ylabel("mean output tokens per solved attempt (k)", fontsize=7.4)
    ax.set_ylim(0, max(60, ax.get_ylim()[1]))
    ax.grid(axis="y", color=GRID, lw=0.45, zorder=0)
    ax.set_axisbelow(True)
    ax.tick_params(axis="y", labelsize=7.2, length=0)
    ax.tick_params(axis="x", length=0)
    ax.spines["bottom"].set_visible(False)
    ax.spines["left"].set_visible(False)
    scene(ax, letter, title)


def panel_work(ax: Any, data: dict[str, Any], letter: str, title: str) -> None:
    parts = []
    for arm in ("baseline", "science"):
        samples = sorted(values(data, arm, "work_seconds") )
        parts.append((arm, samples))
    medians = []
    for arm, samples in parts:
        median = samples[len(samples) // 2]
        medians.append((arm, median))
        ax.hist([sample / 60 for sample in samples], bins=28, color=COLORS[arm], alpha=0.55,
                zorder=2, edgecolor="white", linewidth=0.3)
        ax.plot([median / 60], [ax.get_ylim()[1] * 0.90], marker="v", ms=5, color=COLORS[arm],
                zorder=4)
    for index, (arm, median) in enumerate(medians):
        ax.text(0.03, 0.97 - index * 0.085, f"{arm} median {median / 60:.0f} min",
                transform=ax.transAxes, fontsize=6.4, color=COLORS[arm], ha="left", va="top",
                fontweight="bold")
    ax.set_xlabel("agent work seconds per attempt (minutes, model time excluded)", fontsize=7.4)
    ax.set_ylabel("attempts", fontsize=7.4)
    ax.set_xlim(0, 60)
    ax.grid(axis="y", color=GRID, lw=0.45, zorder=0)
    ax.set_axisbelow(True)
    ax.tick_params(labelsize=7.2, length=2.5)
    ax.spines["bottom"].set_color(INK_SOFT)
    ax.spines["left"].set_visible(False)
    scene(ax, letter, title)


def main() -> None:
    receipt = locked_receipt()
    locked = attempts(LOCKED_RUNS)
    dev = attempts(DEV_RUNS)

    with plt.rc_context(RC):
        fig, axes = plt.subplots(1, 4, figsize=(7.0, 2.35),
                                 gridspec_kw={"width_ratios": [0.72, 1.0, 1.03, 1.0], "wspace": 0.58})
        panel_tokens(axes[0], receipt, "A", "Token totals")
        panel_output_ecdf(axes[1], locked, "B", "Per-attempt output tokens")
        panel_solved_cost(axes[2], [("locked-89", locked), ("dev-30", dev)], "C", "Cost of a solve")
        panel_work(axes[3], locked, "D", "Wall-clock work")

        handles = [
            Line2D([0], [0], color=BLUE, lw=2.0, label="baseline arm"),
            Line2D([0], [0], color=TEAL, lw=2.0, label="science arm"),
            Line2D([0], [0], color="#9CC3DE", lw=2.0, label="uncached input"),
        ]
        fig.legend(handles=handles, loc="upper center", ncol=3, frameon=False, fontsize=7.2,
                   bbox_to_anchor=(0.5, 1.12), handletextpad=0.4, columnspacing=1.2)
        fig.subplots_adjust(left=0.065, right=0.99, top=0.83, bottom=0.19)
        save(fig, "fig_resources")


if __name__ == "__main__":
    main()
