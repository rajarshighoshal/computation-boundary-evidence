"""Where the evidence tools help and where they hurt.

Dumbbell per scientific domain: the baseline rate as a circle, the CBE rate as a square, and the
signed difference as a number. No intervals are drawn --- with two or three attempts per task the
honest annotation is the count, so each row also carries solved/verified for both arms.

Rows are the benchmark paper's scientific domains; the partition decides which rows appear.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parent))
from plotting import RC, domain_receipt, save
from theme import GRID, INK_SOFT
import viz

CLAIM = ("CBE gains in mechanics, astronomy and materials science and loses in biomedical "
         "engineering and biology, while chemistry, physics and mathematics do not move.")

RATE_MAX = 1.0
SHORT = {
    "Aeronautical and Astronautical Science and Technology": "Aeronautical & astronautical eng.",
    "Surveying and Mapping Science and Technology": "Surveying & mapping",
    "Information and Communication Engineering": "Information & comm. eng.",
    "Computer Science and Technology": "Computer science",
    "Materials Science and Engineering": "Materials sci. & eng.",
    "Nuclear Science and Technology": "Nuclear sci. & eng.",
    "Atmospheric Science": "Atmospheric sci.",
    "Biomedical Engineering": "Biomedical eng.",
    "Civil Engineering": "Civil eng.",
    "Electrical Engineering": "Electrical eng.",
    "Marine Science": "Marine sci.",
}


def rows(partition: dict[str, Any], min_tasks: int) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for group, row in partition["by_domain"]["groups"].items():
        if row["n_tasks"] < min_tasks:
            continue
        base, cbe = row["baseline"], row["cbe"]
        out.append({
            "label": f"{SHORT.get(group, group)} ({row['n_tasks']})",
            "base": base["rate"],
            "cbe": cbe["rate"],
            "delta": row["delta_pp"],
            "counts": f"{base['solved']}/{base['verified']} → {cbe['solved']}/{cbe['verified']}",
        })
    out.sort(key=lambda item: (item["delta"], item["label"]))
    return out


def panel(ax: Any, data_rows: list[dict[str, Any]], overall: dict[str, Any], letter: str,
          title: str) -> None:
    count = len(data_rows)
    ys = list(range(count)) + [count + 0.75]
    ax.set_yticks(ys)
    ax.set_yticklabels([row["label"] for row in data_rows] + ["overall"], fontsize=7.0)
    ax.get_yticklabels()[-1].set_fontweight("bold")

    # gridlines span the data rows only; the right band is reserved for the difference column
    ax.vlines([0.0, 0.25, 0.5, 0.75, 1.0], ymin=-0.7, ymax=count - 0.3, color=GRID, lw=0.45,
              zorder=0)
    ax.vlines([0.0], ymin=-0.7, ymax=count - 0.3, color=INK_SOFT, lw=0.7, zorder=1)

    for y, row in zip(ys[:count], data_rows):
        kind = "gain" if row["delta"] > 0 else ("loss" if row["delta"] < 0 else "tie")
        line_colour = viz.COLOUR["line"] if kind == "tie" else viz.COLOUR[kind]
        ax.plot([row["base"], row["cbe"]], [y, y], color=line_colour, lw=1.3,
                alpha=1.0 if kind == "tie" else 0.55, zorder=2)
        if kind == "tie":
            # coincident values: separate the markers by a hair so both read
            viz.dot(ax, row["base"] - 0.022, y, "baseline", size=4.2)
            viz.dot(ax, row["cbe"] + 0.022, y, kind, size=3.4)
        else:
            viz.dot(ax, row["base"], y, "baseline", size=3.5)
            viz.dot(ax, row["cbe"], y, kind, size=3.5)
        ax.text(1.05, y, f"{row['delta']:+.1f}", fontsize=7.0, va="center", ha="left",
                color=viz.COLOUR[kind], fontweight="bold", clip_on=True)

    y0 = ys[-1]
    base, cbe = overall["baseline"], overall["cbe"]
    kind = "gain" if overall["delta_pp"] > 0 else ("loss" if overall["delta_pp"] < 0 else "tie")
    ax.axhline(count + 0.35, color=GRID, lw=0.7, xmin=0.0, xmax=1.0)
    ax.plot([base["rate"], cbe["rate"]], [y0, y0], color=viz.COLOUR[kind], lw=1.6, zorder=2)
    viz.dot(ax, base["rate"], y0, "baseline", size=4.0)
    viz.dot(ax, cbe["rate"], y0, kind, size=4.0)
    ax.text(1.05, y0, f"{overall['delta_pp']:+.1f}", fontsize=7.2, va="center", ha="left",
            color=viz.COLOUR[kind], fontweight="bold", clip_on=True)

    ax.set_xlim(0.0, 1.30)
    ax.set_ylim(-0.8, count + 1.95)
    ax.set_xticks([0.0, 0.25, 0.5, 0.75, 1.0])
    ax.set_xticklabels(["0", "25", "50", "75", "100"])
    ax.set_xlabel("official verifier solve rate per attempt (%)", fontsize=7.2)
    ax.text(1.05, count + 1.20, "Δ pp", fontsize=7.0, color=INK_SOFT, ha="left")
    ax.text(0.02, count + 1.20, "● baseline   ■ CBE", fontsize=7.0, color=INK_SOFT, ha="left")
    viz.panel(ax, letter, title)
    viz.baseline_axis(ax)


def main() -> None:
    payload = domain_receipt()
    locked = payload["partitions"]["locked89_k3"]
    dev = payload["partitions"]["dev30_k4"]

    with plt.rc_context(RC):
        fig = viz.figure(5.5, 3.05)
        left = fig.add_axes((0.210, 0.115, 0.340, 0.740))
        right = fig.add_axes((0.695, 0.115, 0.235, 0.740))
        panel(left, rows(locked, 3), locked["overall"], "A", "Held out ($k=3$)")
        panel(right, rows(dev, 2), dev["overall"], "B", "Development ($k=4$)")
        save(fig, "fig_domains", claim=CLAIM)
    print(f"  locked rows: {len(rows(locked, 3))}, dev rows: {len(rows(dev, 2))}")


if __name__ == "__main__":
    main()
