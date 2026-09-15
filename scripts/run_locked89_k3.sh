#!/usr/bin/env bash
# Sequential runner for locked-89 evaluation across k=1, 2, 3
set -euo pipefail
cd /Users/rajarshighoshal/Projects/TUg_research_task

export PYTHONPATH=src
export SCICONSORT_RESTRICTED_OPTIN=1

for k in 1 2 3; do
    echo "========================================================"
    echo "Starting Locked-89 Attempt $k of 3 at $(date)"
    echo "Config: configs/deepseek-locked89-k$k.json"
    echo "Output: runs/deepseek-locked89-k$k-v1"
    echo "========================================================"
    
    .venv/bin/python -m scicontext.cli pilot \
        --workspace . \
        --config "configs/deepseek-locked89-k$k.json" \
        --output "runs/deepseek-locked89-k$k-v1" \
        --execute
        
    echo "Finished Locked-89 Attempt $k of 3 at $(date)"
    
    # Clean up Docker before next wave
    docker container prune -f || true
    docker image prune -a -f --filter "until=1h" || true
done

echo "========================================================"
echo "ALL 3 LOCKED-89 RUNS COMPLETED AT $(date)!"
echo "========================================================"
