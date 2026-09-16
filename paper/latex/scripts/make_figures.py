#!/usr/bin/env python3
"""Regenerate every analytical figure from receipt-derived JSON.

Each chart is an independent figure with one axes, never a subplot grid.
The blue/teal encoding and serif typography follow the supplied visual brief.
No empirical result is typed into the plotting code. Run analyze_results.py and
analyze_visual_results.py first. Outputs: editable SVG, vector PDF, preview PNG.
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
FULL, COL = 160/25.4, 77/25.4
BLUE, TEAL, GRAY = '#2468A0', '#408F83', '#686868'
ARM_COLORS = {'baseline': BLUE, 'cbe': TEAL}
ALIASES = {
 'Materials Science and Engineering': 'Materials science & engineering',
 'Biomedical Engineering': 'Biomedical engineering',
 'Aeronautical and Astronautical Science and Technology': 'Aeronautical / astronautical science',
 'Surveying and Mapping Science and Technology': 'Surveying / mapping science',
 'Information and Communication Engineering': 'Information / communication engineering',
 'Computer Science and Technology': 'Computer science & technology'}
SHORT = {
 'Materials Science and Engineering':'Materials', 'Biomedical Engineering':'Biomedical',
 'Aeronautical and Astronautical Science and Technology':'Aeronautical',
 'Surveying and Mapping Science and Technology':'Surveying',
 'Atmospheric Science':'Atmospheric', 'Civil Engineering':'Civil eng.'}
plt.rcParams.update({'font.family':'serif', 'font.serif':['STIXGeneral','DejaVu Serif'], 'font.size':8.5,
 'axes.labelsize':8.5,'xtick.labelsize':8,'ytick.labelsize':8,
 'pdf.fonttype':42,'ps.fonttype':42,'svg.fonttype':'none','axes.linewidth':.6})

def save(fig, name):
    dest = ROOT/'figures'; dest.mkdir(exist_ok=True)
    for ext in ('pdf','svg','png'):
        fig.savefig(dest/f'{name}.{ext}', dpi=240, facecolor='white')
    plt.close(fig)

def simple(ax, grid='x'):
    for side in ('top','right','left'): ax.spines[side].set_visible(False)
    ax.tick_params(axis='y', length=0)
    ax.grid(axis=grid, alpha=.18, linewidth=.5)
    ax.set_axisbelow(True)

def gates(d):
    fig, ax = plt.subplots(figsize=(COL,2.50))
    fig.subplots_adjust(left=.36, right=.97, bottom=.17, top=.86)
    categories=[('public_pass','Public\nreproduction'),('private_pass','Entire\nprivate suite'),('exact','Official\nrepair')]
    for offset,arm in [(-.17,'baseline'),(.17,'cbe')]:
        g=d['gates'][arm]; vals=[100*g[k]/g['verified'] for k,_ in categories]
        y=np.arange(len(vals))+offset
        ax.barh(y, vals, height=.29, label='Baseline' if arm=='baseline' else 'CBE',color=ARM_COLORS[arm])
        for yy,(key,_),v in zip(y,categories,vals):
            ax.text(108, yy, f"{g[key]}/{g['verified']}", ha='left',va='center',fontsize=8)
    ax.set_yticks(range(len(categories)), [x[1] for x in categories]);ax.invert_yaxis()
    ax.set_xlim(0,155);ax.set_xticks([0,50,100]);ax.spines['bottom'].set_bounds(0,100)
    ax.set_xlabel('Verified attempts passing (%)',labelpad=4)
    simple(ax)
    fig.legend(loc='upper center',bbox_to_anchor=(.58,1),frameon=False,ncol=2,fontsize=8,
               handlelength=1.1,columnspacing=1)
    save(fig,'public_private_gap')

def domains(d):
    rows=sorted(d['domains'], key=lambda r:(-r['delta_pp'],r['domain']))
    n=len(rows); fig,ax=plt.subplots(figsize=(FULL,4.00))
    fig.subplots_adjust(left=.40,right=.987,top=.88,bottom=.095)
    y=np.arange(n)
    for offset,arm in [(-.16,'baseline'),(.16,'cbe')]:
        vals=[100*r[arm]['solved']/r[arm]['verified'] for r in rows]
        ax.barh(y+offset,vals,height=.28,color=ARM_COLORS[arm],label='Baseline'if arm=='baseline'else'CBE')
    for yy,r in enumerate(rows):
        b,c=r['baseline'],r['cbe']
        ax.text(112,yy,f"{b['solved']}/{b['verified']} → {c['solved']}/{c['verified']}",va='center',fontsize=8.1)
        ax.text(171,yy,f"{r['delta_pp']:+.1f}",ha='right',va='center',fontsize=8.1)
    labels=[f"{ALIASES.get(r['domain'],r['domain'])}  ({r['n_tasks']})" for r in rows]
    ax.set_yticks(y,labels);ax.set_ylim(n-.5,-.65)
    ax.set_xlim(0,178);ax.set_xticks([0,25,50,75,100]);ax.spines['bottom'].set_bounds(0,100)
    ax.set_xlabel('Observed official repair rate (%)',labelpad=4)
    simple(ax)
    ax.text(112,-1.25,'Solved / verified\nBaseline → CBE',va='bottom',fontsize=8)
    ax.text(171,-1.25,'Δ pp',ha='right',va='bottom',fontsize=8)
    fig.text(.017,.925,'Scientific discipline (number of tasks)',fontsize=9,fontweight='bold')
    fig.legend(loc='upper left',bbox_to_anchor=(.40,.98),ncol=2,frameon=False,fontsize=8.5,handlelength=1.4)
    save(fig,'domain_outcomes')

def task_matrix(d):
    rows=sorted([(t,r)for t,r in d['tasks'].items()if abs(r['delta_pp'])>1e-9],
                key=lambda z:(-z[1]['delta_pp'],z[0]))
    n=len(rows);fig,ax=plt.subplots(figsize=(FULL,3.52))
    fig.subplots_adjust(left=.018,right=.995,top=.82,bottom=.09)
    ax.set_xlim(0,22.2);ax.set_ylim(n-.5,-.6);ax.axis('off')
    positions={'baseline':[9.0,10.35,11.70], 'cbe':[14.10,15.45,16.80]}
    ax.text(0,-1.2,'Task / repository',fontweight='bold',fontsize=8.5)
    ax.text(5.5,-1.2,'Discipline',fontweight='bold',fontsize=8.5)
    ax.text(20.05,-1.2,'Solved / verified',ha='center',fontweight='bold',fontsize=8.5)
    for arm,xs in positions.items():
        ax.text(np.mean(xs),-2.0,'Baseline'if arm=='baseline'else'CBE',ha='center',color=ARM_COLORS[arm],fontweight='bold',fontsize=9)
        for rep,x in enumerate(xs,1):ax.text(x,-1.12,f'Run {rep}',ha='center',fontsize=7.7)
    for yy,(task,r) in enumerate(rows):
        repo=r['repository']
        weight='bold'if task in ('022','103')else'normal'
        ax.text(0,yy,f'{task}  {repo}',va='center',fontweight=weight,fontsize=8.2)
        ax.text(5.5,yy,SHORT.get(r['domain'],r['domain']),va='center',fontsize=8)
        for arm,xs in positions.items():
            for x,tr in zip(xs,r[arm]['trials']):
                if tr['reward'] is None:
                    ax.text(x,yy,'—',ha='center',va='center',fontsize=8.2,color=GRAY)
                    continue
                passed=tr['reward']==1
                ax.add_patch(Rectangle((x-.59,yy-.365),1.18,.73,
                    facecolor=ARM_COLORS[arm]if passed else '#F2F2F2',
                    edgecolor=ARM_COLORS[arm]if passed else '#DEDEDE',
                    linewidth=1.05 if passed else .25,alpha=.15 if passed else 1))
                if passed:
                    ax.add_patch(Rectangle((x-.59,yy-.365),1.18,.73,facecolor='none',edgecolor=ARM_COLORS[arm],linewidth=.9))
                ax.text(x,yy,f"{tr['passed']}/{tr['collected']}",ha='center',va='center',fontsize=7.65,
                        fontweight='bold'if passed else'normal')
        b,c=r['baseline'],r['cbe']
        ax.text(20.05,yy,f"{b['solved']}/{b['verified']} → {c['solved']}/{c['verified']}",ha='center',va='center',fontsize=8.2)
    fig.text(.018,.027,'Cell: private tests passed / collected. Outlined + bold: official repair. Dash: no verdict.',fontsize=8.1)
    save(fig,'trial_test_matrix')

def replication(d):
    keys=['never_solved','mixed_outcomes','all_verified_solved']
    labels=['Never\nsolved','Mixed\noutcomes','All available\nverdicts solve']
    fig,ax=plt.subplots(figsize=(COL,2.13));fig.subplots_adjust(left=.30,right=.98,top=.84,bottom=.20)
    y=np.arange(3)
    for offset,arm in [(-.17,'baseline'),(.17,'cbe')]:
        vals=[d['totals'][arm][k]for k in keys]
        ax.barh(y+offset,vals,height=.29,color=ARM_COLORS[arm],label='Baseline'if arm=='baseline'else'CBE')
        for yy,v in zip(y+offset,vals):ax.text(v+1.3,yy,str(v),va='center',fontsize=8.5)
    ax.set_yticks(y,labels);ax.invert_yaxis();ax.set_xlim(0,72);ax.set_xticks([0,20,40,60]);ax.set_xlabel('Tasks (89 per arm)')
    simple(ax)
    fig.legend(loc='upper center',bbox_to_anchor=(.6,1.02),ncol=2,frameon=False,fontsize=8,handlelength=1.1,columnspacing=1)
    save(fig,'replication')

def partial_scatter(d):
    # Supplement: paired private-test changes across all tasks. Larger marks mean coincident observations.
    from collections import Counter
    points=Counter((round(r['delta_pp'],8),round(r['private_delta_pp'],8))for r in d['tasks'].values())
    fig,ax=plt.subplots(figsize=(FULL,3.8));fig.subplots_adjust(left=.12,right=.96,top=.92,bottom=.19)
    xs,ys=zip(*points);counts=list(points.values())
    ax.scatter(xs,ys,s=[22+15*n for n in counts],alpha=.45)
    for (x,y),n in points.items():
        if n>1:ax.annotate(str(n),(x,y),ha='center',va='center',fontsize=8)
    ax.axhline(0,linewidth=.7,alpha=.3);ax.axvline(0,linewidth=.7,alpha=.3)
    for t in ('018','022','103','074','107'):
        r=d['tasks'][t];ax.annotate(t,(r['delta_pp'],r['private_delta_pp']),xytext=(7,7),textcoords='offset points',fontsize=8)
    ax.set_xlabel('CBE − baseline: observed official-repair rate (percentage points)')
    ax.set_ylabel('CBE − baseline: mean private-test pass fraction (pp)')
    ax.set_xlim(-78,115);ax.set_ylim(-110,80);ax.grid(alpha=.17)
    ax.set_title('Exact ties can hide changes in partial test coverage',fontsize=10,loc='left')
    save(fig,'support_partial_comparison')

def main():
    path=ROOT/'generated/visual_results.json'
    if not path.exists():raise SystemExit('Run scripts/analyze_visual_results.py first.')
    d=json.loads(path.read_text())
    gates(d);domains(d);task_matrix(d);replication(d);partial_scatter(d)
    print('Rendered four main analytical figures and one supporting comparison (PDF / SVG / PNG).')

if __name__=='__main__':main()
