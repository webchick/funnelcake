# Funnelcake and OpenTelemetry

Funnelcake should be understandable to people who already know OpenTelemetry.

The core rule is:

```text
Funnelcake artifacts preserve product/eval semantics.
OTLP export provides interoperability with trace tools.
```

## Trace Model

Use OpenTelemetry terms for execution data:

- trace
- span
- span event
- resource
- instrumentation scope
- attribute
- status

Funnelcake terms are layered onto those primitives:

- trial: one evaluated trace for a task
- task: the user outcome being evaluated
- checkpoint: an expected intermediate condition, usually a span event or evaluator span
- assertion: a low-level observable fact, usually a span event
- failure: a diagnosis-linked record that references trace evidence

## IDs

Use real OpenTelemetry-compatible IDs internally:

- `trace_id`: 32 lowercase hex characters, non-zero
- `span_id`: 16 lowercase hex characters, non-zero

Keep friendly Funnelcake identifiers as attributes:

```text
funnelcake.trial.id=FC-0001
funnelcake.task.family=setup/auth-discovery
```

## Required Funnelcake Attributes

Every root trial span should include:

```text
service.name=funnelcake
funnelcake.trial.id
funnelcake.stage
funnelcake.task.family
```

When known, spans and events should also include:

```text
funnelcake.actor
funnelcake.failure.type
funnelcake.assertion
funnelcake.assertion.passed
```

Funnelcake-specific attributes should stay under `funnelcake.*`.

## Existing Semantic Conventions

Use standard OpenTelemetry semantic conventions where they apply:

- HTTP and API calls should use HTTP attributes such as `http.request.method`, `http.response.status_code`, `url.full`, and `error.type`.
- Browser or documentation navigation should use URL attributes such as `url.full`.
- Exceptions should use OpenTelemetry exception attributes.
- Generic trace structure should follow OpenTelemetry span and event conventions.

OpenTelemetry semantic conventions are documented at https://opentelemetry.io/docs/specs/semconv/.

## GenAI and OpenInference

There is value in tracking OpenTelemetry GenAI conventions early. Funnelcake is explicitly about agent-mediated product journeys, so LLM calls, tool calls, retrieval, memory, and MCP interactions are first-class evidence.

However, Funnelcake should not make draft GenAI conventions required for core data validity yet. OpenTelemetry's GenAI conventions are currently managed separately from the core semantic conventions and include development-status areas. Use them where they improve interoperability, but keep Funnelcake's required contract smaller and stable.

Recommended policy:

- Use core OpenTelemetry trace concepts as the hard requirement.
- Use OpenTelemetry GenAI attributes for LLM, tool, retrieval, memory, and MCP spans when the mapping is clear.
- Use OpenInference attributes for AI observability tools such as Phoenix when they improve trace rendering.
- Keep Funnelcake outcome semantics under `funnelcake.*` so convention churn does not break captured trial evidence.

Relevant references:

- OpenTelemetry semantic conventions: https://opentelemetry.io/docs/specs/semconv/
- OpenTelemetry GenAI semantic conventions: https://github.com/open-telemetry/semantic-conventions-genai
- OpenInference specification: https://arize-ai.github.io/openinference/spec/

## Export Direction

Funnelcake should support:

```bash
funnelcake export-otlp artifacts/runs/FC-0001
funnelcake send-otlp artifacts/runs/FC-0001 --endpoint http://localhost:4318/v1/traces
```

The local run JSON remains useful for product-level evidence and dashboard summaries. OTLP JSON or OTLP protobuf should be generated from that source of truth for Phoenix, Jaeger, Tempo, Honeycomb, and OpenTelemetry Collector workflows.

## Phoenix

Phoenix is the first recommended GUI target because it understands AI-oriented traces and OpenInference attributes.

Install Funnelcake's optional Phoenix dependency:

```bash
python3 -m pip install -e '.[phoenix]'
```

Start Phoenix locally, then send a captured run:

```bash
funnelcake send-phoenix artifacts/runs/FC-0001
```

The default endpoint is:

```text
http://localhost:6006/v1/traces
```

Override it when needed:

```bash
funnelcake send-phoenix artifacts/runs/FC-0001 --endpoint https://your-phoenix.example.com/v1/traces
```

For Phoenix Cloud or authenticated deployments, pass an API key:

```bash
funnelcake send-phoenix artifacts/runs/FC-0001 --api-key "$PHOENIX_API_KEY"
```

The sender preserves Funnelcake's OpenTelemetry-compatible `trace_id` and `span_id` values so evidence references line up with the trace shown in Phoenix.
