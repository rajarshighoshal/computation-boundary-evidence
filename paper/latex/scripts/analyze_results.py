#!/usr/bin/env python3
"""Recompute all reported aggregates from the bundled receipt exports.

Usage: python scripts/analyze_results.py
No API access, benchmark execution, or new experimental trials are involved.
Token totals refer to recorded completed calls, not complete billed usage.
"""
from __future__ import annotations
import csv
import json
import math
import random
import statistics
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read_csv(name: str) -> list[dict[str, str]]:
    with (ROOT / 'data' / name).open(newline='') as f:
        return list(csv.DictReader(f))

def sign_p(w: int, l: int) -> float:
    n = w + l
    return min(1., 2 * sum(math.comb(n, i) for i in range(min(w, l) + 1)) / 2**n) if n else 1.

def main() -> None:
    attempts = read_csv('attempts.csv')
    calls = read_csv('completed_calls.csv')
    if len(attempts) != len({(r['task'],r['arm'],r['repeat']) for r in attempts}):
        raise ValueError('Duplicate task/arm/repeat records')
    if len(calls) != len({(r['task'], r['arm'], r['repeat'], r['step']) for r in calls}):
        raise ValueError('Duplicate completed-call records')
    tasks = sorted({r['task'] for r in attempts})
    per_task = {}
    for task in tasks:
        per_task[task] = {'domain': next(r['domain'] for r in attempts if r['task'] == task)}
        for arm in ('baseline', 'cbe'):
            rows = [r for r in attempts if r['task'] == task and r['arm'] == arm]
            rewards = [int(r['reward']) for r in rows if r['reward'] != '']
            assert len(rows) == 3 and set(rewards) <= {0,1}
            solved, verified = sum(rewards), len(rewards)
            per_task[task][arm] = dict(solved=solved, verified=verified, scheduled=len(rows),
                                      rate=solved/verified if verified else None,
                                      mixed=0 < solved < verified,
                                      repeats=[int(r['reward']) if r['reward'] else None for r in rows])
        b,c = per_task[task]['baseline'],per_task[task]['cbe']
        per_task[task]['delta_pp'] = 100*(c['rate']-b['rate'])
    diffs = [t['delta_pp'] for t in per_task.values()]
    rng = random.Random(20260916)
    draws = sorted(sum(rng.choices(diffs,k=len(diffs)))/len(diffs) for _ in range(20000))
    comparison = dict(n_tasks=len(tasks), cbe_better=sum(d>0 for d in diffs),
                      baseline_better=sum(d<0 for d in diffs), tied=sum(d==0 for d in diffs),
                      mean_task_delta_pp=statistics.mean(diffs),
                      bootstrap_95ci_pp=[draws[500],draws[19500]], bootstrap_draws=len(draws),
                      bootstrap_seed=20260916)
    comparison['sign_test_p'] = sign_p(comparison['cbe_better'],comparison['baseline_better'])
    comparison['mixed_either'] = sum(t['baseline']['mixed'] or t['cbe']['mixed'] for t in per_task.values())
    comparison['never_both'] = sum(t['baseline']['solved']==t['cbe']['solved']==0 for t in per_task.values())
    totals = {}
    for arm in ('baseline','cbe'):
        rows=[r for r in attempts if r['arm']==arm]; cc=[r for r in calls if r['arm']==arm]
        present=[r for r in rows if int(r['run_record_present'])]
        tt=[t[arm] for t in per_task.values()]
        values=dict(scheduled=len(rows),verified=sum(r['reward']!='' for r in rows),
                    solved=sum(int(r['reward']) for r in rows if r['reward']!=''),
                    completed_calls=len(cc),session_count=sum(int(r['session_present']) for r in rows),
                    run_record_count=len(present),
                    input_tokens=sum(int(r['input_tokens']) for r in cc),
                    output_tokens=sum(int(r['output_tokens']) for r in cc),
                    old_stage_input=sum(int(r['old_stage_input']) for r in rows),
                    old_stage_output=sum(int(r['old_stage_output']) for r in rows),
                    stage_usage_unknown_attempts=sum(int(r['stage_usage_unknown']) for r in rows),
                    explicit_unknown_inflight_attempts=sum(int(r['explicit_unknown_inflight']) for r in rows),
                    mean_recorded_work_seconds=statistics.mean(float(r['work_seconds']) for r in present),
                    private_passed=sum(int(r['private_passed']) for r in rows if r['private_passed']!=''),
                    private_collected=sum(int(r['private_collected']) for r in rows if r['private_collected']!=''),
                    never_solved=sum(t['solved']==0 for t in tt),
                    mixed_outcomes=sum(t['mixed'] for t in tt),
                    all_verified_solved=sum(t['solved']==t['verified'] for t in tt),
                    success_histogram={str(k):sum(t['solved']==k for t in tt) for k in range(4)})
        values['solve_rate']=values['solved']/values['verified']
        values['successes_per_scheduled']=values['solved']/values['scheduled']
        if arm=='cbe':
            pp=[float(r['prepare_seconds']) for r in present]
            values['median_prepare_seconds']=statistics.median(pp)
        totals[arm]=values
    domains=[]
    for domain in sorted({r['domain'] for r in attempts}):
        ids=[t for t,d in per_task.items() if d['domain']==domain]
        d={'domain':domain,'n_tasks':len(ids)}
        for arm in ('baseline','cbe'):
            d[arm]={'solved':sum(per_task[t][arm]['solved'] for t in ids),
                    'verified':sum(per_task[t][arm]['verified'] for t in ids)}
        d['delta_pp']=100*(d['cbe']['solved']/d['cbe']['verified']-d['baseline']['solved']/d['baseline']['verified'])
        domains.append(d)
    sensitivity={}
    complete=[t for t,d in per_task.items() if d['baseline']['verified']==d['cbe']['verified']==3]
    sensitivity['complete_tasks']=dict(n_tasks=len(complete),
        baseline_solved=sum(per_task[t]['baseline']['solved'] for t in complete),
        cbe_solved=sum(per_task[t]['cbe']['solved'] for t in complete), attempts_per_arm=3*len(complete))
    split=json.loads((ROOT/'data/split.json').read_text())
    result={'scope':'89 locked evaluation tasks, three scheduled attempts per arm',
            'resource_scope':'Tokens: recorded completed API calls (in-flight usage unknown). Work: available run records, preparation+repair stages, excluding retry backoff and verifier.',
            'totals':totals,'comparison':comparison,'tasks':per_task,'domains':domains,'sensitivity':sensitivity}
    gen=ROOT/'generated';gen.mkdir(exist_ok=True)
    (gen/'results.json').write_text(json.dumps(result,indent=2))
    with (gen/'task_outcomes.csv').open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['task','domain','baseline_solved','baseline_verified','cbe_solved','cbe_verified','delta_pp'])
        for t,d in per_task.items():w.writerow([t,d['domain'],d['baseline']['solved'],d['baseline']['verified'],d['cbe']['solved'],d['cbe']['verified'],d['delta_pp']])
    b,c=totals['baseline'],totals['cbe']
    macros={
      'BaselineRate':f"{100*b['solve_rate']:.1f}", 'CbeRate':f"{100*c['solve_rate']:.1f}",
      'TaskDelta':f"{comparison['mean_task_delta_pp']:+.2f}",
      'CILower':f"{comparison['bootstrap_95ci_pp'][0]:.1f}", 'CIUpper':f"{comparison['bootstrap_95ci_pp'][1]:+.1f}",
      'OutputReduction':f"{100*(1-c['output_tokens']/b['output_tokens']):.1f}",
      'InputIncrease':f"{100*(c['input_tokens']/b['input_tokens']-1):.1f}",
      'WorkIncrease':f"{c['mean_recorded_work_seconds']-b['mean_recorded_work_seconds']:.0f}",
      'MedianPreparation':f"{c['median_prepare_seconds']:.0f}",
      'MixedEither':str(comparison['mixed_either']),
      'BaselineMixed':str(b['mixed_outcomes']), 'CbeMixed':str(c['mixed_outcomes']),
      'CompleteTasks':str(sensitivity['complete_tasks']['n_tasks']),
      'BaselineCompletedCalls':f"{b['completed_calls']:,}", 'CbeCompletedCalls':f"{c['completed_calls']:,}",
    }
    (gen/'numbers.tex').write_text('% Generated by scripts/analyze_results.py; do not edit.\n'+''.join('\\newcommand{\\'+k+'}{'+v+'}\n' for k,v in macros.items()))
    rows=[('Scheduled attempts',str(b['scheduled']),str(c['scheduled'])),
          ('Exact repairs / verdicts',f"{b['solved']}/{b['verified']}",f"{c['solved']}/{c['verified']}"),
          ('Exact-repair rate',f"{100*b['solve_rate']:.1f}\\%",f"{100*c['solve_rate']:.1f}\\%"),
          ('Private tests passed',f"{b['private_passed']}/{b['private_collected']}",f"{c['private_passed']}/{c['private_collected']}"),
          ('Recorded input (M tokens)',f"{b['input_tokens']/1e6:.1f}",f"{c['input_tokens']/1e6:.1f}"),
          ('Recorded output (M tokens)',f"{b['output_tokens']/1e6:.2f}",f"{c['output_tokens']/1e6:.2f}"),
          ('Mean recorded work (s)',f"{b['mean_recorded_work_seconds']:.1f}",f"{c['mean_recorded_work_seconds']:.1f}")]
    (gen/'main_table.tex').write_text('% Generated; metric scopes explained in caption and protocol.\n'+ '\n'.join(' & '.join(r)+r' \\' for r in rows)+'\n\\bottomrule\n')
    # Check outcomes against the supplied packet, without treating its resource totals as complete.
    original=json.loads((ROOT/'data/original_evidence_packet.json').read_text())
    for arm in ('baseline','cbe'):
        assert totals[arm]['solved']==original['headline']['locked89_k3'][arm]['solved']
        assert totals[arm]['verified']==original['headline']['locked89_k3'][arm]['verified']
        for task in tasks:
            expected = original['by_task']['locked89_k3'][arm][task]
            for key in ('solved', 'verified'):
                assert per_task[task][arm][key] == expected[key], (task, arm, key)
    # Reconcile complete stage ledgers with their saved completed-call records.
    call_totals = defaultdict(lambda: [0, 0])
    for call in calls:
        key = (call['task'], call['arm'], call['repeat'])
        call_totals[key][0] += int(call['input_tokens'])
        call_totals[key][1] += int(call['output_tokens'])
    reconciled = 0
    for row in attempts:
        if int(row['session_present']) and not int(row['stage_usage_unknown']):
            key = (row['task'], row['arm'], row['repeat'])
            assert call_totals[key] == [int(row['old_stage_input']), int(row['old_stage_output'])], key
            reconciled += 1
    print(f'Reconciled {reconciled} complete stage ledgers; all task outcomes match the original packet.')
    print(json.dumps({'totals':totals,'comparison':comparison,'sensitivity':sensitivity},indent=2))

if __name__=='__main__':
    main()
