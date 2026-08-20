# AEO/GEO Answer Observations

Funnelcake answer observations capture what an answer-generation surface produced,
what evidence surrounded that answer, and enough run context to compare repeated
trials.

## Levels

1. Observation: what appeared, was recommended, or was omitted.
2. Evidence: which citations, retrieved sources, entities, and claims surrounded
   the outcome.
3. Experiment: what changed between comparable observation sets.

This package implements levels 1 and 2, plus a small level 3 comparison command.
Experiment comparison should build on these observation sets instead of using
raw answer text directly.

## Design Principles

- Evidence before scores: metrics are computed from stored observations and
  should remain traceable to raw answers, citations, and provider metadata.
- Raw observations are immutable: provider answers and raw request/response
  payloads are preserved so derived analyses can be rerun.
- Separate observation from interpretation: reports may describe correlations,
  but causal explanations stay as hypotheses or later experiments.
- Treat AI answers probabilistically: repeated runs are first-class, and
  recommendation consistency is reported as a frequency.
- Keep v0 small: JSON artifacts and CLI output come before dashboards,
  databases, provider orchestration, or hosted services.

## Standards Alignment

There is no single standard for AEO/GEO visibility observations, so the native
schema stays small and maps to existing standards where they are useful.

- OpenTelemetry GenAI semantic conventions: `engine`, `model`, `model_version`,
  `provider`, `raw_answer`, and later trace/span attributes for generation and
  search activity.
- schema.org `CreativeWork` and `citation`: generated answers and cited pages.
- schema.org `Claim` / `ClaimReview`: extracted claims about an entity.
- W3C Web Annotation Data Model: future mapping for entity mentions and claims
  anchored to answer text spans or cited resources.
- W3C PROV-O: future export for provenance between prompt, generation activity,
  model/engine, retrieved sources, and generated answer.
- WARC: future storage format only when Funnelcake archives retrieved web
  payloads, request headers, and response bodies.

## Core Fields

Each observation records:

- `prompt`
- `engine`
- `surface`
- `model`
- `model_version`
- `search_enabled`
- `country`
- `language`
- `timestamp`
- `run_number`
- `raw_answer`
- `citations`

Funnelcake adds structured `mentions`, `retrieved_sources`, and `claims` so
aggregate reports can separate visibility from supporting evidence.

## Prompt And Product Metadata

Observation sets may include a prompt corpus and product registry.

Prompts represent realistic user problems rather than SEO keywords. They can
carry optional `intent`, `persona`, `task`, `funnel_stage`, `language`,
`region`, and `tags` metadata. The optional `task` field connects discovery
observations to later executable agent evals.

Products use canonical IDs and aliases so extracted mentions can normalize
`Drupal`, `Drupal CMS`, `Drupal 11`, and similar names to one product ID.

## Initial Metrics

`geo summary` reports:

- visibility: how often the subject appeared
- recommendation rate: how often the subject was recommended
- first-choice rate: how often the subject was the first recommendation
- share of recommendation: share among recommendation appearances
- citation and retrieval counts by URL and domain
- consistency: recommendation frequency by prompt and provider

These are observational metrics. They should not be phrased as causal claims.

## Inspection

Use `inspect-observation` to drill from an aggregate metric back to one raw
observation:

```bash
funnelcake geo inspect-observation fixtures/geo/drupal-answers.json obs-001
```

Inspection prints the prompt, raw answer, model/provider metadata, product
mentions, citations, retrieved sources, extracted claims, and raw provider
payload keys. This is the v0 mechanism for keeping metrics attached to evidence.

Use `inspect-product` to drill from aggregate product visibility to every
observation where that product appeared:

```bash
funnelcake geo inspect-product fixtures/geo/drupal-answers.json drupal
```

Product inspection accepts a product ID, name, or alias from the product
registry and prints matching prompts, recommendation status, matching mentions,
citations, and claims.

Use `inspect-prompt` to drill from a prompt ID to every answer gathered for that
user problem:

```bash
funnelcake geo inspect-prompt fixtures/geo/drupal-answers.json cms-enterprise-001
```

Prompt inspection prints prompt metadata, the raw answer for each observation,
provider/model/repetition metadata, mentions, citations, and claims.

Use `inspect-domain` to drill from citation or retrieval domain summaries to
URLs, observations, and prompts:

```bash
funnelcake geo inspect-domain fixtures/geo/drupal-answers.json drupal.org
```

Domain inspection accepts a bare domain or URL and prints cited URLs, retrieved
URLs, observation IDs, prompt IDs, and prompt text.

## Comparison

Use `compare-observations` to compare two observation sets:

```bash
funnelcake geo compare baseline.json followup.json
```

Comparison reports percentage-point changes for visibility, recommendation
rate, first-choice rate, and share of recommendation. It intentionally says
these are observational deltas rather than causal claims.

The older flat commands, such as `observe-answers`, `inspect-product`, and
`compare-observations`, remain available as compatibility aliases.

## Deferred

The broader `geo.md` plan also sketches provider adapters, SQLite persistence,
provider failure handling, report/inspect subcommands, run comparison, and
manual hypotheses. Those are compatible with the current schema, but are
deferred until the JSON artifact shape and metric semantics settle.
