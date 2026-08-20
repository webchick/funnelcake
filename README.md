# Funnelcake

Funnelcake is a scaffold for an agent discovery/evaluation pipeline. The initial structure follows `plan.md` and splits the work into importable packages for platform profiling, signal mining, intent extraction, benchmark building, discovery evaluation, and reporting.

Uses DESSERT metrics:

| DESSERT          | Human PLG                                                 | Agentic PLG                                                       |
| ---------------- | --------------------------------------------------------- | ----------------------------------------------------------------- |
| **D · Discover** | Human becomes aware you exist                             | Agent surfaces you for an eligible intent                         |
| **E · Evaluate** | Human reads docs/site/reviews and decides whether you fit | Agent understands capabilities, constraints and suitability       |
| **S · Select**   | Human chooses/signs up for your product                   | Agent recommends or chooses you among candidates                  |
| **S · Setup**    | Signup, onboarding, configuration, integrations           | Auth, credentials, permissions, MCP/API connection                |
| **E · Execute**  | Human reaches first value                                 | Agent successfully completes the intended task                    |
| **R · Repeat**   | Human returns and develops a habit                        | Agent repeatedly routes eligible work through you                 |
| **T · Trust**    | Human becomes comfortable depending on the product        | Human allows increasingly autonomous delegation through the agent |


## Layout

- `apps/cli`: command-line entry point.
- `packages/platform-profile`: Step 0.0 platform profile primitives.
- `packages/signal-mining`: Step 0.1 signal extraction primitives.
- `packages/intent-extraction`: Step 0.2 intent modeling primitives.
- `packages/answer-observation`: AEO/GEO answer observation primitives.
- `packages/benchmark-builder`: Step 0.3 benchmark assembly primitives.
- `packages/discover-eval`: Step 1 discovery evaluation primitives.
- `packages/reporting`: reporting output primitives.
- `shared`: schemas, LLM adapters, and web helpers shared across packages.
- `fixtures`: platform-specific sample inputs.
- `artifacts`: local run output, ignored by git.
- `specs`: design notes for benchmark grain size, OpenTelemetry alignment, and data semantics.

## Local checks

```bash
python3 -m compileall apps packages shared
FC_PYTHONPATH=apps/cli/src:packages/platform-profile/src:packages/signal-mining/src:packages/intent-extraction/src:packages/answer-observation/src:packages/benchmark-builder/src:packages/discover-eval/src:packages/reporting/src:shared
PYTHONPATH=$FC_PYTHONPATH python3 -m funnelcake_cli --help
PYTHONPATH=$FC_PYTHONPATH python3 -m funnelcake_cli dashboard-demo
PYTHONPATH=$FC_PYTHONPATH python3 -m funnelcake_cli capture-run fixtures/runs/setup-auth-docs.json
PYTHONPATH=$FC_PYTHONPATH python3 -m funnelcake_cli show-run artifacts/runs/FC-0001
PYTHONPATH=$FC_PYTHONPATH python3 -m funnelcake_cli export-otlp artifacts/runs/FC-0001
python3 -m pip install -e '.[phoenix]'
PYTHONPATH=$FC_PYTHONPATH python3 -m funnelcake_cli send-phoenix artifacts/runs/FC-0001
PYTHONPATH=$FC_PYTHONPATH python3 -m funnelcake_cli validate-task fixtures/tasks/setup-auth-discovery.json
PYTHONPATH=$FC_PYTHONPATH python3 -m funnelcake_cli observe-answers fixtures/geo/drupal-answers.json
PYTHONPATH=$FC_PYTHONPATH python3 -m funnelcake_cli run-task fixtures/tasks/setup-auth-discovery.json
PYTHONPATH=$FC_PYTHONPATH python3 -m funnelcake_cli evaluate-run fixtures/tasks/setup-auth-discovery.json artifacts/runs/FC-0001 --write
PYTHONPATH=$FC_PYTHONPATH python3 -m funnelcake_cli diagnose-run fixtures/tasks/setup-auth-discovery.json artifacts/runs/FC-0001 --write
PYTHONPATH=$FC_PYTHONPATH python3 -m funnelcake_cli show-diagnosis artifacts/runs/FC-0001 AUTH_DOCS_NOT_FOUND-001
PYTHONPATH=$FC_PYTHONPATH python3 -m funnelcake_cli run-suite fixtures/tasks
PYTHONPATH=$FC_PYTHONPATH python3 -m funnelcake_cli dashboard-summary
```

`run-suite` writes `run.json`, `evaluation.json`, and `diagnosis.json` artifacts for each task. `dashboard-summary` loads those artifacts so failure clusters can include diagnosis IDs and evidence grades.

See [specs/opentelemetry.md](specs/opentelemetry.md) for Phoenix and OTLP notes, and [specs/aeo-geo-observations.md](specs/aeo-geo-observations.md) for AEO/GEO observation schema notes.
