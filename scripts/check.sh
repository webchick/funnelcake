#!/usr/bin/env bash
set -euo pipefail

export FC_PYTHONPATH="apps/cli/src:packages/platform-profile/src:packages/signal-mining/src:packages/intent-extraction/src:packages/answer-observation/src:packages/benchmark-builder/src:packages/discover-eval/src:packages/telemetry/src:packages/collectors/src:packages/reporting/src:shared"
export PYTHONPATH="$FC_PYTHONPATH"

python3 - <<'PY'
try:
    import yaml  # noqa: F401
except ModuleNotFoundError:
    raise SystemExit(
        "Missing project dependency PyYAML. Run `python3 -m pip install -e .` "
        "before `./scripts/check.sh`, or use `./scripts/check-install.sh` "
        "to verify a fresh install."
    )
PY

python3 -m compileall apps packages shared tests
python3 -m unittest discover tests
