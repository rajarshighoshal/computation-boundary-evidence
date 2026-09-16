"""What the prepared representation actually contains, and how repair fails.

Panel A  scientific objects and operations per task across every prepared task
Panel B  call-boundary kinds distilled from the science arm's recorded contracts
Panel C  outcome anatomy on the held-out tasks: both arms, one arm, or neither

Panel A/B read the frozen extraction bundles under runs/full-119-extract and the
locked-run science state; panel C reads the held-out verifier receipt.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

sys.path.insert(0, str(Path(__file__).resolve().parent))
from plotting import LOCKED_RUNS, RC, RUNS, attempts, locked_receipt, save, scene  # noqa: E402
from theme import BLUE, GRID, INK_SOFT, LIGHT_BLUE, RUST, TEAL  # noqa: E402


def bundle_stats() -> list[dict[str, Any]]:
    """Per-task representation size from the frozen extraction bundles."""
    stats = []
    for path in sorted((RUNS / "full-119-extract" / "jobs").glob("*/task_*/graph-bundle.json")):
        payload = json.loads(path.read_text())
        graph = payload["graph"]
        stats.append({
            "task": graph.get("task_id", path.parent.name),
            "objects": len(graph.get("objects") or []),
            "operations": len(graph.get("operations") or []),
            "quantities": int((graph.get("quantity_graph") or {}).get("quantities") or 0),
            "unsupported": len(graph.get("unsupported") or []),
            "api_connected": (graph.get("coverage") or {}).get("api_connected_objects", 0),
        })
    return stats


def boundary_kinds() -> tuple[Counter[str], Counter[str]]:
    """Boundary kinds recorded by the science arm, read from saved agent state."""
    counter: Counter[str] = Counter()
    providers: Counter[str] = Counter()
    for run in LOCKED_RUNS:
        for path in (RUNS / run / "jobs").glob("*-science/task_*/agent-host/science/state.json"):
            payload = json.loads(path.read_text())
            stack: list[Any] = [payload]
            while stack:
                item = stack.pop()
                if isinstance(item, dict):
                    boundary = item.get("boundary")
                    if isinstance(boundary, dict) and boundary.get("kind"):
                        counter[boundary["kind"]] += 1
                        if boundary.get("provider"):
                            providers[boundary["provider"]] += 1
                    stack.extend(item.values())
                elif isinstance(item, list):
                    stack.extend(item)
    return counter, providers


def panel_objects(ax: Any, stats: list[dict[str, Any]], letter: str, title: str) -> None:
    ys = sorted(stat["objects"] for stat in stats)
    xs = [(index + 0.5) / len(ys) * 100 for index in range(len(ys))]
    ax.plot(xs, ys, color=BLUE, lw=1.4, zorder=3)
    ax.fill_between(xs, 0, ys, color=LIGHT_BLUE, alpha=0.85, zorder=2)
    for label, value in (("median", ys[len(ys) // 2]), ("max", ys[-1])):
        ax.plot([100], [value], marker="o", ms=3.2, color=BLUE, zorder=4,
                markeredgecolor="white", markeredgewidth=0.5, ls="none")
        ax.text(101, value, f"{label} {value}", fontsize=6.4, color=BLUE, va="center")
    ax.set_xlim(0, 124)
    ax.set_ylim(0, ys[-1] * 1.12)
    ax.set_xticks([0, 25, 50, 75, 100])
    ax.set_xticklabels(["0", "25", "50", "75", "100"])
    ax.set_xlabel(f"tasks ordered by size (% of {len(ys)} prepared tasks)", fontsize=7.4)
    ax.set_ylabel("scientific objects per task", fontsize=7.4)
    ax.grid(axis="y", color=GRID, lw=0.45, zorder=0)
    ax.set_axisbelow(True)
    ax.tick_params(labelsize=7.2, length=2.5)
    ax.spines["bottom"].set_color(INK_SOFT)
    ax.spines["left"].set_visible(False)
    scene(ax, letter, title)


def panel_boundaries(ax: Any, kinds: Counter[str], providers: Counter[str],
                     letter: str, title: str) -> None:
    order = [("internal", BLUE), ("external", TEAL), ("unknown_external", RUST)]
    total = sum(kinds.values()) or 1
    left = 0.0
    for kind, colour in order:
        share = kinds.get(kind, 0) / total * 100
        ax.barh([0], [share], left=left, height=0.42, color=colour, edgecolor="white",
                linewidth=0.6, zorder=2)
        if share > 6:
            ax.text(left + share / 2, 0, f"{kind}\n{kinds.get(kind, 0)}  ({share:.0f}%)",
                    ha="center", va="center", fontsize=6.4,
                    color="white" if kind != "unknown_external" else "white", linespacing=1.35)
        else:
            ax.text(left + share / 2, 0.30, f"{kind} ({kinds.get(kind, 0)})", ha="center",
                    va="bottom", fontsize=6.2, color=colour)
        left += share
    top = ", ".join(f"{name} {count}" for name, count in providers.most_common(4))
    ax.text(0, 0.62, f"most frequent external providers: {top}", fontsize=6.4, color=INK_SOFT,
            va="bottom")
    ax.set_xlim(0, 100)
    ax.set_ylim(-0.5, 0.95)
    ax.set_yticks([])
    ax.set_xticks([0, 25, 50, 75, 100])
    ax.set_xticklabels(["0", "25", "50", "75", "100"])
    ax.set_xlabel(f"share of {total} distilled call boundaries (%)", fontsize=7.4)
    ax.grid(axis="x", color=GRID, lw=0.45, zorder=0)
    ax.set_axisbelow(True)
    ax.tick_params(labelsize=7.2, length=2.5)
    ax.spines["bottom"].set_color(INK_SOFT)
    ax.spines["left"].set_visible(False)
    scene(ax, letter, title)


def panel_outcomes(ax: Any, data: dict[str, Any], letter: str, title: str) -> None:
    both = science_only = baseline_only = neither = 0
    for task in sorted(data):
        base = [r["reward"] for r in data[task].get("baseline", []) if r["reward"] is not None]
        sci = [r["reward"] for r in data[task].get("science", []) if r["reward"] is not None]
        if not base or not sci:
            continue
        base_any, sci_any = any(base), any(sci)
        if base_any and sci_any:
            both += 1
        elif sci_any:
            science_only += 1
        elif base_any:
            baseline_only += 1
        else:
            neither += 1
    bars = [("both", both, BLUE), ("sci only", science_only, TEAL),
            ("base only", baseline_only, RUST), ("neither", neither, "#B9BEC4")]
    xs = list(range(len(bars)))
    ax.bar(xs, [count for _, count, _ in bars], width=0.58,
           color=[colour for _, _, colour in bars], edgecolor="white", linewidth=0.5, zorder=2)
    for x, (name, count, colour) in zip(xs, bars):
        ax.text(x, count + 0.8, f"{count}", ha="center", va="bottom", fontsize=6.8,
                color=colour, fontweight="bold")
    ax.set_xticks(xs)
    ax.set_xticklabels([name for name, _, _ in bars], fontsize=6.6)
    ax.set_ylabel(f"held-out tasks (of {both + science_only + baseline_only + neither})",
                  fontsize=7.4)
    ax.set_ylim(0, max(count for _, count, _ in bars) * 1.22)
    ax.grid(axis="y", color=GRID, lw=0.45, zorder=0)
    ax.set_axisbelow(True)
    ax.tick_params(axis="y", labelsize=7.2, length=0)
    ax.tick_params(axis="x", length=0)
    ax.spines["bottom"].set_visible(False)
    ax.spines["left"].set_visible(False)
    scene(ax, letter, title)


def main() -> None:
    stats = bundle_stats()
    kinds, providers = boundary_kinds()
    locked = attempts(LOCKED_RUNS)
    receipt = locked_receipt()

    with plt.rc_context(RC):
        fig, axes = plt.subplots(1, 3, figsize=(7.0, 2.6),
                                 gridspec_kw={"width_ratios": [1.0, 1.05, 0.95], "wspace": 0.62})
        panel_objects(axes[0], stats, "A", f"Representation size ({len(stats)} tasks)")
        panel_boundaries(axes[1], kinds, providers, "B", "Distilled call boundaries")
        panel_outcomes(axes[2], locked, "C",
                       f"Outcomes, {receipt['comparison']['tasks_with_both_arms']} held-out tasks")
        handles = [
            Line2D([0], [0], color=BLUE, lw=2.0, label="internal call"),
            Line2D([0], [0], color=TEAL, lw=2.0, label="external provider"),
            Line2D([0], [0], color=RUST, lw=2.0, label="unknown external"),
        ]
        fig.legend(handles=handles, loc="upper center", ncol=3, frameon=False, fontsize=7.0,
                   bbox_to_anchor=(0.5, 1.11), handletextpad=0.4, columnspacing=1.2)
        fig.subplots_adjust(left=0.075, right=0.985, top=0.80, bottom=0.17)
        save(fig, "fig_representation")

    print(f"  objects: median {sorted(s['objects'] for s in stats)[len(stats) // 2]}, "
          f"max {max(s['objects'] for s in stats)} over {len(stats)} tasks")
    print(f"  boundaries: {dict(kinds)} | top providers {providers.most_common(4)}")


if __name__ == "__main__":
    main()
