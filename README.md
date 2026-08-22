# Funnelcake

Funnelcake measures the agent-mediated product funnel from demand to revenue and explains where and why conversion breaks. Funnelcake owns the growth model and normalized interpretation layer; native experiments and external tools supply evidence through collectors.

FILLING is the canonical product-funnel vocabulary:

```text
FIT → INVESTIGATE → LAND → LAUNCH → INITIAL_VALUE → NEXT_VALUE → GROW
```

Those stages mean eligible demand, consideration, selection, activation, first value, retention, and paid/expansion respectively.

DESSERT provides the diagnostic taxonomy around that funnel:

| DESSERT          | Human PLG                                                 | Agentic PLG                                                       |
| ---------------- | --------------------------------------------------------- | ----------------------------------------------------------------- |
| **D · Discover** | Human becomes aware you exist                             | Agent surfaces you for an eligible intent                         |
| **E · Evaluate** | Human reads docs/site/reviews and decides whether you fit | Agent understands capabilities, constraints and suitability       |
| **S · Select**   | Human chooses/signs up for your product                   | Agent recommends or chooses you among candidates                  |
| **S · Setup**    | Signup, onboarding, configuration, integrations           | Auth, credentials, permissions, MCP/API connection                |
| **E · Execute**  | Human reaches first value                                 | Agent successfully completes the intended task                    |
| **R · Retain**   | Activated user repeatedly realizes product value          | Activated account continues routing eligible workloads through you via agents |
| **T · Trust**    | Human becomes comfortable depending on the product        | Human allows increasingly autonomous delegation through the agent |

Collectors normalize native and external evidence into a shared observation contract. The metric and WHY layers should consume `Observation` records without caring whether the evidence came from Funnelcake-native answer observation, MCP Inspector output, Promptfoo later, or another tool.


## Layout

- `apps/cli`: command-line entry point.
- `packages/platform-profile`: Step 0.0 platform profile primitives.
- `packages/signal-mining`: Step 0.1 signal extraction primitives.
- `packages/intent-extraction`: Step 0.2 intent modeling primitives.
- `packages/answer-observation`: AEO/GEO answer observation primitives.
- `packages/benchmark-builder`: Step 0.3 benchmark assembly primitives.
- `packages/discover-eval`: Step 1 discovery evaluation primitives.
- `packages/telemetry`: canonical product telemetry, FILLING stage attainment, and funnel snapshots.
- `packages/collectors`: normalized evidence collector contract and adapters.
- `packages/reporting`: reporting output primitives.
- `shared`: schemas, LLM adapters, and web helpers shared across packages.
- `fixtures`: platform-specific sample inputs.
- `artifacts`: local run output, ignored by git.
- `specs`: design notes for benchmark grain size, OpenTelemetry alignment, and data semantics.

## Local checks

Install the project in editable mode before running local commands. This installs runtime dependencies such as `PyYAML`.

```bash
python3 -m pip install -e .
./scripts/check.sh
./scripts/check-install.sh
funnelcake --help
funnelcake dashboard-demo
funnelcake capture-run fixtures/runs/setup-auth-docs.json
funnelcake show-run artifacts/runs/FC-0001
funnelcake export-otlp artifacts/runs/FC-0001
funnelcake send-otlp artifacts/runs/FC-0001 --endpoint http://localhost:4318/v1/traces
python3 -m pip install -e '.[phoenix]'
funnelcake send-phoenix artifacts/runs/FC-0001
funnelcake validate-task fixtures/tasks/setup-auth-discovery.json
funnelcake geo summary fixtures/geo/drupal-answers.json
funnelcake geo summary fixtures/geo/drupal-answers.json --json
funnelcake geo inspect-observation fixtures/geo/drupal-answers.json obs-001
funnelcake geo inspect-product fixtures/geo/drupal-answers.json drupal
funnelcake geo inspect-prompt fixtures/geo/drupal-answers.json cms-enterprise-001
funnelcake geo inspect-domain fixtures/geo/drupal-answers.json drupal.org
funnelcake geo validate fixtures/geo/drupal-raw-collected.json
funnelcake geo validate fixtures/geo/drupal-raw-collected.json --json
funnelcake geo run fixtures/geo/drupal-prompts.yaml --providers fixture --repeat 2 --out artifacts/geo/drupal-fixture-corpus-run.json
funnelcake geo report artifacts/geo/drupal-fixture-corpus-run.json
OPENAI_API_KEY=... GEMINI_API_KEY=... PERPLEXITY_API_KEY=... funnelcake geo run fixtures/geo/drupal-prompts.yaml --providers openai,gemini,perplexity --repeat 5 --out artifacts/geo/drupal-real-run.json
funnelcake geo run-fixture fixtures/geo/drupal-fixture-provider.json --out artifacts/geo/drupal-fixture-run.json
OPENAI_API_KEY=... funnelcake geo run-openai fixtures/geo/drupal-openai-provider.json --out artifacts/geo/drupal-openai-run.json
GEMINI_API_KEY=... funnelcake geo run-gemini fixtures/geo/drupal-gemini-provider.json --out artifacts/geo/drupal-gemini-run.json
PERPLEXITY_API_KEY=... funnelcake geo run-perplexity fixtures/geo/drupal-perplexity-provider.json --out artifacts/geo/drupal-perplexity-run.json
funnelcake geo normalize fixtures/geo/drupal-answers.json --out artifacts/geo/drupal-answers.normalized.json
funnelcake geo normalize fixtures/geo/drupal-raw-collected.json --out artifacts/geo/drupal-raw-collected.normalized.json
funnelcake geo extract-products fixtures/geo/drupal-unextracted.json --out artifacts/geo/drupal-extracted.json
funnelcake geo import-sqlite fixtures/geo/drupal-answers.json --db data/funnelcake.db
funnelcake geo compare fixtures/geo/drupal-answers.json fixtures/geo/drupal-answers-followup.json
funnelcake geo compare fixtures/geo/drupal-answers.json fixtures/geo/drupal-answers-followup.json --json
funnelcake run-task fixtures/tasks/setup-auth-discovery.json
funnelcake evaluate-run fixtures/tasks/setup-auth-discovery.json artifacts/runs/FC-0001 --write
funnelcake diagnose-run fixtures/tasks/setup-auth-discovery.json artifacts/runs/FC-0001 --write
funnelcake show-diagnosis artifacts/runs/FC-0001 AUTH_DOCS_NOT_FOUND-001
funnelcake run-suite fixtures/tasks
funnelcake dashboard-summary
funnelcake telemetry normalize fixtures/telemetry/posthog-ish-events.json --mapping fixtures/telemetry/posthog-ish-mapping.yaml --out artifacts/telemetry/posthog-ish.normalized.json
funnelcake telemetry normalize fixtures/telemetry/posthog-ish-events-current.json --mapping fixtures/telemetry/posthog-ish-mapping.yaml --out artifacts/telemetry/posthog-ish-current.normalized.json
funnelcake telemetry inspect artifacts/telemetry/posthog-ish.normalized.json
funnelcake collect run --collector answer-observation fixtures/geo/drupal-raw-collected.json --out artifacts/collectors/geo-observations.json
funnelcake collect run --collector mcp-inspector fixtures/collectors/mcp-inspector-auth-failed.json --out artifacts/collectors/mcp-observations.json
funnelcake collect run --collector promptfoo fixtures/collectors/promptfoo-results.json --out artifacts/collectors/promptfoo-observations.json
funnelcake collect inspect artifacts/collectors/mcp-observations.json
mcp-inspector --version
funnelcake collect mcp-inspector https://example.com/mcp --raw-out artifacts/collectors/mcp-raw.json --out artifacts/collectors/mcp-observations.json
promptfoo --version
funnelcake collect promptfoo fixtures/collectors/promptfooconfig.yaml --raw-out artifacts/collectors/promptfoo-raw.json --out artifacts/collectors/promptfoo-observations.json
funnelcake filling snapshot artifacts/telemetry/posthog-ish.normalized.json --config fixtures/telemetry/filling-config.yaml --out artifacts/filling/baseline.json
funnelcake filling snapshot artifacts/telemetry/posthog-ish-current.normalized.json --config fixtures/telemetry/filling-config-current.yaml --out artifacts/filling/current.json
funnelcake filling compare artifacts/filling/baseline.json artifacts/filling/current.json
funnelcake dashboard-summary --filling-snapshot artifacts/filling/current.json --compare-to artifacts/filling/baseline.json
```

`run-suite` writes `run.json`, `evaluation.json`, and `diagnosis.json` artifacts for each task. `dashboard-summary` can lead with a saved FILLING product-funnel snapshot and then append DESSERT diagnostic run summaries so failure clusters can include diagnosis IDs and evidence grades.

The older flat AEO/GEO commands, such as `observe-answers` and `inspect-product`, remain available as compatibility aliases. Prefer the grouped `geo ...` commands for new usage.

See [specs/opentelemetry.md](specs/opentelemetry.md) for Phoenix and OTLP notes, and [specs/aeo-geo-observations.md](specs/aeo-geo-observations.md) for AEO/GEO observation schema notes.
