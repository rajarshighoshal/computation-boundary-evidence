#!/bin/zsh
# Full-benchmark launch pipeline: v5 completion -> commit -> Docker CPU bump
# -> preflight two unseen tasks -> launch full-119 -> monitors.
# Each stage logs; any failure aborts with a clear marker for inspection.
set -u
cd /Users/rajarshighoshal/Projects/TUg_research_task
LOG() { print -r -- "[$(date +%H:%M:%S)] $*"; }

# --- Stage 1: wait for v5 completion (all attempts finalized) ---
LOG "stage 1: waiting for dev-five-v5 completion"
while true; do
  DONE=$(.venv/bin/python - <<'EOF'
import json, sys
s = json.load(open('runs/dev-five-v5/schedule.json'))
final = all(i['status'] in ('completed', 'infrastructure_failure') for i in s['schedule'])
infrastructure = sum(1 for i in s['schedule'] if i['status'] == 'infrastructure_failure')
print(f"{final} {infrastructure}")
EOF
)
  set -- ${(z)DONE}
  if [ "$1" = "True" ]; then LOG "v5 finished (infra failures: $2)"; break; fi
  sleep 120
done

# --- Stage 2: commit staged work ---
LOG "stage 2: committing staged changes"
git add src/scicontext/deepseek_agent.py src/scicontext/cli.py tests/test_parallel_cli.py \
        configs/full-119.json configs/full-119.selection.json data/full-119-release.json \
        scripts/cost_report.py scripts/preflight.py scripts/monitor_attempt.py scripts/autopsy_attempt.py \
        data/selections/full-119 .cache/benchmark-repo 2>/dev/null
git commit -q -m "Full-benchmark launch kit: 119-task materialization, receipt, config; cache-preserving compaction; per-pair image cleanup; cost/preflight/monitor tooling" \
  && LOG "committed $(git rev-parse --short HEAD)" || LOG "WARN: commit step reported nothing to commit"

# --- Stage 3: Docker CPUs 4 -> 8 and restart ---
LOG "stage 3: bumping Docker VM CPUs to 8 and restarting Docker"
SETTINGS="$HOME/Library/Group Containers/group.com.docker/settings.json"
.venv/bin/python - "$SETTINGS" <<'EOF'
import json, sys
path = sys.argv[1]
settings = json.load(open(path))
settings["cpus"] = 8
json.dump(settings, open(path, "w"), indent=2)
print("cpus set to 8")
EOF
osascript -e 'quit app "Docker"' 2>/dev/null
sleep 10
open -a Docker
LOG "waiting for docker daemon"
for i in $(seq 1 60); do
  docker info > /dev/null 2>&1 && break
  sleep 5
done
docker info --format 'daemon up: CPUs {{.NCPU}} | Mem {{.MemTotal}}' && LOG "docker restarted" || { LOG "ABORT: docker did not come up"; exit 1; }

# --- Stage 4: preflight two unseen tasks (extraction-only, sequential) ---
LOG "stage 4: preflight 016 and 030"
for TID in 016 030; do
  .venv/bin/python - "$TID" <<'EOF'
import json, sys, hashlib
from pathlib import Path
tid = sys.argv[1]
config = json.load(open('configs/full-119.json'))
config.update({"task_ids": [tid], "condition_order": {tid: ["science"]}, "conditions": ["science"],
               "concurrency": 1, "study_kind": f"preflight_{tid}"})
manifest = {"task_ids": [tid], "condition_order": {tid: ["science"]}, "count": 1}
Path(f'configs/preflight-{tid}.selection.json').write_text(json.dumps(manifest, indent=1))
config["sampling_manifest"] = f"configs/preflight-{tid}.selection.json"
config["sampling_manifest_sha256"] = hashlib.sha256(Path(f'configs/preflight-{tid}.selection.json').read_bytes()).hexdigest()
Path(f'configs/preflight-{tid}.json').write_text(json.dumps(config, indent=1, sort_keys=True))
EOF
  .venv/bin/python scripts/preflight.py "$TID" --config "configs/preflight-$TID.json" --output "runs/preflight-$TID" \
    && LOG "preflight $TID PASS" || { LOG "ABORT: preflight $TID FAIL"; exit 1; }
done

# --- Stage 5: launch the full 119-task run ---
LOG "stage 5: launching full-119 (concurrency 8)"
rm -rf runs/full-119
.venv/bin/python -m scicontext.cli pilot --workspace . --config configs/full-119.json --output runs/full-119 --execute \
  > workspace/full-119-launch.log 2>&1 &
LAUNCH_PID=$!
LOG "full-119 pilot launched (pid $LAUNCH_PID)"

# --- Stage 6: monitors ---
LOG "stage 6: monitors attached"
sleep 120
nohup .venv/bin/python -u scripts/monitor_attempt.py runs/full-119 --interval 300 > workspace/full-119-monitor.log 2>&1 &
LOG "pipeline complete; full run in flight"
