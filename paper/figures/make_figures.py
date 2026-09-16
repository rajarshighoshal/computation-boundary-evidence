"""Generate all paper figures using the shared styling theme.

Consumes durable results JSON files and writes vector PDFs for LaTeX
plus high-res PNGs for visual inspection into paper/figures/out/.

Usage:
    PYTHONPATH=. .venv/bin/python paper/figures/make_figures.py
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from paper.figures.theme import (
    COLOR_BASELINE,
    COLOR_EXPLORE,
    COLOR_NEUTRAL,
    COLOR_SCIENCE,
    new_figure,
    save_figure,
    wilson_ci,
)

ROOT = Path(__file__).resolve().parents[2]
RESULTS_DIR = ROOT / "results"


def load_json(rel_path: str) -> dict[str, Any]:
    path = RESULTS_DIR / rel_path
    if not path.is_file():
        raise FileNotFoundError(f"Missing durable receipt: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


# -----------------------------------------------------------------------------
# Figure 1: Solve Rates across Partitions with 95% Wilson Confidence Intervals
# -----------------------------------------------------------------------------
def figure_solve_rates(locked_analysis: dict[str, Any]) -> None:
    """Figure 1: Main repair performance comparison across partitions."""
    locked_base = locked_analysis["totals"]["baseline"]
    locked_sci = locked_analysis["totals"]["science"]

    dev_b_solved, dev_b_tot = 43, 120
    dev_s_solved, dev_s_tot = 44, 120

    categories = [
        "Dev-30\n(k=4)",
        "Locked-89\n(k=1)",
        "Locked-89\n(k=2)",
        "Locked-89\n(Pooled)",
    ]

    base_counts = [
        (dev_b_solved, dev_b_tot),
        (23, 89),
        (20, 89),
        (locked_base["attempts_solved"], locked_base["attempts_verified"]),
    ]
    sci_counts = [
        (dev_s_solved, dev_s_tot),
        (23, 89),
        (22, 88),
        (locked_sci["attempts_solved"], locked_sci["attempts_verified"]),
    ]

    fig, ax = new_figure(cols=1, height=2.4)

    x = np.arange(len(categories))
    width = 0.35

    base_rates = [k / n for k, n in base_counts]
    sci_rates = [k / n for k, n in sci_counts]

    base_err_low = []
    base_err_high = []
    for (k, n), r in zip(base_counts, base_rates):
        lo, hi = wilson_ci(k, n)
        base_err_low.append(r - lo)
        base_err_high.append(hi - r)

    sci_err_low = []
    sci_err_high = []
    for (k, n), r in zip(sci_counts, sci_rates):
        lo, hi = wilson_ci(k, n)
        sci_err_low.append(r - lo)
        sci_err_high.append(hi - r)

    rects1 = ax.bar(
        x - width / 2,
        [r * 100 for r in base_rates],
        width,
        yerr=[[e * 100 for e in base_err_low], [e * 100 for e in base_err_high]],
        label="Baseline",
        color=COLOR_BASELINE,
        capsize=2.5,
        error_kw={"elinewidth": 0.8, "ecolor": "#222222"},
        edgecolor="#222222",
        linewidth=0.5,
    )

    rects2 = ax.bar(
        x + width / 2,
        [r * 100 for r in sci_rates],
        width,
        yerr=[[e * 100 for e in sci_err_low], [e * 100 for e in sci_err_high]],
        label="Science",
        color=COLOR_SCIENCE,
        capsize=2.5,
        error_kw={"elinewidth": 0.8, "ecolor": "#222222"},
        edgecolor="#222222",
        linewidth=0.5,
    )

    for rect, (k, n), r in zip(rects1, base_counts, base_rates):
        lo, hi = wilson_ci(k, n)
        ax.annotate(
            f"{r*100:.1f}%\n({k}/{n})",
            xy=(rect.get_x() + rect.get_width() / 2, hi * 100 + 1.2),
            ha="center",
            va="bottom",
            fontsize=5.8,
            color="#222222",
            fontweight="bold",
            linespacing=0.85,
        )

    for rect, (k, n), r in zip(rects2, sci_counts, sci_rates):
        lo, hi = wilson_ci(k, n)
        ax.annotate(
            f"{r*100:.1f}%\n({k}/{n})",
            xy=(rect.get_x() + rect.get_width() / 2, hi * 100 + 1.2),
            ha="center",
            va="bottom",
            fontsize=5.8,
            color="#222222",
            fontweight="bold",
            linespacing=0.85,
        )

    ax.set_ylabel("Repair Solve Rate (%)")
    ax.set_xticks(x)
    ax.set_xticklabels(categories)
    ax.set_ylim(0, 56)
    ax.legend(loc="upper right", framealpha=0.95, ncol=2)
    ax.set_title("Verifier Success by Partition")
    fig.tight_layout()
    pdf, png = save_figure(fig, "fig_solve_rates")
    print(f"Generated Figure 1: {pdf.name}, {png.name}")


# -----------------------------------------------------------------------------
# Figure 2: The Single-Attempt Noise Floor (Task Stability Matrix)
# -----------------------------------------------------------------------------
def figure_task_stability(locked_analysis: dict[str, Any]) -> None:
    """Figure 2: Empirical demonstration of the sampling noise floor across repeated trials."""
    fig, (ax_dev, ax_locked) = new_figure(cols=2, height=2.2, ncols=2)

    dev_data = load_json("dev30-four-run-consolidation.json")
    stab = dev_data["task_stability_breakdown"]
    n_rock_solved = len(stab["rock_solid_solved_4_of_4"])
    n_rock_unsolved = len(stab["rock_solid_unsolved_0_of_4"])
    n_variable = len(stab["variable_marginal_tasks"])

    labels_dev = [
        f"Consistently\nSolved (4/4)\n[{n_rock_solved}]",
        f"Sampling\nFlipped (1-3/4)\n[{n_variable}]",
        f"Consistently\nFailed (0/4)\n[{n_rock_unsolved}]",
    ]
    counts_dev = [n_rock_solved, n_variable, n_rock_unsolved]
    colors = [COLOR_SCIENCE, COLOR_EXPLORE, COLOR_NEUTRAL]

    bars_dev = ax_dev.bar(labels_dev, counts_dev, color=colors, edgecolor="#222222", linewidth=0.5, width=0.55)
    for b in bars_dev:
        h = b.get_height()
        ax_dev.annotate(
            f"{int(h)} ({h/30*100:.0f}%)",
            xy=(b.get_x() + b.get_width() / 2, h + 0.5),
            ha="center",
            va="bottom",
            fontsize=6.5,
            fontweight="bold",
        )
    ax_dev.set_ylim(0, 22)
    ax_dev.set_ylabel("Number of Tasks (out of 30)")
    ax_dev.set_title("(a) Dev-30 Outcome Stability (k=4)")

    tasks = locked_analysis.get("tasks", {})
    both_solved = 0
    both_failed = 0
    flipped = 0
    for t in tasks.values():
        b_s = t.get("baseline", {}).get("solved", 0)
        s_s = t.get("science", {}).get("solved", 0)
        b_v = t.get("baseline", {}).get("verified", 0)
        s_v = t.get("science", {}).get("verified", 0)
        total_attempts = b_v + s_v
        total_solved = b_s + s_s
        if total_solved == total_attempts and total_attempts > 0:
            both_solved += 1
        elif total_solved == 0:
            both_failed += 1
        else:
            flipped += 1

    total_locked = len(tasks)
    labels_locked = [
        f"Robustly\nSolved\n[{both_solved}]",
        f"Stochastic\nFlips\n[{flipped}]",
        f"Robustly\nUnsolved\n[{both_failed}]",
    ]
    counts_locked = [both_solved, flipped, both_failed]

    bars_locked = ax_locked.bar(labels_locked, counts_locked, color=colors, edgecolor="#222222", linewidth=0.5, width=0.55)
    for b in bars_locked:
        h = b.get_height()
        ax_locked.annotate(
            f"{int(h)} ({h/total_locked*100:.0f}%)",
            xy=(b.get_x() + b.get_width() / 2, h + 1.3),
            ha="center",
            va="bottom",
            fontsize=6.5,
            fontweight="bold",
        )
    ax_locked.set_ylim(0, 68)
    ax_locked.set_ylabel("Number of Tasks (out of 89)")
    ax_locked.set_title("(b) Locked-89 Outcome Stability (k=2)")

    fig.tight_layout()
    pdf, png = save_figure(fig, "fig_task_stability")
    print(f"Generated Figure 2: {pdf.name}, {png.name}")


# -----------------------------------------------------------------------------
# Figure 3: Paradigm-Stratified Solve Rates and Contrasts
# -----------------------------------------------------------------------------
def figure_paradigms() -> None:
    """Figure 3: Stratification across Issue-Driven, Exploratory, and Integration paradigms."""
    paradigm_data = load_json("paradigm-analysis-summary.json")
    findings = paradigm_data["experimental_findings_by_paradigm"]

    paradigms = ["Issue-Driven\n(43.7%)", "Expert-Exploratory\n(41.2%)", "Engineering-Integ.\n(15.1%)"]
    keys = ["Issue-Driven", "Expert-Exploratory", "Engineering-Integration"]

    base_rates = [float(findings[k]["baseline_solved_rate"].rstrip("%")) for k in keys]
    sci_rates = [float(findings[k]["science_solved_rate"].rstrip("%")) for k in keys]

    fig, ax = new_figure(cols=1, height=2.4)

    x = np.arange(len(paradigms))
    width = 0.35

    ax.bar(
        x - width / 2,
        base_rates,
        width,
        label="Baseline",
        color=COLOR_BASELINE,
        edgecolor="#222222",
        linewidth=0.5,
    )
    ax.bar(
        x + width / 2,
        sci_rates,
        width,
        label="Science",
        color=COLOR_SCIENCE,
        edgecolor="#222222",
        linewidth=0.5,
    )

    deltas = ["+1.5 pp\n(Structural Win)", "-1.8 pp\n(Cognitive Anchor)", "0.0 pp\n(Architectural Ceiling)"]
    for i, (b, s, delta) in enumerate(zip(base_rates, sci_rates, deltas)):
        top = max(b, s)
        ax.annotate(
            delta,
            xy=(x[i], top + 1.2),
            ha="center",
            va="bottom",
            fontsize=6.0,
            fontweight="bold",
            color="#222222",
            linespacing=0.9,
        )

    ax.set_ylabel("Solve Rate (%)")
    ax.set_xticks(x)
    ax.set_xticklabels(paradigms)
    ax.set_ylim(0, 42)
    ax.legend(loc="upper right", framealpha=0.95, ncol=2)
    ax.set_title("Performance by Benchmark Paradigm")

    fig.tight_layout()
    pdf, png = save_figure(fig, "fig_paradigms")
    print(f"Generated Figure 3: {pdf.name}, {png.name}")


# -----------------------------------------------------------------------------
# Figure 4: Resource Efficiency Dividend
# -----------------------------------------------------------------------------
def figure_efficiency(locked_analysis: dict[str, Any]) -> None:
    """Figure 4: Token efficiency and wall-clock comparison."""
    totals = locked_analysis["totals"]
    b = totals["baseline"]
    s = totals["science"]

    fig, (ax_tokens, ax_time) = new_figure(
        cols=1,
        height=2.2,
        ncols=2,
        gridspec_kw={"wspace": 0.42},
    )

    b_out = b["output_tokens"] / b["attempts_verified"] / 1e3
    s_out = s["output_tokens"] / s["attempts_verified"] / 1e3

    bars_tok = ax_tokens.bar(
        ["Baseline", "Science"],
        [b_out, s_out],
        color=[COLOR_BASELINE, COLOR_SCIENCE],
        edgecolor="#222222",
        linewidth=0.5,
        width=0.55,
    )
    diff_pct = (s_out - b_out) / b_out * 100
    ax_tokens.annotate(
        f"{diff_pct:+.1f}%\nOutput",
        xy=(1, s_out / 2),
        ha="center",
        va="center",
        fontsize=6.5,
        color="white",
        fontweight="bold",
    )
    for rect in bars_tok:
        h = rect.get_height()
        ax_tokens.annotate(
            f"{h:.1f}k",
            xy=(rect.get_x() + rect.get_width() / 2, h + 1.0),
            ha="center",
            va="bottom",
            fontsize=6.5,
            fontweight="bold",
        )
    ax_tokens.set_ylabel("Output Tokens (k / Attempt)", labelpad=2)
    ax_tokens.set_ylim(0, 56)
    ax_tokens.set_title("(a) Generation Budget", pad=8)

    b_sec = b["mean_work_seconds_per_attempt"]
    s_sec = s["mean_work_seconds_per_attempt"]

    bars_sec = ax_time.bar(
        ["Baseline", "Science"],
        [b_sec, s_sec],
        color=[COLOR_BASELINE, COLOR_SCIENCE],
        edgecolor="#222222",
        linewidth=0.5,
        width=0.55,
    )
    for rect in bars_sec:
        h = rect.get_height()
        ax_time.annotate(
            f"{int(h)}s",
            xy=(rect.get_x() + rect.get_width() / 2, h + 25),
            ha="center",
            va="bottom",
            fontsize=6.5,
            fontweight="bold",
        )
    ax_time.set_ylabel("Work Seconds / Attempt", labelpad=2)
    ax_time.set_ylim(0, 1600)
    ax_time.set_title("(b) Active Work Time", pad=8)

    fig.tight_layout()
    pdf, png = save_figure(fig, "fig_efficiency")
    print(f"Generated Figure 4: {pdf.name}, {png.name}")


def main() -> None:
    locked_analysis = load_json("locked89-k2-analysis.json")
    print(f"Loaded locked analysis with k={locked_analysis.get('k', 2)} runs.")
    figure_solve_rates(locked_analysis)
    figure_task_stability(locked_analysis)
    figure_paradigms()
    figure_efficiency(locked_analysis)
    print("All 4 figures successfully regenerated with clean layout!")


if __name__ == "__main__":
    main()
