ABSOLUTELY. Here’s the version I’d hand Codex and say: **“please turn this increasingly elaborate cake metaphor into software.”** 🍰

The repo is already in a good spot for this. It has DESSERT stages, trial/run/failure/diagnosis primitives, a dashboard model, and a reporting package. The current dashboard assumes every stage can be represented by a generic `"score"` derived from pass/fail trial runs, though, which is exactly the abstraction we now need to outgrow.  The current enum also still uses `REPEAT`, so we should deliberately migrate that to `RETAIN`.

# Funnelcake: DESSERT Measurement Layer

## Goal

Evolve Funnelcake from primarily an **agent-readiness eval harness** into an **agentic PLG measurement layer**.

Funnelcake should:

1. Define consistent semantics for each DESSERT stage.
2. Calculate comparable metrics regardless of the underlying telemetry provider.
3. Combine:

   * external/synthetic observations,
   * Funnelcake agent task evaluations,
   * first-party product telemetry.
4. Preserve provenance so every metric clearly states where it came from.
5. Support drill-down from:
   **metric → contributing observations/events → failures/diagnoses → evidence/traces.**
6. Produce a useful dashboard without inventing a meaningless composite “DESSERT score.”

---

# FILLING first, DESSERT diagnostics second

The product object Funnelcake should measure is the agent-mediated FILLING growth funnel:

```text
FIT
      ↓
INVESTIGATE
      ↓
LAND
      ↓
LAUNCH
      ↓
INITIAL_VALUE
      ↓
NEXT_VALUE
      ↓
GROW
```

The canonical stage identifiers are FILLING:

| FILLING       | PLG meaning       |
| ------------- | ----------------- |
| FIT           | eligible demand   |
| INVESTIGATE   | consideration     |
| LAND          | selection         |
| LAUNCH        | activation        |
| INITIAL_VALUE | first value       |
| NEXT_VALUE    | retention         |
| GROW          | paid/expansion    |

Those transitions answer the business question:

```text
Are agents helping more people discover, successfully adopt, keep using,
and ultimately pay for the product?
```

DESSERT should explain why those transitions move:

```text
Discover   Evaluate   Select
Setup      Execute    Retain
Trust
```

The funnel measures business progression. DESSERT is the diagnostic taxonomy around that progression.

Hierarchy:

```text
Business outcomes
Paid conversion · revenue · expansion · retention

↓ driven by

Product growth funnel
FIT → INVESTIGATE → LAND → LAUNCH → INITIAL_VALUE → NEXT_VALUE → GROW

↓ diagnosed through

DESSERT
Discover · Evaluate · Select · Setup · Execute · Retain · Trust
```

Product proposition:

```text
Funnelcake measures the agent-mediated product funnel from demand to revenue
and explains where and why conversion breaks.
```

Do not treat the seven DESSERT diagnostic metrics as the core data architecture.
Do not serialize product-funnel stages with verbose PLG labels when FILLING identifiers apply; keep those labels as definitions and metadata.

---

# 0. First: change Repeat → Retain

Change:

```text
D · Discover
E · Evaluate
S · Select
S · Setup
E · Execute
R · Repeat
T · Trust
```

to:

```text
D · Discover
E · Evaluate
S · Select
S · Setup
E · Execute
R · Retain
T · Trust
```

Definitions:

| Stage      | Human PLG                                        | Agentic PLG                                                                       |
| ---------- | ------------------------------------------------ | --------------------------------------------------------------------------------- |
| Discover   | User becomes aware product exists                | Agent surfaces product for an eligible intent                                     |
| Evaluate   | User understands whether product fits            | Agent correctly understands capabilities, constraints, suitability                |
| Select     | User chooses product                             | Agent appropriately recommends/chooses product                                    |
| Setup      | User completes onboarding/configuration          | Agent establishes auth, credentials, permissions, MCP/API connection              |
| Execute    | User reaches product value                       | Agent successfully completes a verified valuable task                             |
| **Retain** | Activated user repeatedly realizes product value | Activated account continues routing eligible workloads through product via agents |
| Trust      | User increasingly depends on product             | Human permits increasingly autonomous agent delegation                            |

### Migration

Rename:

```python
DessertStage.REPEAT
```

to:

```python
DessertStage.RETAIN
```

If persisted fixtures/artifacts already use `"repeat"`, support `"repeat"` as a deprecated input alias temporarily, but always emit `"retain"` in newly normalized data.

Update README/specs/fixtures/tests.

**Important:** synthetic task repetition is **not Retain**. That belongs under Execute as `execution_reliability`.

---

# 1. Stop treating every DESSERT stage as a generic score

The existing dashboard currently builds `StageMetric(name="score")` from pass/fail runs and applies those percentages sequentially to construct a funnel.

Keep this behavior available for old fixtures, but introduce stage-specific metrics.

Canonical headline metrics:

```text
discover  = eligible_intent_visibility_rate
evaluate  = fit_evaluation_accuracy
select    = appropriate_selection_rate
setup     = autonomous_setup_completion_rate
execute   = verified_task_success_rate
retain    = value_retention_rate
trust     = autonomous_workload_share
```

These are **not interchangeable generic scores**.

Create a metric registry describing each metric:

```yaml
id: autonomous_setup_completion_rate
stage: setup
label: Autonomous Setup Completion
unit: percentage

numerator:
  setup attempts completed successfully without human intervention

denominator:
  eligible setup attempts

preferred_source:
  - synthetic
  - production

diagnostics:
  - first_attempt_success_rate
  - human_intervention_rate
  - median_time_to_ready
  - credential_failure_rate
  - permission_failure_rate
```

This registry should become the semantic heart of DESSERT.

---

# 2. Introduce the Funnelcake telemetry contract

Create a canonical event model independent of Amplitude/PostHog/Segment/etc.

Suggested package:

```text
packages/
  telemetry/
    src/funnelcake_telemetry/
      models.py
      normalize.py
      validation.py
      fixtures.py
```

Do **not** cram this into the existing trace model.

The current trace model is good for evaluated execution evidence: trials, spans, assertions, failures and diagnoses.

Telemetry represents longer-lived product usage.

## Canonical `TelemetryEvent`

Something roughly like:

```python
TelemetryEvent(
    id,
    timestamp,

    event_type,

    user_id=None,
    account_id=None,
    session_id=None,

    actor=None,           # human | agent | system | unknown

    agent_provider=None,
    agent_surface=None,
    agent_id=None,

    workload_id=None,
    task_family=None,
    capability=None,

    outcome=None,         # success | failure | abandoned
    failure_type=None,

    autonomy_level=None,
    approval_required=None,
    human_intervention=None,
    intervention_type=None,

    source=None,
    source_event_id=None,
    trace_id=None,

    attributes={},
)
```

Enums should be used wherever semantics are controlled.

---

# 3. Define a tiny semantic event vocabulary

Do **not** try to normalize every product event.

Normalize only events needed to calculate DESSERT.

v0 vocabulary:

```text
setup.started
setup.completed

workload.started
workload.completed
value.realized

approval.requested
approval.granted
approval.denied

human.intervention_required
human.takeover

permission.granted
permission.revoked

rollback.performed
```

Possibly later:

```text
agent.connected
credential.created
credential.revoked
```

but don't explode the ontology prematurely.

### Important rule

Metrics are derived.

Never create nonsense events like:

```text
user.retained
user.trusted_agent
```

Instead Funnelcake derives those states from observed behavior.

---

# 4. Add telemetry provenance

Every calculated metric needs to say **how we know it**.

Do not overload the existing `EvidenceGrade`.

That currently expresses things like:

```text
confirmed
strongly_supported
hypothesis
observation
```

which serves diagnosis/evidence semantics.

Create a separate concept:

```python
class MeasurementSource:
    SYNTHETIC
    PRODUCTION

class MeasurementQuality:
    NATIVE
    MAPPED
    INFERRED
    PROXY
```

Meanings:

**Native**
: Source already emits Funnelcake-semantic data.

**Mapped**
: Explicit customer configuration maps source events to Funnelcake semantics.

**Inferred**
: Funnelcake inferred semantics from fields/user-agents/etc.

**Proxy**
: Metric approximates the desired behavior but cannot observe it directly.

Dashboard examples:

```text
Retain     57%  ↑3pp    [PRODUCTION · NATIVE]
Setup      42% ↓11pp    [SYNTHETIC · NATIVE]
Trust      31%  ↑7pp    [PRODUCTION · INFERRED]
```

---

# 5. Build the mapping layer before vendor adapters

This is the “not a pipe dream” part.

Create a generic declarative mapping format.

Example source event:

```json
{
  "event": "Deployment Succeeded",
  "user_id": "u123",
  "properties": {
    "workspaceId": "abc",
    "initiatedBy": "cursor"
  }
}
```

Mapping:

```yaml
mappings:

  - source_event: "Deployment Succeeded"

    funnelcake_event: workload.completed

    fields:
      user_id: user_id
      account_id: properties.workspaceId

    constants:
      task_family: deployment
      outcome: success

    rules:
      actor:
        if:
          field: properties.initiatedBy
          exists: true
        then: agent
        else: human
```

Result:

```json
{
  "event_type": "workload.completed",
  "user_id": "u123",
  "account_id": "abc",
  "actor": "agent",
  "task_family": "deployment",
  "outcome": "success"
}
```

### CLI

Add:

```bash
funnelcake telemetry validate mapping.yaml

funnelcake telemetry normalize \
  events.json \
  --mapping mapping.yaml \
  --out normalized.json

funnelcake telemetry inspect normalized.json

funnelcake telemetry summary normalized.json
```

Get this generic adapter working **before** touching seven vendor APIs.

---

# 6. First adapter: generic JSON/JSONL

This is v0.

Support:

```text
JSON
JSONL
CSV if trivial
```

This lets people export data from almost anything and test Funnelcake without credentials or API integrations.

Fixture data should model at least:

* human workloads
* agent workloads
* successful/failed workloads
* repeated value events
* approval events
* human intervention
* persistent permissions

This will unblock all metric work.

---

# 7. Second adapter: OpenTelemetry

This should be the first real integration because Funnelcake already speaks OTel fluently.

Current Funnelcake execution data already models traces/spans/events and exports OTLP.

Add the reverse direction:

```bash
funnelcake telemetry import-otlp traces.json
```

Map appropriate OTel events/spans to canonical telemetry.

Examples:

```text
funnelcake.actor
funnelcake.task.family
funnelcake.failure.type
funnelcake.assertion
```

already exist conceptually in Funnelcake's trace conventions.

Do not attempt to turn arbitrary OTel installations into perfect DESSERT telemetry.

Instead:

1. recognize Funnelcake-native attributes automatically;
2. allow declarative mapping for everything else.

---

# 8. Then vendor adapters

Once the canonical importer works:

```text
packages/
  integrations/
    posthog/
    amplitude/
    mixpanel/
    segment/
    rudderstack/
    snowplow/
```

BUT do these incrementally.

Suggested order:

### v1

1. OpenTelemetry
2. PostHog
3. Segment/RudderStack style events

### v1.1

4. Amplitude
5. Mixpanel

### v1.2

6. Snowplow
7. warehouse/SQL adapter

Each adapter should only do:

```text
source API/export
        ↓
raw events
        ↓
mapping
        ↓
TelemetryEvent[]
```

Absolutely **no vendor-specific DESSERT calculations**.

Otherwise we shall summon Integration Spaghetti, Ancient Enemy of Weekend Projects.

---

# 9. Create the actual DESSERT metric engine

Suggested package:

```text
packages/
  dessert-metrics/
    src/funnelcake_dessert_metrics/
      registry.py
      discover.py
      evaluate.py
      select.py
      setup.py
      execute.py
      retain.py
      trust.py
      models.py
```

Each metric should return something like:

```python
MetricResult(
    metric_id: str,
    stage: DessertStage,

    value: float | None,
    unit: MetricUnit,

    numerator: float | int | None,
    denominator: float | int | None,

    window: MeasurementWindow,
    population: PopulationDefinition,

    source: MeasurementSource,
    quality: MeasurementQuality,
    status: MetricStatus,

    contributing_event_ids: tuple[str, ...] = (),
    contributing_trial_ids: tuple[str, ...] = (),
    evidence_refs: tuple[EvidenceRef, ...] = (),

    diagnostics: dict[str, JsonValue] = {},
)
```

Do not encode unavailable, immature, or partly classified metrics as only `value=None`.
Use explicit availability status:

```text
available
unavailable
insufficient_data
partial
```

That lets the dashboard distinguish:

```text
Retain unavailable: no first-party telemetry connected.
Retain insufficient_data: 30-day retention configured; oldest activation is 18 days old.
Trust partial: only 62% of workloads can currently be classified human vs agent.
```

`MeasurementWindow` must carry both the observation period and, where needed, a relative cohort interval:

```python
MeasurementWindow(
    period_start="2026-07-01T00:00:00Z",
    period_end="2026-07-31T23:59:59Z",
    interval_type="calendar" | "cohort",
    return_interval=None | Duration(...),
)
```

`population` is not optional. It should explain the denominator in human terms, for example:

```text
accounts activated by an agent-mediated successful workload during July,
measured for four weeks after activation
```

Support comparison:

```python
MetricComparison(
    current,
    previous,
    delta,
    delta_unit="percentage_points",
)
```

---

# 10. Implement metrics in stages

Do not build DESSERT all at once.

## Phase A: metrics we can calculate today

### Discover

From existing GEO observations:

```text
eligible_intent_visibility_rate
retrieval_rate
citation_rate
visibility_consistency
```

### Select

Existing observation machinery already knows recommendation status/position.

Calculate:

```text
recommendation_rate
first_choice_rate
appropriate_selection_rate
```

`appropriate_selection_rate` requires benchmark truth to be added.

### Setup

From task runs:

```text
autonomous_setup_completion_rate
human_intervention_rate
first_attempt_success_rate
median_time_to_ready
```

### Execute

From task runs:

```text
verified_task_success_rate
eventual_success_rate
execution_reliability
human_intervention_rate
median_time_to_value
recovery_after_failure_rate
```

This gets us a real **D _ S S E _ _** dashboard before production telemetry exists.

---

# 11. Phase B: Evaluate

Evaluate requires benchmark truth.

Extend benchmark specs with:

```yaml
evaluation:
  requirements:

  expected_capabilities:

  relevant_constraints:

  disqualifying_conditions:

  acceptable_products:

  authoritative_evidence:
```

Capture structured agent evaluation:

```yaml
product:
suitable:
confidence:

capabilities:
constraints:
unsupported_requirements:
evidence:
```

Metrics:

```text
fit_evaluation_accuracy
capability_recall
constraint_accuracy
false_capability_rate
evidence_groundedness
```

Now DES becomes properly separated:

```text
Discover:
Did you appear?

Evaluate:
Did the agent understand you?

Select:
Did it choose appropriately?
```

---

# 12. Phase C: Retain

This is the first stage requiring production telemetry.

Define **critical value events** at product level:

```yaml
product:
  id: acquia

  value_events:
    - workload.completed

  qualifying_task_families:
    - content
    - deployment
    - configuration

  expected_usage_interval:
    unit: week
    value: 1
```

Do not globally assume weekly retention.

Calculate:

```text
value_retention_rate
agent_mediated_retention_rate

D1 / D7 / D30
or
W1 / W4

successful_workloads_per_account
task_family_breadth
time_between_value_events
```

Primary definition:

> Of activated accounts that achieved a qualifying value event, what percentage achieved another qualifying value event during the expected return interval?

Support cohorts.

---

# 13. Phase D: Trust

Represent Trust primarily through **observable delegation behavior**.

Define:

```text
T0 Human execution
T1 Agent advises
T2 Approval per meaningful action
T3 Approval per task
T4 Persistent scoped delegation
T5 Guardrailed autonomous operation
```

Telemetry should support:

```python
autonomy_level
approval_required
human_intervention
```

Metrics:

```text
autonomous_workload_share
delegation_level_distribution
approval_requests_per_workload
human_takeover_rate
permission_revocation_rate
rollback_rate
autonomy_level_migration
```

Pair Trust with safety.

Never present increased autonomy as intrinsically positive if:

```text
rollback_rate ↑
incorrect_action_rate ↑
human_takeover_rate ↑
```

---

# 14. Replace the current dashboard model

The current dashboard structure is a great scaffold:

```python
DashboardOverview
StageScore
ConversionStep
FailureClusterSummary
BiggestLeak
```

and already calculates biggest leaks and connects failure clusters to diagnosis IDs/evidence grades. Keep that excellent bit.

But evolve:

```python
StageScore
```

into something like:

```python
StageHealth(
    stage,
    headline_metric,
    diagnostics,
    delta,
    source,
    measurement_quality,
    biggest_driver,
)
```

And:

```python
DashboardOverview(
    stage_health,
    funnel,
    biggest_opportunity,
    top_failure_clusters,
    data_connections,
)
```

---

# 15. Dashboard Level 1: executive overview

Target output:

```text
Agentic Product Growth
Last 30 days

                    CURRENT    Δ        SOURCE

D Discover             63%    +8pp     SYNTHETIC
E Evaluate             78%    -6pp     SYNTHETIC
S Select               51%    +2pp     SYNTHETIC
S Setup                42%   -11pp     SYNTHETIC
E Execute              86%    +4pp     SYNTHETIC
R Retain               57%    +3pp     PRODUCTION
T Trust                31%    +7pp     PRODUCTION
```

Then:

```text
BIGGEST OPPORTUNITY

Setup is currently the largest constraint.

58% of attempts fail.
38% of setup failures involve credential provisioning.
Evidence: confirmed
94 affected trials

[Inspect]
```

No overall DESSERT score.

---

# 16. Important correction: don't build a fake sequential funnel yet

The existing dashboard takes one stage's percentage and multiplies the resulting count through the next stage.

That's okay for a fixture/demo.

It is **not valid production funnel math** unless stages refer to the same population/cohort.

For the new implementation:

Only render:

```text
Discover → Evaluate → Select → Setup → Execute → Retain → Trust
```

as an actual numerical conversion funnel when Funnelcake can establish shared cohort identity.

Otherwise render **stage health** rather than pretending:

```text
1,000 → 630 → 491 → 250...
```

comes from observed entities.

This deserves a test because it is exactly the kind of accidental dashboard lie that looks gorgeous.

---

# 17. Dashboard drill-down

Every stage should expose:

### Health

```text
headline metric
delta
sample size
source
measurement quality
```

### Breakdown

Dimensions such as:

```text
provider/model
task family
product capability
region
persona
agent vs human
new vs returning
```

### Why

```text
failure clusters
diagnoses
misunderstood capabilities
competitive losses
human intervention reasons
```

### Evidence

Ultimately:

```text
metric
↓
observation/event cohort
↓
trial/event
↓
diagnosis
↓
trace/source evidence
```

Existing Funnelcake already has the lower half of this ladder for run evaluation and diagnosis.

---

# 18. Add time-series snapshots

We need up/down arrows to mean something.

Store metric snapshots:

```text
measurement_runs

run_id
generated_at
period_start
period_end

metric_results[]
```

Then support:

```bash
funnelcake metrics snapshot
funnelcake metrics compare baseline.json current.json

funnelcake dashboard \
  --current current.json \
  --previous previous.json
```

Report **percentage point** changes for percentage metrics.

Don't silently report relative percentage changes.

```text
42% → 52%

correct:
+10pp

not:
+23.8%
```

unless explicitly requested.

---

# 19. Product configuration

Add something like:

```yaml
product:
  id: example-product
  name: Example Product

measurement:

  value_events:
    - deploy_application
    - publish_content

  expected_usage_interval:
    unit: week
    value: 1

  task_families:
    - deployment
    - content

  autonomy:
    supported_levels:
      - T0
      - T1
      - T2
      - T3
      - T4

telemetry:

  mapping: mappings/example.yaml
```

This makes cross-product comparisons sane because Funnelcake knows each product's definition of value.

---

# 20. Add a connection/data coverage report

Before showing metrics, Funnelcake should know what it can actually measure.

Example:

```text
DESSERT DATA COVERAGE

Discover    ✓ Funnelcake GEO
Evaluate    ✓ Benchmark evals
Select      ✓ Funnelcake GEO
Setup       ✓ Task traces
Execute     ✓ Task traces
Retain      ✓ PostHog
Trust       ◐ inferred from PostHog

Coverage: 7/7 stages

Warnings:
- Trust actor classification is inferred.
- Retain has only 19 days of history.
```

This would make setup dramatically easier and stop absent telemetry from masquerading as `0%`.

**Missing ≠ zero.**

Please encode that distinction deeply.

---

# 21. CLI shape

Eventually:

```bash
# Telemetry
funnelcake telemetry validate mapping.yaml
funnelcake telemetry normalize events.json --mapping mapping.yaml
funnelcake telemetry import-otlp traces.json
funnelcake telemetry inspect normalized.json

# Metrics
funnelcake metrics calculate
funnelcake metrics snapshot
funnelcake metrics compare baseline.json current.json

# Existing synthetic systems
funnelcake geo run ...
funnelcake run-suite ...

# Dashboard
funnelcake dashboard-summary
funnelcake dashboard-stage setup
funnelcake dashboard-stage retain
```

Backward-compatible aliases are fine.

---

# 22. Suggested implementation order

I would give Codex **this exact sequence** rather than saying “BUILD THE WHOLE THING LOL.”

### Milestone 1: semantic foundation

Implement:

* `Repeat → Retain`
* agentic product funnel stages/transitions
* metric registry
* `MetricResult`
* provenance model
* window, population, eligibility, and availability semantics
* canonical `TelemetryEvent`
* generic JSON loader
* validation
* fixtures/tests

**Done when:** Funnelcake has stable contracts for product funnel progression, DESSERT diagnostics, and telemetry; it can normalize arbitrary fixture events into canonical telemetry and calculate no production metrics yet.

### Milestone 2: real DESSERT metrics from existing data

Refactor reporting to calculate:

* Setup
* Execute

from existing Funnelcake artifacts.

Stop using generic `"score"` internally.

**Done when:** dashboard-summary produces meaningful stage-specific metrics and existing tests remain compatible.

### Milestone 3: windowed Retain and Trust

Implement:

* activation/value population definitions
* eligible workload configuration
* cohort observation windows
* Retain
* Trust

**Done when:** Retain and Trust are calculated from canonical telemetry, not synthetic task repetition.

### Milestone 4: dashboard v1

Implement:

* product funnel conversion
* DESSERT diagnostic health
* deltas
* provenance
* sample sizes
* availability status
* biggest opportunity
* failure clusters
* missing-data state

**Done when:** fixture dashboard resembles the finished executive view.

### Milestone 5: Evaluate

Add:

* benchmark truth
* fit evaluation output
* evaluator
* evaluation diagnostics

**Done when:** Funnelcake distinguishes visibility, understanding and recommendation.

### Milestone 6: production telemetry

Add:

* mapping config
* generic JSON/JSONL ingestion
* OTel import
* normalized event storage

**Done when:** production-like fixture telemetry enters the same metric system.

### Milestone 7: Retain

Implement:

* activation cohort
* expected usage interval
* critical value event
* retention calculations
* cohort view

**Done when:** Funnelcake can calculate genuine PLG retention from first-party events.

### Milestone 8: Trust

Implement:

* autonomy ladder
* delegation metrics
* safety counter-metrics
* autonomy migration

**Done when:** Trust is behaviorally measurable rather than vibes-based.

### Milestone 9: first vendor adapter

I'd pick **PostHog or Segment/RudderStack**.

Prove that the adapter layer works.

Do **not** build six integrations until one is boring.

---

# 23. Tests Codex absolutely needs to write

Especially test these semantic traps:

* missing metric ≠ `0%`
* Repeat input migrates to Retain
* synthetic repetition does not count as Retain
* failed workload does not count as realized value
* two events in one session do not necessarily mean retention
* retention respects expected usage interval
* human intervention prevents `autonomous_setup_success`
* successful task with unverified outcome does not count toward verified task success
* mapped telemetry gets `MAPPED`, not `NATIVE`
* inferred actor classification is marked `INFERRED`
* stage conversion is not calculated across incompatible populations
* percentage deltas use percentage points
* every aggregate can identify its source records
* vendor adapter output produces the same canonical records as equivalent generic JSON

---

# 24. Explicit non-goals

For this pass, **do not**:

* build a hosted SaaS
* build authentication/account management
* create an overall DESSERT score
* build every vendor integration
* build generic ETL infrastructure
* create a full CDP
* auto-discover the meaning of arbitrary customer events with an LLM
* claim cross-product comparison when definitions/populations differ
* infer causal impact from correlations
* replace OpenTelemetry/product analytics vendors

Funnelcake should be the **semantic measurement layer over them**, not eat them alive and become Snowflake wearing a tiny cake hat.

---

# 25. End-state architecture

```text
                  FUNNELCAKE

     EXTERNAL / SYNTHETIC MEASUREMENT
     ────────────────────────────────
      GEO / AEO observations
              │
      benchmark evaluation
              │
      agent task harness
              │
              ▼

        FILLING snapshots and transitions
              ▲
              │
      DESSERT diagnostics and Funnelcake semantic model
              ▲
              │
        telemetry mappings
              ▲
              │
     FIRST-PARTY PRODUCT DATA
     ────────────────────────────────
     OTel
     PostHog
     Segment
     RudderStack
     Amplitude
     Mixpanel
     Snowplow
     warehouse / generic JSON


                 ↓

       FILLING PRODUCT DASHBOARD

 FIT          INVESTIGATE
 LAND         LAUNCH
 INITIAL_VALUE
 NEXT_VALUE   GROW

       diagnosed by DESSERT

 Discover   Evaluate   Select
 Setup      Execute    Retain
 Trust

       ↓ every number drills down ↓

 metric
 event/observation cohort
 task/trial
 failure/diagnosis
 trace/raw evidence
```

## North-star design rule

Codex should use this to resolve ambiguity:

> **FILLING defines product-funnel progression. DESSERT diagnoses why it moves. Funnelcake adapters normalize where the evidence comes from. Metrics remain traceable to that evidence.**

And a second rule:

> **Never manufacture comparability by throwing away semantics.**

If Product A and Product B have compatible definitions of “value realization,” compare them.

If they don't, Funnelcake should say so rather than producing a shiny chart of lies.

That feels like a very nice next chapter for the repo. The existing reporting code is already a baby version of this, particularly the stage ordering, leak detection, failure clustering and diagnosis linkage.  So Codex is refactoring toward a clearer model, not launching into the Void with only a whisk and a dream. 🍰
