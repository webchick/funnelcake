# Discovery Evaluator v0

## Goal

Build a small, evidence-first CLI tool for measuring how AI answer engines perceive and recommend products for realistic user problems.

The tool should answer questions such as:

- Does an AI know this product exists?
- Does it recommend the product for a given user problem?
- How often does it recommend the product?
- How consistently does that happen across repeated runs?
- What competing products are recommended?
- What sources/citations are associated with those answers?
- How do these observations change over time?

This is NOT intended to be a full GEO/AEO SaaS product.

It is the discovery/consideration component of a larger future agent-experience evaluation system:

    user problem
        ↓
    product discovery
        ↓
    product consideration
        ↓
    product selection
        ↓
    onboarding
        ↓
    task execution
        ↓
    successful outcome


# Core Design Principles

## 1. Evidence before scores

Every metric must be traceable back to the raw observations that produced it.

Never store only:

    Drupal visibility = 72%

Store the actual model responses, citations, provider metadata, timestamps, etc., and calculate metrics from those records.

## 2. Raw observations are immutable

Provider responses should be stored as received.

Derived analyses may be re-run later without re-running the original probes.

## 3. Separate observation from interpretation

The system may say:

    Drupal was recommended in 12/15 observations.

It may say:

    Drupal appeared less often when third-party comparison sites dominated citations.

It should NOT automatically say:

    Third-party comparison sites caused Drupal's visibility decline.

Causal explanations should be represented as hypotheses, not facts.

## 4. Treat AI answers probabilistically

Do not model AI recommendations as deterministic rankings.

Prefer:

    Recommended in 12/15 observations: 80%

over:

    Rank: #2

Repeated runs are a first-class concept.

## 5. Keep v0 extremely small

Prefer:

- CLI
- YAML
- SQLite
- JSON
- Markdown output
- TypeScript

Avoid:

- web dashboard
- authentication
- multi-user support
- hosted service
- queues
- vector databases
- analytics infrastructure
- complex distributed architecture


# Technology

Use:

- TypeScript
- Node.js
- SQLite
- Zod for schemas/runtime validation
- a lightweight CLI library such as Commander
- Vitest or equivalent for tests

Keep dependencies minimal.

API keys should come from environment variables.

Suggested variables:

    OPENAI_API_KEY
    GEMINI_API_KEY
    PERPLEXITY_API_KEY

Provider model names/configuration should be configurable rather than deeply hardcoded.


# Repository Structure

    discovery-evaluator/
    │
    ├── src/
    │   ├── cli/
    │   │   ├── run.ts
    │   │   ├── report.ts
    │   │   └── inspect.ts
    │   │
    │   ├── providers/
    │   │   ├── types.ts
    │   │   ├── openai.ts
    │   │   ├── gemini.ts
    │   │   └── perplexity.ts
    │   │
    │   ├── evals/
    │   │   ├── extract-products.ts
    │   │   ├── normalize-product.ts
    │   │   ├── extract-claims.ts
    │   │   └── normalize-citations.ts
    │   │
    │   ├── metrics/
    │   │   ├── visibility.ts
    │   │   ├── recommendation-rate.ts
    │   │   ├── first-choice-rate.ts
    │   │   ├── share-of-recommendation.ts
    │   │   ├── citation-share.ts
    │   │   └── consistency.ts
    │   │
    │   ├── db/
    │   │   ├── schema.ts
    │   │   ├── migrations.ts
    │   │   └── database.ts
    │   │
    │   ├── config/
    │   │   ├── prompts.ts
    │   │   └── products.ts
    │   │
    │   └── index.ts
    │
    ├── prompts/
    │   └── example.yaml
    │
    ├── products/
    │   └── example.yaml
    │
    ├── data/
    │   └── .gitkeep
    │
    ├── tests/
    │
    ├── package.json
    ├── tsconfig.json
    └── README.md


# Domain Model

## Prompt

Prompts represent realistic user problems, NOT SEO keywords.

Example:

    - id: multilingual-enterprise-cms

      prompt: >
        I need to build a website with complex editorial
        workflows and support for multiple languages.
        What platforms should I consider?

      intent: solution_discovery
      persona: developer
      task: launch_multilingual_site
      funnel_stage: discovery

      language: en
      region: ca

      tags:
        - cms
        - multilingual
        - enterprise


Schema:

    type ProbePrompt = {
      id: string
      prompt: string

      intent?: string
      persona?: string
      task?: string
      funnelStage?: string

      language?: string
      region?: string

      tags?: string[]
    }


# Product Registry

Products need canonical IDs so aliases can be normalized.

Example:

    products:

      - id: drupal
        name: Drupal

        aliases:
          - Drupal CMS
          - Drupal 11
          - Drupal.org

      - id: contentful
        name: Contentful

        aliases:
          - Contentful CMS

      - id: sanity
        name: Sanity

        aliases:
          - Sanity.io


Schema:

    type Product = {
      id: string
      name: string
      aliases: string[]
    }


# Provider Interface

All answer-engine integrations MUST normalize into one interface.

    interface AnswerEngine {
      id: string

      run(
        prompt: ProbePrompt,
        context: RunContext
      ): Promise<Observation>
    }


RunContext:

    type RunContext = {
      runId: string
      repetition: number

      language?: string
      region?: string
    }


Observation:

    type Observation = {
      id: string

      runId: string
      promptId: string

      provider: string
      model: string
      surface: string

      repetition: number

      timestamp: string

      language?: string
      region?: string

      answer: string

      citations: Citation[]

      rawRequest?: unknown
      rawResponse: unknown
    }


Citation:

    type Citation = {
      url: string
      title?: string
      domain?: string
    }


# Providers

Implement provider adapters separately.

## OpenAI

Use the Responses API with web search enabled.

Capture:

- generated answer
- model
- search citations/sources
- raw provider response

## Gemini

Use Gemini with Google Search grounding enabled.

Capture:

- generated answer
- model
- grounding metadata/citations
- raw provider response

## Perplexity

Use Sonar.

Capture:

- generated answer
- model
- citations
- raw provider response


IMPORTANT:

Provider-specific response formats must NOT leak outside the adapter.

Everything downstream consumes Observation.


# Database

Use SQLite.

At minimum create:

## runs

    id
    started_at
    completed_at

    prompt_file
    product_file

    repetitions

    providers

    config_json


## observations

    id

    run_id
    prompt_id

    provider
    model
    surface

    repetition

    timestamp

    language
    region

    answer_text

    raw_request_json
    raw_response_json


## citations

    id
    observation_id

    url
    domain
    title


## product_mentions

    id
    observation_id

    product_id
    display_name

    mentioned
    recommended

    recommendation_position

    stance

    claims_json


Indexes should exist for:

    run_id
    prompt_id
    provider
    product_id
    observation_id


# Evaluation Pipeline

Provider execution and answer evaluation MUST be separate steps.

Pipeline:

    prompt
       ↓
    answer engine
       ↓
    raw Observation stored
       ↓
    evaluator
       ↓
    structured ProductMention records
       ↓
    metrics


# Product Extraction Evaluator

Take the frozen answer text and identify product mentions.

Return structured data.

Example:

    {
      "products": [
        {
          "productId": "drupal",
          "displayName": "Drupal",
          "mentioned": true,
          "recommended": true,
          "recommendationPosition": 2,
          "stance": "positive",
          "claims": [
            "Strong multilingual support",
            "Suitable for complex editorial workflows"
          ]
        }
      ]
    }


Use constrained structured output.

Do NOT infer products that do not actually appear in the answer.

Represent stance as:

    strong_positive
    positive
    neutral
    negative
    strong_negative


# Product Normalization

Product extraction should resolve aliases through products.yaml.

Examples:

    Drupal
    Drupal CMS
    Drupal 11

all normalize to:

    drupal


Unknown products MAY be retained using a generated stable identifier.

Example:

    Adobe Experience Manager
        ↓
    adobe-experience-manager

Do not require every possible competitor to be preconfigured.


# Metrics

Implement ONLY these metrics initially.


## 1. Visibility

Question:

    How often was Product X mentioned?

Formula:

    observations mentioning product
    --------------------------------
    relevant observations


Example:

    Drupal mentioned 72/100 times

    Visibility = 72%


## 2. Recommendation Rate

Question:

    How often was Product X actually recommended?

Formula:

    observations recommending product
    ----------------------------------
    relevant observations


## 3. First Choice Rate

Question:

    How often was Product X the first recommendation?

Formula:

    observations where position = 1
    --------------------------------
    relevant observations


## 4. Share of Recommendation

Question:

    Among all product recommendation appearances,
    what share belongs to Product X?


Example:

    Contentful   31%
    Drupal       23%
    Sanity       19%
    Storyblok    14%
    Other        13%


## 5. Citation Share

Aggregate citation domains.

Example:

    reddit.com       18%
    g2.com           13%
    drupal.org       11%
    github.com        9%


Allow drill-down conceptually from:

    domain
       ↓
    URLs
       ↓
    observations
       ↓
    prompts

No UI required yet.


## 6. Consistency

Report recommendation frequency across repetitions.

Example:

    Prompt:
    multilingual-enterprise-cms

    Drupal

        OpenAI       5/5
        Gemini       4/5
        Perplexity   3/5

        Overall     12/15 = 80%


This should make clear that model outputs are probabilistic.


# CLI

Implement three primary commands.


## Run

    discovery-eval run prompts/example.yaml

Options:

    --products products/example.yaml
    --providers openai,gemini,perplexity
    --repeat 5
    --region ca
    --language en


Example output:

    Running 20 prompts
    Providers: OpenAI, Gemini, Perplexity
    Repetitions: 5

    OpenAI       100/100 ✓
    Gemini       100/100 ✓
    Perplexity   100/100 ✓

    300 observations stored.

    Run ID:
    run_2026_08_19_abc123


Provider failures should NOT destroy the entire run.

Record failures and continue where practical.


# Report

    discovery-eval report <run-id>


Default output should be readable Markdown/text.

Example:

    DISCOVERY EVALUATION

    Run: run_2026_08_19_abc123

    Observations: 300


    PRODUCT VISIBILITY

                    Seen    Recommended    #1

    Contentful       82%       71%         38%
    Drupal           73%       58%         27%
    Sanity           61%       46%         19%


    TOP CITATION DOMAINS

    reddit.com       18%
    g2.com           13%
    drupal.org       11%
    github.com        9%


    CONSISTENCY

    Drupal

        OpenAI       72%
        Gemini       63%
        Perplexity   41%


Support:

    --json

for machine-readable output.


# Inspect

Allow inspection of the actual evidence.

Examples:

    discovery-eval inspect observation <id>

    discovery-eval inspect prompt multilingual-enterprise-cms

    discovery-eval inspect product drupal --run <run-id>


Prompt inspection should show individual answers.

Example:

    Prompt:
    I need a multilingual enterprise CMS...

    OPENAI / RUN 1

    [actual model answer]

    Citations:
    - ...
    - ...


    GEMINI / RUN 1

    [actual model answer]

This feature is important.

Metrics must never become detached from evidence.


# Run Comparison

After basic reporting works, add:

    discovery-eval compare <old-run> <new-run>


Example:

    RECOMMENDATION RATE

                    BEFORE      AFTER      CHANGE

    Drupal           42%         61%        +19pp
    Contentful       71%         68%         -3pp
    Sanity           51%         48%         -3pp


Do NOT claim causation.

Use language such as:

    Recommendation rate increased by 19 percentage points.

Not:

    Documentation changes caused a 19% increase.


# Hypotheses

Optionally support manually-authored hypotheses.

Example:

    hypothesis:
      id: drupal-comparison-visibility

      statement: >
        Drupal may be underrepresented in third-party
        comparison content retrieved for enterprise
        CMS evaluation prompts.

      evidence:
        run: abc123
        prompts:
          - enterprise-cms
          - multilingual-cms


The system should NOT automatically promote correlations into hypotheses in v0.

Human creates the hypothesis.


# Experimental Support

Do NOT build a complex experiment framework yet.

But structure run metadata so future experiments are possible.

Example:

    experiment:
      id: ai-positioning-001

      hypothesis: >
        Improving explicit documentation of Acquia's
        AI capabilities will increase recommendation
        frequency for AI CMS evaluation prompts.

      baselineRun: run_001
      interventionDate: 2026-08-20
      followupRun: run_002


Run comparison already gives most of what v0 needs.


# Prompt Corpus Guidance

Provide an example corpus with approximately 10-20 prompts.

Prompts should represent user problems rather than brand queries.

Include several intent categories.


## Solution Discovery

Example:

    I need to build a multilingual website with
    complex editorial workflows. What platforms
    should I consider?


## Category Selection

Example:

    When should I choose a traditional CMS rather
    than a headless CMS?


## Product Comparison

Example:

    What are good alternatives to Contentful for
    an enterprise content platform?


## Capability Discovery

Example:

    What platforms support multilingual content,
    editorial approval workflows, and multisite
    management?


Avoid prompts such as:

    Is Drupal good?

because they test brand-conditioned answers rather than discovery.


# Future Agent-Journey Compatibility

The prompt schema MUST contain an optional:

    task

field.

Example:

    task: launch_multilingual_site


This is not used heavily in v0.

It exists so discovery scenarios can later connect to executable agent evals.


Future system:

    Scenario

      User problem:
      "I need a multilingual content platform."

      Discovery eval:
      Which products would AI consider?

      ↓

      Agent onboarding eval:
      Can the agent start using the selected product?

      ↓

      Task eval:
      Can it launch a working multilingual site?

      ↓

      Outcome:
      Did it succeed?


Do NOT implement the downstream onboarding/task evaluator in this project.


# Error Handling

Each provider call should record:

    success
    failure type
    error message
    retry count

Distinguish at least:

    provider_error
    rate_limit
    timeout
    malformed_response
    evaluator_error


Provider failures should be visible in reports.

Never silently remove failed observations from denominators without indicating this.


# Reproducibility

Each run should record:

- timestamp
- provider
- provider model name
- prompt corpus version/hash
- product registry version/hash
- repetitions
- evaluator model/version
- relevant provider configuration


This allows later investigation of:

    "Why did visibility suddenly change?"


# Testing

Unit tests should cover:

## Product normalization

    Drupal CMS → drupal
    Drupal 11 → drupal
    Contentful CMS → contentful


## Metric calculation

Use deterministic fixture observations.

Test:

- visibility
- recommendation rate
- first-choice rate
- share of recommendation
- citation share
- consistency


## Provider normalization

Mock provider responses.

Verify all adapters produce the same Observation structure.


## Evaluator parsing

Use fixed answer fixtures.

Verify:

- mentioned products
- recommendation order
- stance
- claims


No live API calls should be required to run the regular test suite.


# Fixture Mode

Add a fixture/mock provider.

Example:

    --providers fixture


This should allow:

    discovery-eval run prompts/example.yaml \
      --providers fixture \
      --repeat 3


without API keys.

This is important for development and CI.


# Implementation Order

## Phase 1: Skeleton

Build:

- TypeScript project
- CLI
- config loading
- Zod schemas
- SQLite setup
- fixture provider

Acceptance criteria:

    discovery-eval run prompts/example.yaml \
      --providers fixture

successfully creates a run and observations.


## Phase 2: Evidence Storage

Implement:

- observations
- citations
- raw response storage
- inspect command

Acceptance criteria:

Every generated observation can be inspected individually.


## Phase 3: Evaluation

Implement:

- product registry
- product extraction
- product normalization
- product_mentions storage

Acceptance criteria:

Fixture responses produce correct structured product mentions.


## Phase 4: Metrics

Implement:

- visibility
- recommendation rate
- first-choice rate
- share of recommendation
- citation share
- consistency

Acceptance criteria:

    discovery-eval report <run-id>

produces a useful Markdown report.


## Phase 5: First Real Provider

Implement OpenAI provider.

Keep provider/model configurable.

Acceptance criteria:

A real web-grounded prompt can be executed and its answer,
citations, and raw response are stored.


## Phase 6: Additional Providers

Implement:

- Gemini
- Perplexity

Acceptance criteria:

The same prompt corpus can be run across all configured providers.


## Phase 7: Run Comparison

Implement:

    discovery-eval compare

Acceptance criteria:

Two runs can be compared without claiming causal attribution.


# Explicit Non-Goals for v0

DO NOT BUILD:

- web application
- dashboard
- user accounts
- hosted database
- OAuth
- billing
- scheduling
- cron jobs
- background workers
- email reports
- Slack notifications
- vector database
- embeddings
- crawling system
- SEO keyword research
- search-volume estimation
- automatic prompt generation
- automatic causal explanations
- autonomous website optimization
- sophisticated sentiment analysis
- enterprise permission model
- browser automation
- consumer ChatGPT UI automation

If one of these seems necessary, stop and reconsider whether a
simpler implementation can satisfy the v0 requirement.


# Definition of Done

v0 is complete when I can:

1. Write a YAML file containing realistic user problems.

2. Run:

       discovery-eval run prompts.yaml \
         --providers openai,gemini,perplexity \
         --repeat 5

3. Produce persistent raw observations containing:

       prompt
       provider
       model
       timestamp
       response
       citations
       raw provider data

4. Extract product mentions and recommendations.

5. Run:

       discovery-eval report <run-id>

6. See:

       visibility
       recommendation rate
       first-choice rate
       share of recommendation
       citation share
       cross-run/provider consistency

7. Drill down from every aggregate metric to the actual
   underlying observations.

8. Compare two runs.

9. Run the complete automated test suite without making live
   external API calls.


# Final Product Principle

The tool should optimize for answering:

    "What happened, and what evidence do we have?"

rather than:

    "What number can we put on a dashboard?"

A successful v0 is boring, inspectable, reproducible, and difficult
to bullshit with.
