# AEO/GEO Answer Observations

Funnelcake answer observations capture what an answer-generation surface produced,
what evidence surrounded that answer, and enough run context to compare repeated
trials.

## Levels

1. Observation: what appeared, was recommended, or was omitted.
2. Evidence: which citations, retrieved sources, entities, and claims surrounded
   the outcome.
3. Experiment: what changed between comparable observation sets.

This package implements levels 1 and 2. Experiment comparison should build on
these observation sets instead of using raw answer text directly.

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
