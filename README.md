# Funnelcake

Funnelcake is a scaffold for an agent discovery/evaluation pipeline. The initial structure follows `plan.md` and splits the work into importable packages for platform profiling, signal mining, intent extraction, benchmark building, discovery evaluation, and reporting.

## Layout

- `apps/cli`: command-line entry point.
- `packages/platform-profile`: Step 0.0 platform profile primitives.
- `packages/signal-mining`: Step 0.1 signal extraction primitives.
- `packages/intent-extraction`: Step 0.2 intent modeling primitives.
- `packages/benchmark-builder`: Step 0.3 benchmark assembly primitives.
- `packages/discover-eval`: Step 1 discovery evaluation primitives.
- `packages/reporting`: reporting output primitives.
- `shared`: schemas, LLM adapters, and web helpers shared across packages.
- `fixtures`: platform-specific sample inputs.
- `artifacts`: local run output, ignored by git.

## Local checks

```bash
python3 -m compileall apps packages shared
PYTHONPATH=apps/cli/src:packages/platform-profile/src:packages/signal-mining/src:packages/intent-extraction/src:packages/benchmark-builder/src:packages/discover-eval/src:packages/reporting/src:shared python3 -m funnelcake_cli --help
```
