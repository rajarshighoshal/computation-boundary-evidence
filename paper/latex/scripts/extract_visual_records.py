#!/usr/bin/env python3
"""Read existing task metadata and full verifier summaries from an unpacked repo.

Usage: python scripts/extract_visual_records.py --repo /path/to/TUg_research_task
No repository code is imported or executed. No repair/verifier/model calls occur.
"""
from __future__ import annotations
import argparse,csv,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo',type=Path,required=True)
    args=parser.parse_args();repo=args.repo.resolve()
    if not (repo/'runs').is_dir():raise SystemExit(f'No runs directory in {repo}')
    attempts=list(csv.DictReader((ROOT/'data/attempts.csv').open(newline='')))
    manifest={}
    def read(path):
        raw=path.read_bytes()
        manifest[str(path.relative_to(repo))]=hashlib.sha256(raw).hexdigest()
        return json.loads(raw)
    metadata={}
    for path in sorted((repo/'data/release/tasks').glob('task_*/metadata.json')):
        metadata[path.parent.name.split('_')[-1]]=read(path)
    receipts=[]
    for row in attempts:
        path=repo/row['trial_path']/'verifier/reward.json'
        if not path.exists():
            if row['reward']!='':raise ValueError(f'Expected verdict absent: {path}')
            continue
        verdict=read(path)
        if int(row['reward'])!=verdict['reward']:raise ValueError(f'Reward mismatch: {path}')
        receipts.append(dict(task=row['task'],arm=row['arm'],repeat=int(row['repeat']),
                             source=str(path.relative_to(repo)),verdict=verdict))
        if row['task'] not in metadata:
            raw_arm='science' if row['arm']=='cbe' else 'baseline'
            mp=repo/'runs'/row['run']/'inputs'/f"task-{row['task']}-{raw_arm}"/f"task_{row['task']}"/'metadata.json'
            metadata[row['task']]=read(mp)
    missing=sorted({r['task']for r in attempts}-set(metadata))
    if missing:raise ValueError(f'Missing metadata: {missing}')
    for name,obj in [('task_metadata',metadata),('full_verdicts',receipts),('additional_sources',manifest)]:
        (ROOT/'data'/f'{name}.json').write_text(json.dumps(obj,indent=2))
    print(f'Read {len(receipts)} existing verdicts and {len(metadata)} task metadata records.')

if __name__=='__main__':main()
