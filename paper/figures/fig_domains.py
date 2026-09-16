"""Domain-level outcome map: where the evidence tools help, and where they hurt.

One dumbbell row per scientific domain (the benchmark paper's Appendix Table 5
domains) for the held-out locked-89 partition and the development dev-30 partition.
Both panels read ``results/domain-arm-analysis.json``.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

sys.path.insert(0, str(Path(__file__).resolve().parent))
from plotting import RC, domain_receipt, dotted_grid, save, scene, wilson  # noqa: E402
from theme import BLUE, RUST, TEAL  # noqa: E402

RATE_MAX = 0.80
DATA_FRAC = 0.62

SHORT_NAMES = {
    "Aeronautical and Astronautical Science and Technology": "Aeronautical & astronautical eng.",
    "Surveying and Mapping Science and Technology": "Surveying & mapping sci.",
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
        out.append({
            "domain": SHORT_NAMES.get(group, group),
            "n": row["n_tasks"],
            "baseline": row["baseline"],
            "science": row["science"],
            "delta": row["delta_pp"],
        })
    out.sort(key=lambda item: (item["delta"], item["domain"]))
    return out


def panel(ax: Any, data_rows: list[dict[str, Any]], overall: dict[str, Any],
          letter: str, title: str) -> None:
    count = len(data_rows)
    ys = list(range(count)) + [count + 0.6]
    ax.set_yticks(ys)
    ax.set_yticklabels([f"{row['domain']} ({row['n']})" for row in data_rows] + ["overall"],
                       fontsize=7.2)
    ax.get_yticklabels()[-1].set_fontweight("bold")

    for x in (0.0, 0.2, 0.4, 0.6, 0.8):
        ax.plot([x / RATE_MAX * DATA_FRAC] * 2, [0.0, 1.0], transform=ax.transAxes,
                color="#D9D9D9", lw=0.45, zorder=0)
    ax.plot([0.66, 0.66], [0.0, 1.0], transform=ax.transAxes, color="#D9D9D9", lw=0.6)

    for y, row in zip(ys[:count], data_rows):
        base, sci = row["baseline"], row["science"]
        delta = row["delta"]
        colour = TEAL if delta > 0 else (RUST if delta < 0 else "#555555")
        ax.plot([base["rate"], sci["rate"]], [y, y], color=colour, lw=1.4, alpha=0.5, zorder=2)
        ax.plot([base["rate"]], [y], marker="o", ms=3.4, color=BLUE, zorder=3,
                markeredgecolor="white", markeredgewidth=0.5, ls="none")
        ax.plot([sci["rate"]], [y], marker="s", ms=3.4, color=colour, zorder=3,
                markeredgecolor="white", markeredgewidth=0.5, ls="none")
        low, high = wilson(sci["solved"], sci["verified"])
        ax.plot([low, high], [y, y], color=colour, lw=0.7, alpha=0.45, zorder=1)
        ax.text(0.68, y, f"{delta:+.1f}", fontsize=7.0, va="center", ha="left", color=colour,
                fontweight="bold", transform=ax.get_yaxis_transform())

    y0 = ys[-1]
    base, sci = overall["baseline"], overall["science"]
    colour = TEAL if sci["rate"] >= base["rate"] else RUST
    ax.plot([0.0, 1.0], [count + 0.28, count + 0.28], transform=ax.get_yaxis_transform(),
            color="#D9D9D9", lw=0.6)
    ax.plot([base["rate"], sci["rate"]], [y0, y0], color=colour, lw=1.6, zorder=2)
    ax.plot([base["rate"]], [y0], marker="o", ms=3.8, color=BLUE, zorder=3,
            markeredgecolor="white", markeredgewidth=0.5, ls="none")
    ax.plot([sci["rate"]], [y0], marker="s", ms=3.8, color=colour, zorder=3,
            markeredgecolor="white", markeredgewidth=0.5, ls="none")
    ax.text(0.68, y0, f"{overall['delta_pp']:+.1f}", fontsize=7.2, va="center", ha="left",
            color=colour, fontweight="bold", transform=ax.get_yaxis_transform())

    ax.set_xlim(0.0, RATE_MAX / DATA_FRAC)
    ax.set_ylim(-0.8, count + 1.4)
    ax.set_xticks([0.0, 0.2, 0.4, 0.6, 0.8])
    ax.set_xticklabels(["0", "20", "40", "60", "80"])
    ax.set_xlabel("official verifier solve rate per attempt (%)", fontsize=7.4)
    ax.text(0.68, count + 1.05, "$\\Delta$ pp", fontsize=7.2, color="#555555", fontweight="bold",
            transform=ax.get_yaxis_transform())
    dotted_grid(ax)
    scene(ax, letter, title)


def main() -> None:
    payload = domain_receipt()
    locked = payload["partitions"]["locked89_k3"]
    dev = payload["partitions"]["dev30_k4"]

    with plt.rc_context(RC):
        fig, axes = plt.subplots(1, 2, figsize=(7.0, 3.4),
                                 gridspec_kw={"width_ratios": [1.18, 1.0], "wspace": 0.78})
        panel(axes[0], rows(locked, 3), locked["overall"], "A", "Locked-89, held out ($k=3$)")
        panel(axes[1], rows(dev, 2), dev["overall"], "B", "Dev-30, pooled ($k=4$)")

        handles = [
            Line2D([0], [0], marker="o", ms=3.4, ls="none", color=BLUE, markeredgecolor="white",
                   markeredgewidth=0.5, label="baseline arm"),
            Line2D([0], [0], marker="s", ms=3.4, ls="none", color=TEAL, markeredgecolor="white",
                   markeredgewidth=0.5, label="science arm, gain (whiskers: Wilson 95%)"),
            Line2D([0], [0], marker="s", ms=3.4, ls="none", color=RUST, markeredgecolor="white",
                   markeredgewidth=0.5, label="science arm, loss"),
        ]
        fig.legend(handles=handles, loc="upper center", ncol=2, frameon=False, fontsize=7.2,
                   bbox_to_anchor=(0.5, 1.10), handletextpad=0.4, columnspacing=1.4)
        fig.subplots_adjust(left=0.215, right=0.995, top=0.815, bottom=0.115)
        save(fig, "fig_domains")


if __name__ == "__main__":
    main()
