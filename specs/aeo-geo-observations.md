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
Use `--json` when another tool needs the summary as structured data.

## Normalization

Collected answer-engine output should be normalized before analysis:

```bash
funnelcake geo normalize raw-observations.json --out observations.normalized.json
```

Normalization loads the accepted observation-set shape, applies canonical field
names and defaults, validates required identifiers, and writes the canonical JSON
shape consumed by summary, inspection, and comparison commands. Raw provider
request/response payloads should remain in `raw_request` and `raw_response` so
later analysis can be rerun without repeating the original probes.

The loader accepts common collected-output aliases such as `subjectEntity`,
`subjectProductId`, `promptId`, `runId`, `modelVersion`, `searchEnabled`,
`runNumber`, `answer`, `rawRequest`, `rawResponse`, `productId`,
`recommendationPosition`, `retrievedSources`, and `sourceUrls`. See
`fixtures/geo/drupal-raw-collected.json` for a minimal raw-to-normalized
example.

## Validation

Use validation before normalizing or reporting on newly collected observations:

```bash
funnelcake geo validate raw-observations.json
```

Hard validation errors fail the file when required identifiers, prompts, or
observations are missing. Warnings flag evidence-quality issues that may still
analyze successfully, such as missing model/provider metadata, empty raw
answers, observations without mentions, citations, or search retrievals, and
product/prompt references that are not in the local registries. Use `--json`
when another tool needs the validation report as structured data.

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
Use `--json` when another tool needs the comparison as structured data.

The older flat commands, such as `observe-answers`, `inspect-product`, and
`compare-observations`, remain available as compatibility aliases.

## SQLite Import

Use SQLite import when repeated runs need to be queried outside a single JSON
file:

```bash
funnelcake geo import-sqlite observations.json --db data/funnelcake.db
```

The importer writes `runs`, `observations`, `citations`, `retrieved_sources`,
and `product_mentions` tables. Raw provider request and response payloads stay
attached to `observations` as JSON text so stored records can still be traced
back to the original evidence.

## Product Extraction

Use deterministic product extraction when raw observations contain answer text
and a product registry but do not yet have structured mentions:

```bash
funnelcake geo extract-products raw-observations.json --out extracted-observations.json
```

The v0 extractor scans frozen answer text for configured product names and
aliases. It is conservative: it does not invent products outside the registry,
and it only marks a product as recommended when the text near the product
contains recommendation language. Provider execution and product extraction
remain separate steps so extracted structure can be improved without rerunning
the original probes.

## Fixture Provider Runs

Use the fixture provider to exercise the v0 execution boundary without API
keys:

```bash
funnelcake geo run-fixture fixture-provider.json --out raw-observations.json
funnelcake geo extract-products raw-observations.json --out extracted-observations.json
funnelcake geo summary extracted-observations.json
```

The fixture provider accepts prompts, products, and predefined answers, then
emits raw observations with provider/model/run metadata and raw request/response
payloads. Live answer-engine adapters should produce the same observation-set
shape.

## Combined Provider Runs

Use a YAML or JSON prompt corpus to run the same prompts across configured
providers and repetitions:

```bash
funnelcake geo run prompts.yaml --providers openai,gemini,perplexity --repeat 5 --out raw-observations.json
funnelcake geo report raw-observations.json
```

Each provider/prompt/repetition produces one observation. Provider errors are
recorded as failed observations with `failure_type=provider_error` and
`error_message`, so one missing or failing provider does not destroy the whole
run. The command preserves raw provider payloads, then runs deterministic product
mention extraction before writing the observation set.

## OpenAI Provider Runs

Use the OpenAI provider to collect real answer observations through the
Responses API:

```bash
OPENAI_API_KEY=... funnelcake geo run-openai openai-provider.json --out raw-observations.json
funnelcake geo extract-products raw-observations.json --out extracted-observations.json
```

The v0 OpenAI adapter sends each prompt to `/v1/responses`, stores the raw
provider response, captures `output_text` or message text as `raw_answer`, and
extracts URL annotations as citations when present. If `search_enabled` is true
in the provider config, the request includes the hosted web search tool.

## Gemini Provider Runs

Use the Gemini provider to collect grounded Generate Content observations:

```bash
GEMINI_API_KEY=... funnelcake geo run-gemini gemini-provider.json --out raw-observations.json
```

The v0 Gemini adapter sends each prompt to `models.generateContent`, stores the
raw provider response, captures `candidates[0].content.parts[*].text` as
`raw_answer`, and maps `groundingMetadata.groundingChunks[*].web` into
Funnelcake citations and retrieved sources. When `search_enabled` is true in the
provider config, the request includes the `google_search` grounding tool.

## Perplexity Provider Runs

Use the Perplexity provider to collect Sonar observations:

```bash
PERPLEXITY_API_KEY=... funnelcake geo run-perplexity perplexity-provider.json --out raw-observations.json
```

The v0 Perplexity adapter sends each prompt to `/v1/sonar`, stores the raw
provider response, captures `choices[0].message.content` as `raw_answer`, and
maps top-level `citations` and `search_results` into Funnelcake citations and
retrieved sources.

## Deferred

Manual hypothesis tracking remains deferred. The v0 CLI now covers local
fixtures, OpenAI, Gemini, Perplexity, SQLite import, report/inspect subcommands,
provider failure records, and run comparison.
