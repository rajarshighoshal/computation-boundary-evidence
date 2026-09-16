#!/usr/bin/env bash
# Sequential runner for locked-89 evaluation across k=1, 2, 3
set -euo pipefail
cd "$(dirname "$0")/.."

export PYTHONPATH=src
export SCICONSORT_RESTRICTED_OPTIN=1

for k in 1 2 3; do
    echo "Starting locked-89 attempt $k of 3 at $(date)"

    .venv/bin/python -m scicontext.cli pilot \
        --workspace . \
        --config "configs/deepseek-locked89-k$k.json" \
        --output "runs/deepseek-locked89-k$k-v2" \
        --execute

    echo "Finished locked-89 attempt $k of 3 at $(date)"
done
