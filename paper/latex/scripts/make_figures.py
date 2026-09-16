#!/usr/bin/env python3
"""Regenerate figures from visual_results.json.

Figure 1: diverging discipline bars (approved clean design with legend).
Figure 3: trial matrix (original binary encoding — colored=solve, gray=unsolved).
Figure 2 (pipeline diagram) is TikZ in main.tex, not generated here.
"""
from __future__ import annotations
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Patch
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
FULL = 160 / 25.4
BLUE, TEAL, GRAY = '#2468A0', '#408F83', '#686868'
ARM_COLORS = {'baseline': BLUE, 'cbe': TEAL}
SHORT = {
    'Materials Science and Engineering': 'Materials',
    'Biomedical Engineering': 'Biomedical',
    'Aeronautical and Astronautical Science and Technology': 'Aeronautical',
    'Surveying and Mapping Science and Technology': 'Surveying',
    'Atmospheric Science': 'Atmospheric',
    'Civil Engineering': 'Civil eng.',
    'Chemistry': 'Chemistry',
}
DSHORT = {
    'Materials Science and Engineering': 'Materials (15 tasks)',
    'Biomedical Engineering': 'Biomedical eng. (10)',
    'Aeronautical and Astronautical Science and Technology': 'Aeronautical (1)',
    'Surveying and Mapping Science and Technology': 'Surveying (1)',
    'Atmospheric Science': 'Atmospheric (5)',
    'Civil Engineering': 'Civil eng. (5)',
    'Mechanics': 'Mechanics (3)',
    'Astronomy': 'Astronomy (5)',
    'Biology': 'Biology (6)',
    'Chemistry': 'Chemistry (19)',
}
plt.rcParams.update({
    'font.family': 'serif', 'font.serif': ['STIXGeneral', 'DejaVu Serif'],
    'font.size': 9, 'pdf.fonttype': 42, 'ps.fonttype': 42,
    'svg.fonttype': 'none', 'axes.linewidth': .5,
})


def save(fig, name):
    dest = ROOT / 'figures'
    dest.mkdir(exist_ok=True)
    for ext in ('pdf', 'svg', 'png'):
        fig.savefig(dest / f'{name}.{ext}', dpi=240, facecolor='white',
                    bbox_inches='tight', pad_inches=0.02)
    plt.close(fig)


def domain_outcomes(d):
    """Figure 1: diverging bars for disciplines with non-zero change."""
    movers = sorted([r for r in d['domains'] if abs(r['delta_pp']) > 0.5],
                    key=lambda r: -r['delta_pp'])
    n = len(movers)
    fig, ax = plt.subplots(figsize=(FULL, 3.0))
    fig.subplots_adjust(left=.28, right=.95, top=.97, bottom=.11)

    for i, r in enumerate(movers):
        delta = r['delta_pp']
        color = TEAL if delta > 0 else BLUE
        ax.barh(i, delta, height=.62, color=color, edgecolor='none', zorder=3)
        ha = 'left' if delta > 0 else 'right'
        off = 1.2 if delta > 0 else -1.2
        ax.text(delta + off, i, f'{delta:+.0f}', ha=ha, va='center',
                fontsize=8.5, color=color, fontweight='bold')

    ax.axvline(0, color='#333', linewidth=.8, zorder=2)
    labels = [DSHORT.get(r['domain'], r['domain']) for r in movers]
    ax.set_yticks(range(n), labels, fontsize=9)
    ax.set_ylim(n - .4, -.5)
    ax.set_xlim(-40, 28)
    ax.set_xticks([-30, -20, -10, 0, 10, 20])
    ax.set_xlabel('CBE − Baseline (pp)', fontsize=9)
    for s in ('top', 'right', 'left'):
        ax.spines[s].set_visible(False)
    ax.tick_params(left=False)
    ax.grid(axis='x', linewidth=.25, alpha=.15)
    ax.set_axisbelow(True)

    handles = [Patch(facecolor=TEAL, label='CBE higher'),
               Patch(facecolor=BLUE, label='Baseline higher')]
    ax.legend(handles=handles, loc='lower right', frameon=False,
              fontsize=8, handlelength=1.0, handletextpad=.4)
    save(fig, 'domain_outcomes')


def trial_test_matrix(d):
    """Figure 3: per-run grid with binary encoding (colored=solve, gray=unsolved)."""
    rows = sorted([(t, r) for t, r in d['tasks'].items() if abs(r['delta_pp']) > 1e-9],
                  key=lambda z: (-z[1]['delta_pp'], z[0]))
    n = len(rows)
    fig, ax = plt.subplots(figsize=(FULL, 3.52))
    fig.subplots_adjust(left=.018, right=.995, top=.82, bottom=.09)
    ax.set_xlim(0, 22.2)
    ax.set_ylim(n - .5, -.6)
    ax.axis('off')

    positions = {'baseline': [9.0, 10.35, 11.70], 'cbe': [14.10, 15.45, 16.80]}
    ax.text(0, -1.2, 'Task / repository', fontweight='bold', fontsize=8.5)
    ax.text(5.5, -1.2, 'Discipline', fontweight='bold', fontsize=8.5)
    ax.text(20.05, -1.2, 'Solved / verified', ha='center', fontweight='bold', fontsize=8.5)

    for arm, xs in positions.items():
        ax.text(np.mean(xs), -2.0, 'Baseline' if arm == 'baseline' else 'CBE',
                ha='center', color=ARM_COLORS[arm], fontweight='bold', fontsize=9)
        for rep, x in enumerate(xs, 1):
            ax.text(x, -1.12, f'Run {rep}', ha='center', fontsize=7.7)

    for yy, (task, r) in enumerate(rows):
        weight = 'bold' if task in ('022', '103') else 'normal'
        ax.text(0, yy, f'{task}  {r["repository"]}', va='center',
                fontweight=weight, fontsize=8.2)
        ax.text(5.5, yy, SHORT.get(r['domain'], r['domain']),
                va='center', fontsize=8)
        for arm, xs in positions.items():
            for x, tr in zip(xs, r[arm]['trials']):
                if tr['reward'] is None:
                    ax.text(x, yy, '—', ha='center', va='center',
                            fontsize=8.2, color=GRAY)
                    continue
                solved = tr['reward'] == 1
                ax.add_patch(Rectangle(
                    (x - .59, yy - .365), 1.18, .73,
                    facecolor=ARM_COLORS[arm] if solved else '#F2F2F2',
                    edgecolor=ARM_COLORS[arm] if solved else '#DEDEDE',
                    linewidth=1.05 if solved else .25,
                    alpha=.15 if solved else 1))
                if solved:
                    ax.add_patch(Rectangle(
                        (x - .59, yy - .365), 1.18, .73,
                        facecolor='none', edgecolor=ARM_COLORS[arm], linewidth=.9))
                ax.text(x, yy, f"{tr['passed']}/{tr['collected']}",
                        ha='center', va='center', fontsize=7.65,
                        fontweight='bold' if solved else 'normal')

        b, c = r['baseline'], r['cbe']
        ax.text(20.05, yy,
                f"{b['solved']}/{b['verified']} → {c['solved']}/{c['verified']}",
                ha='center', va='center', fontsize=8.2)

    fig.text(.018, .027,
             'Cell: private tests passed / collected. '
             'Outlined + bold: official repair. Dash: no verdict.',
             fontsize=8.1)
    save(fig, 'trial_test_matrix')


def main():
    path = ROOT / 'generated/visual_results.json'
    if not path.exists():
        raise SystemExit('Run analyze_visual_results.py first.')
    d = json.loads(path.read_text())
    domain_outcomes(d)
    trial_test_matrix(d)
    print('Rendered domain_outcomes and trial_test_matrix (PDF / SVG / PNG).')


if __name__ == '__main__':
    main()
