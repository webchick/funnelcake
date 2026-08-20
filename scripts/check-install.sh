#!/usr/bin/env bash
set -euo pipefail

venv_dir="${TMPDIR:-/tmp}/funnelcake-install-check"
rm -rf "$venv_dir"
python3 -m venv "$venv_dir"

export PIP_DISABLE_PIP_VERSION_CHECK=1
"$venv_dir/bin/python" -m pip install -e .

"$venv_dir/bin/funnelcake" status
"$venv_dir/bin/funnelcake" geo validate fixtures/geo/drupal-raw-collected.json --json
