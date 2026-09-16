#!/usr/bin/env python3
"""Derive explanatory views from existing verifier receipts; no new trials.

Inputs are compact exports in data/. The official reward is never replaced by
private-test counts. Missing verdicts remain missing, not failed.
"""
from __future__ import annotations
import csv
import json
from collections import Counter
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARMS = ('baseline', 'cbe')

def load(name):
    return json.loads((ROOT / name).read_text())

def complete(block):
    return (block['collected'] > 0 and block['passed'] == block['collected']
            and block['return_code'] == 0)

def main():
    data = load('generated/results.json')
    metadata = load('data/task_metadata.json')
    receipts = load('data/full_verdicts.json')
    lookup = {(r['task'], r['arm'], r['repeat']): r['verdict'] for r in receipts}
    if len(lookup) != len(receipts):
        raise ValueError('Duplicate verifier receipt')
    tasks = data['tasks']
    gates = {}
    for arm in ARMS:
        rr = [r['verdict'] for r in receipts if r['arm'] == arm]
        categories = Counter((complete(r['public']), complete(r['private'])) for r in rr)
        gates[arm] = dict(verified=len(rr), public_pass=sum(complete(r['public']) for r in rr),
                         private_pass=sum(complete(r['private']) for r in rr),
                         exact=sum(r['reward'] for r in rr),
                         both=categories[(True, True)], public_only=categories[(True, False)],
                         private_only=categories[(False, True)], neither=categories[(False, False)])
        assert gates[arm]['exact'] == gates[arm]['both'] == data['totals'][arm]['solved']
    joint = [[0]*3 for _ in range(3)]  # row = exact lower/equal/higher; col = private lower/equal/higher
    details = []
    for task, item in tasks.items():
        info = metadata[task]
        item['repository'] = info['source_repository'].rstrip('/').split('/')[-1]
        item['title'] = info['title']
        means = {}
        for arm in ARMS:
            trials = []
            for repeat in (1, 2, 3):
                verdict = lookup.get((task, arm, repeat))
                trial = {'repeat': repeat, 'reward': None, 'passed': None, 'collected': None, 'public': None}
                if verdict is not None:
                    trial.update(reward=verdict['reward'], passed=verdict['private']['passed'],
                                 collected=verdict['private']['collected'], public=complete(verdict['public']))
                    assert verdict['reward'] == item[arm]['repeats'][repeat-1]
                trials.append(trial)
            item[arm]['trials'] = trials
            valid = [t for t in trials if t['reward'] is not None]
            assert len(valid) == item[arm]['verified']
            means[arm] = sum((Fraction(t['passed'], t['collected']) for t in valid), Fraction()) / len(valid)
            item[arm]['mean_private_fraction'] = float(means[arm])
        dp = means['cbe'] - means['baseline']
        ds = Fraction(item['cbe']['solved'],item['cbe']['verified']) - Fraction(item['baseline']['solved'],item['baseline']['verified'])
        sign = lambda x: (x > 0) - (x < 0)
        joint[sign(ds)+1][sign(dp)+1] += 1
        item['private_delta_pp'] = float(dp*100)
        details.append({'task':task, 'domain':item['domain'], 'repository':item['repository'],
                        'exact_delta_pp':float(ds*100), 'private_delta_pp':float(dp*100),
                        'baseline_private_mean':float(means['baseline']), 'cbe_private_mean':float(means['cbe'])})
    data['gates'] = gates
    data['partial_analysis'] = {'joint_counts':joint, 'row_order':['baseline higher','equal','CBE higher'],
        'column_order':['baseline higher','equal','CBE higher'],
        'exact_ties_private_different':joint[1][0]+joint[1][2],
        'definition':'Per-task mean of private passed/collected across available verdicts; compare CBE minus baseline. No private-test counts are pooled across tasks for this view.'}
    assert sum(map(sum,joint)) == len(tasks)
    data['plot_data_version'] = 2
    (ROOT/'generated/visual_results.json').write_text(json.dumps(data,indent=2))
    with (ROOT/'generated/partial_task_comparison.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(details[0]));w.writeheader();w.writerows(details)
    with (ROOT/'generated/private_joint_table.tex').open('w') as f:
        f.write('% Generated from per-task exact and mean private rates.\n')
        for name,row in zip(('Baseline higher','Equal','CBE higher'),joint):
            f.write(name+' & '+' & '.join(map(str,row))+r' \\'+'\n')
        f.write('\\bottomrule\n')
    macros = {
        'BaselinePublic':str(gates['baseline']['public_pass']), 'CbePublic':str(gates['cbe']['public_pass']),
        'BaselinePublicRate':f"{100*gates['baseline']['public_pass']/gates['baseline']['verified']:.1f}",
        'CbePublicRate':f"{100*gates['cbe']['public_pass']/gates['cbe']['verified']:.1f}",
        'BaselinePublicOnly':str(gates['baseline']['public_only']), 'CbePublicOnly':str(gates['cbe']['public_only']),
        'HiddenPrivateDifferences':str(data['partial_analysis']['exact_ties_private_different'])}
    (ROOT/'generated/visual_numbers.tex').write_text('% Generated; no new trials.\n'+''.join('\\newcommand{\\'+k+'}{'+v+'}\n' for k,v in macros.items()))
    print('Verified all 522 original rewards. Gate categories:',json.dumps(gates))
    print('Exact-by-private direction matrix:',joint)

if __name__ == '__main__':
    main()
