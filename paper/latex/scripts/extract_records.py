#!/usr/bin/env python3
"""Export existing receipts only. Never runs a repair, verifier, or model call.

Usage: python scripts/extract_records.py --repo /path/to/TUg_research_task
The compact exports are already included; rerunning this is optional.

An attempt slot whose primary run produced no verifier verdict (infrastructure
failure, timeout, missing record) is replaced wholesale by the trial that the
dedicated gap-fill run ``RERUN`` recorded for it: verdict, stage usage, and
completed calls. The replacement keeps the slot's original repeat index and
names the gap-fill run in its ``run`` column, so every exported outcome is
traceable to the run that produced it. Calls belonging to the discarded trial
are dropped with it, never merged.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
from pathlib import Path

RUNS = ('deepseek-locked89-k1-v2', 'deepseek-locked89-k2-v2',
        'deepseek-locked89-k3-clean-v1')
RERUN = 'rerun-missing-k3-v1'
ROOT = Path(__file__).resolve().parents[1]


def load(path: Path) -> dict:
    return json.loads(path.read_text()) if path.is_file() else {}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True)
    args = parser.parse_args()
    repo = args.repo.resolve()
    if not (repo / 'runs').is_dir():
        raise SystemExit(f'No runs directory under {repo}')
    out = ROOT / 'data'
    out.mkdir(exist_ok=True)
    manifest = {}
    def tracked(path: Path) -> dict:
        if path.is_file():
            manifest[str(path.relative_to(repo))] = hashlib.sha256(path.read_bytes()).hexdigest()
        return load(path)
    packets = tracked(repo / 'results/evidence-packet.json')
    domains = packets['by_task']['locked89_k3']['domain']

    def collect_trial(trial: Path, task: str, arm: str, repeat: int, run: str):
        """Read one trial. Returns (attempt row, its completed calls, its case events)."""
        record = tracked(trial / 'run.json')
        verdict = tracked(trial / 'verifier/reward.json')
        session = tracked(trial / 'agent-host/repair-session.json')
        stages = record.get('stages', [])
        usage_unknown = any((s.get('usage') or {}).get('output_tokens') is None for s in stages)
        row = dict(task=task, domain=domains[task], arm=arm, repeat=repeat, run=run,
                   reward=verdict.get('reward', ''),
                   private_passed=(verdict.get('private') or {}).get('passed', ''),
                   private_collected=(verdict.get('private') or {}).get('collected', ''),
                   run_record_present=int(bool(record)), session_present=int(bool(session)),
                   status=record.get('status', 'missing_record'),
                   model=record.get('model', ''), effort=record.get('reasoning_effort', ''),
                   work_seconds=sum(s.get('work_seconds') or 0.0 for s in stages),
                   prepare_seconds=sum(s.get('work_seconds') or 0.0 for s in stages if s.get('name') == 'prepare'),
                   stage_usage_unknown=int(usage_unknown),
                   explicit_unknown_inflight=int(any((s.get('usage') or {}).get('unknown_inflight_request', False) for s in stages)),
                   old_stage_input=sum((s.get('usage') or {}).get('input_tokens') or 0 for s in stages),
                   old_stage_output=sum((s.get('usage') or {}).get('output_tokens') or 0 for s in stages),
                   trial_path=str(trial.relative_to(repo)))
        trial_calls, events = [], []
        for message in session.get('messages', []):
            u = message.get('usage')
            if u is not None:
                inp, output = u.get('prompt_tokens'), u.get('completion_tokens')
                if not isinstance(inp, int) or not isinstance(output, int):
                    raise ValueError(f'Incomplete completed-call usage: {trial}, step {message.get("step")}')
                trial_calls.append(dict(task=task, arm=arm, repeat=repeat, step=message.get('step', ''),
                                        input_tokens=inp, output_tokens=output,
                                        cached_input_tokens=u.get('prompt_cache_hit_tokens', ''),
                                        reasoning_output_tokens=(u.get('completion_tokens_details') or {}).get('reasoning_tokens', '')))
            for call in message.get('tool_calls') or []:
                f = call.get('function') or {}
                if task in ('103', '022'):
                    events.append(dict(step=message.get('step'), name=f.get('name'), arguments=f.get('arguments')))
        trial_cases = []
        if task in ('103', '022'):
            patch = trial / 'artifacts/model.patch'
            if patch.exists():
                manifest[str(patch.relative_to(repo))] = hashlib.sha256(patch.read_bytes()).hexdigest()
                pd = ROOT / 'supporting/case_patches'
                pd.mkdir(exist_ok=True)
                (pd / f'{task}_{arm}_r{repeat}.patch').write_bytes(patch.read_bytes())
            trial_cases.append(dict(task=task, arm=arm, repeat=repeat, reward=row['reward'],
                                    private_passed=row['private_passed'], private_collected=row['private_collected'],
                                    trial_path=row['trial_path'], events=events))
        return row, trial_calls, trial_cases

    def trials_of(run: str):
        """Yield (trial, task, arm) for every arm trial recorded under one run."""
        for trial in sorted((repo / 'runs' / run / 'jobs').glob('task-*/task_*')):
            _, task, raw_arm = trial.parent.name.split('-', 2)
            if raw_arm in ('baseline', 'science'):
                yield trial, task, 'cbe' if raw_arm == 'science' else 'baseline'

    entries = [collect_trial(trial, task, arm, repeat, run)
               for repeat, run in enumerate(RUNS, 1)
               for trial, task, arm in trials_of(run)]

    # Replace slots whose primary run yielded no verifier verdict.
    gaps = [i for i, (row, _, _) in enumerate(entries) if row['reward'] == '']
    if gaps:
        refills = {(task, arm): (trial, task, arm) for trial, task, arm in trials_of(RERUN)}
        for i in gaps:
            row = entries[i][0]
            key = (row['task'], row['arm'])
            if key not in refills:
                raise ValueError(f'No gap-fill trial for {key[0]}/{key[1]}')
            trial, task, arm = refills.pop(key)
            entries[i] = collect_trial(trial, task, arm, row['repeat'], RERUN)
            if entries[i][0]['reward'] == '':
                raise ValueError(f'Gap-fill run also lacks a verdict for {key[0]}/{key[1]}')
        print(f'Gap-filled {len(gaps)} slots from {RERUN}')

    attempts = [row for row, _, _ in entries]
    calls = [c for _, tc, _ in entries for c in tc]
    cases = [c for _, _, tc in entries for c in tc]
    if len(attempts) != 534:
        raise ValueError(f'Expected 534 primary attempts, found {len(attempts)}')
    if any(r['reward'] == '' for r in attempts):
        raise ValueError('Missing verifier verdicts remain after gap-fill')
    for name, rows in [('attempts.csv', attempts), ('completed_calls.csv', calls)]:
        with (out / name).open('w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0]))
            writer.writeheader(); writer.writerows(rows)
    (out / 'case_events.json').write_text(json.dumps(cases, indent=2))
    split = tracked(repo / 'configs/interactive-science.split.json')
    (out / 'split.json').write_text(json.dumps(split, indent=2))
    (out / 'original_evidence_packet.json').write_text(json.dumps(packets, indent=2))
    (out / 'source_manifest.json').write_text(json.dumps(manifest, indent=2, sort_keys=True))
    print(f'Exported {len(attempts)} attempts and {len(calls)} completed API calls. No experiments executed.')

if __name__ == '__main__':
    main()
