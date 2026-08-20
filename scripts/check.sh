#!/usr/bin/env bash
set -euo pipefail

export FC_PYTHONPATH="apps/cli/src:packages/platform-profile/src:packages/signal-mining/src:packages/intent-extraction/src:packages/answer-observation/src:packages/benchmark-builder/src:packages/discover-eval/src:packages/reporting/src:shared"
export PYTHONPATH="$FC_PYTHONPATH"

python3 -m compileall apps packages shared tests
python3 -m unittest discover tests
