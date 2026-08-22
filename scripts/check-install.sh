#!/usr/bin/env bash
set -euo pipefail

venv_dir="${TMPDIR:-/tmp}/funnelcake-install-check"
rm -rf "$venv_dir"
python3 -m venv "$venv_dir"

export PIP_DISABLE_PIP_VERSION_CHECK=1
"$venv_dir/bin/python" -m pip install -e .

"$venv_dir/bin/funnelcake" status
"$venv_dir/bin/funnelcake" geo validate fixtures/geo/drupal-raw-collected.json --json
"$venv_dir/bin/funnelcake" telemetry normalize fixtures/telemetry/posthog-ish-events.json --mapping fixtures/telemetry/posthog-ish-mapping.yaml --out "$venv_dir/telemetry.normalized.json"
"$venv_dir/bin/funnelcake" telemetry normalize fixtures/telemetry/posthog-ish-events-current.json --mapping fixtures/telemetry/posthog-ish-mapping.yaml --out "$venv_dir/telemetry-current.normalized.json"
"$venv_dir/bin/funnelcake" telemetry inspect "$venv_dir/telemetry.normalized.json"
"$venv_dir/bin/funnelcake" collect run --collector answer-observation fixtures/geo/drupal-raw-collected.json --out "$venv_dir/geo-observations.json"
"$venv_dir/bin/funnelcake" collect run --collector mcp-inspector fixtures/collectors/mcp-inspector-auth-failed.json --out "$venv_dir/mcp-observations.json"
"$venv_dir/bin/funnelcake" collect run --collector promptfoo fixtures/collectors/promptfoo-results.json --out "$venv_dir/promptfoo-observations.json"
"$venv_dir/bin/funnelcake" collect inspect "$venv_dir/mcp-observations.json"
"$venv_dir/bin/funnelcake" filling snapshot "$venv_dir/telemetry.normalized.json" --config fixtures/telemetry/filling-config.yaml --out "$venv_dir/filling-baseline.json"
"$venv_dir/bin/funnelcake" filling snapshot "$venv_dir/telemetry-current.normalized.json" --config fixtures/telemetry/filling-config-current.yaml --out "$venv_dir/filling-current.json"
"$venv_dir/bin/funnelcake" filling compare "$venv_dir/filling-baseline.json" "$venv_dir/filling-current.json"
"$venv_dir/bin/funnelcake" dashboard-summary --filling-snapshot "$venv_dir/filling-current.json" --compare-to "$venv_dir/filling-baseline.json" --runs-dir "$venv_dir/missing-runs"
