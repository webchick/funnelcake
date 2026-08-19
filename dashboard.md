# Funnelcake DESSERT Dashboard Plan

## Goal

Build a dashboard that answers, at progressively deeper levels:

1. **Where is the agent-mediated product journey failing?**
2. **What appears to be causing the failure?**
3. **What evidence supports that diagnosis?**
4. **Can an engineer reproduce it?**
5. **What experiment or product change would verify the suspected cause?**

Core principle:

> **No diagnosis without receipts.**

Every aggregate score should eventually drill down to the underlying trials, traces, observations, and source evidence.

---

# 1. Dashboard Information Hierarchy

Use a consistent drill-down model:

```text
DESSERT
   ↓
Stage
   ↓
Metric
   ↓
Failure cluster
   ↓
Diagnosis
   ↓
Evidence
   ↓
Trial
   ↓
Trace
   ↓
Raw observation
```

Optionally later:

```text
Raw observation
   ↓
Reproduction
   ↓
Counterfactual experiment
   ↓
Verified intervention
```

This allows different audiences to stop at the level they care about.

### Executive / CPO

> Setup is the largest leak.

### Product

> Credential acquisition and auth-doc discovery account for most Setup failures.

### Engineering

> Here are the exact failing traces, URLs, API responses, and reproduction steps.

---

# 2. Dashboard Home

The home screen should stay extremely simple.

## DESSERT Health

```text
D       E       S       S       E       R       T

72      86      61      43      78      67      58
↑8      ↑2      ↓4      ↓12     ↑5      →       ↑3

Discover
Evaluate
Select
Setup
Execute
Repeat
Trust
```

Each stage should show:

* score
* trend
* number of trials
* confidence / evidence quality where appropriate

---

## Journey Conversion

```text
Eligible intents              10,000
      ↓ 72%
Discovered                     7,200
      ↓ 86%
Correctly evaluated            6,192
      ↓ 61%
Selected                       3,777
      ↓ 43%
Setup completed                1,624
      ↓ 78%
Successful execution           1,267
      ↓ 67%
Repeated use                     849
      ↓ 58%
Trusted delegation               492
```

The largest conversion loss should be visually obvious.

---

## Biggest Leak

Example:

```text
BIGGEST LEAK

SETUP

107 / 187 trials failed before first authenticated API call.

Likely causes:

🟢 Manual credential provisioning       42 trials
🔵 Authentication docs not located      31 trials
🟡 Scope-selection confusion            18 trials
```

Clicking any cause opens the supporting evidence.

---

# 3. Evidence Grades

Every causal diagnosis gets an explicit evidence grade.

## 🟢 Confirmed

Supported by deterministic evidence and a successful reproduction or counterfactual experiment.

Example:

> Supplying the missing credential changes task success from 29% to 96%.

---

## 🔵 Strongly Supported

Repeated trace pattern across multiple independent trials, agents, or tasks.

Example:

> 31 trials failed to locate the authentication documentation and followed similar trajectories.

---

## 🟡 Hypothesis

Evidence suggests a cause, but causality has not been isolated.

Example:

> Agents may be confusing OAuth scopes because several chose insufficient permissions.

---

## ⚪ Observation

Describes what happened without explaining why.

Example:

> 18 trials returned HTTP 403.

The dashboard must distinguish observation from explanation.

---

# 4. Stage Detail Pages

Clicking a DESSERT stage opens its metrics and failure anatomy.

Example:

# Setup

```text
SETUP                                      43 / 100

Account creation success                 82%
Authentication mechanism discovered      81%
Authentication docs located              55%
Credential acquisition                   48%
Authentication success                   94%
Connection verification                  97%
```

Then:

## Failure Clusters

```text
42   Credential provisioning requires human action
31   Authentication instructions not located
18   Incorrect scopes / permissions
10   Authentication loop
 6   Other
```

Each cluster links to a diagnosis page.

---

# 5. Diagnosis Detail

Example:

## AUTH-017: Authentication docs are difficult for agents to locate

**Stage:** Setup
**Impact:** High
**Evidence grade:** 🔵 Strongly Supported
**Affected trials:** 31 / 187
**Affected agents:** 3 / 3
**Affected task families:** 8 / 10

### Observed Pattern

Agents determine that authentication is required but fail to locate instructions explaining how credentials are created.

### Supporting Evidence

```text
31 / 38 relevant trials searched documentation for auth
27 / 31 never reached the access-token documentation
25 / 27 abandoned or requested human intervention
```

### Representative Trials

```text
FC-1842   deploy-app       failed
FC-1901   create-project   failed
FC-1917   configure-env    failed
```

### Supporting Sources

```text
/docs/api
/docs/authentication
/docs/access-tokens
```

### Suggested Intervention

Link credential creation directly from API onboarding and use consistent terminology for authentication/access tokens.

Important:

This recommendation should be clearly separated from the observed evidence.

---

# 6. Trial View

Clicking a trial exposes the entire run.

Example:

## Trial FC-1842

### Task

> Create a project and deploy the example application.

### Result

❌ Failed before authenticated API access.

### Trace

```text
14:03:02  Agent searches docs for authentication
14:03:07  Opens /docs/api
14:03:11  Determines API token is required
14:03:17  Searches "create API token"
14:03:21  Opens Account Settings documentation
14:03:30  Attempts token creation
14:03:34  Interactive login required
14:03:42  Cannot proceed autonomously
14:03:45  Requests human intervention
```

### Technical Events

Include when available:

* tool calls
* HTTP requests
* HTTP status codes
* MCP calls
* API responses
* browser/navigation actions
* search queries
* errors
* retries
* human-intervention requests

### Final State Verification

Do not rely solely on the agent's claim.

Record whether the desired product state actually exists.

Example:

```text
Expected:
Project created + deployment available

Observed:
No project created

Outcome:
FAIL
```

---

# 7. Failure Cluster Model

Individual failures should be grouped into reusable failure classes.

Initial taxonomy could include:

```text
DISCOVERY
- product not surfaced
- category misunderstood
- insufficient evidence
- wrong competitor set

EVALUATE
- capability missed
- capability hallucinated
- constraints misunderstood
- outdated information

SELECT
- inappropriate competitor preferred
- incorrect differentiation
- unsupported reason for rejection

SETUP
- account creation blocker
- auth docs not found
- human credential requirement
- insufficient scope
- browser-only flow
- CAPTCHA
- unsupported integration

EXECUTE
- wrong API/tool
- invalid parameters
- opaque error
- retry loop
- incomplete task
- incorrect final state

REPEAT
- product not selected again
- task routed elsewhere
- reliability degradation

TRUST
- human correction
- rollback
- unexpected side effect
- insufficient auditability
- insufficient preview
```

The taxonomy can evolve as real failures appear.

Do not attempt to perfectly design it upfront.

---

# 8. Counterfactual Experiments

Later, Funnelcake should be able to validate likely causes by rerunning failed tasks with one controlled change.

Example:

```text
BASELINE
Task success                         29%

DIRECT AUTH DOC URL PROVIDED
Task success                         84%

VALID CREDENTIAL PROVIDED
Task success                         96%
```

Interpretation:

```text
Find documentation        major friction
Understand documentation  minor friction
Acquire credential         major friction
Use API                    little friction
```

A diagnosis can be upgraded from:

```text
🟡 Hypothesis
```

to:

```text
🟢 Confirmed
```

when experimental evidence supports it.

---

# 9. Issue-Shaped Engineering View

A diagnosis should be convertible into something resembling an engineering issue.

Example:

## AUTH-017

**Authentication instructions are not reliably discoverable from API onboarding**

### Impact

31 failures across 187 Setup trials.

### Reproduction

```text
1. Start from public API landing page.
2. Attempt to create a project using only publicly discoverable documentation.
3. Observe agent documentation search/navigation.
4. Agent fails to locate token creation instructions.
```

### Evidence

* 31 affected traces
* 3 agent implementations
* 8 task families
* direct source URLs
* HTTP/tool logs

### Suggested Fix

Link token-creation instructions directly from the API quickstart.

### Verification

Rerun:

```text
setup/auth-discovery
```

Success criterion:

```text
Auth documentation discovery ≥ 90%
```

This creates a direct path from:

```text
dashboard finding
    ↓
engineering work
    ↓
regression eval
```

---

# 10. Actor Overlay

Because DESSERT applies to human, agent, and hybrid workflows, optionally show who performs each stage.

```text
                HUMAN      SHARED      AGENT

Discover          12%         21%        67%
Evaluate          18%         39%        43%
Select            41%         47%        12%
Setup             28%         58%        14%
Execute            9%         22%        69%
Repeat             8%         17%        75%
Trust             71%         26%         3%
```

This is secondary to v0 but useful later.

---

# 11. Core Data Objects

Keep the underlying model relatively simple.

## Trial

```json
{
  "id": "FC-1842",
  "stage": "setup",
  "task": "Create project and deploy example",
  "agent": "example-agent",
  "status": "failed",
  "outcome_verified": true,
  "trace_id": "trace-1842"
}
```

## Trace Event

```json
{
  "timestamp": "...",
  "type": "navigation",
  "action": "open_url",
  "target": "/docs/authentication",
  "result": "success"
}
```

Possible event types:

```text
search
navigation
tool_call
http_request
api_response
error
retry
human_intervention
state_verification
```

## Failure

```json
{
  "trial_id": "FC-1842",
  "failure_type": "credential_human_required",
  "stage": "setup",
  "evidence_event_ids": ["..."]
}
```

## Diagnosis

```json
{
  "id": "AUTH-017",
  "title": "Authentication docs difficult to locate",
  "stage": "setup",
  "evidence_grade": "strongly_supported",
  "affected_trial_ids": ["FC-1842", "FC-1901"],
  "supporting_sources": [],
  "suggested_intervention": "..."
}
```

---

# 12. MVP Dashboard

Do **not** build the entire vision first.

The first useful dashboard only needs:

## View 1: DESSERT Overview

* seven stage scores
* stage conversion
* biggest leak
* top 3 failure clusters

## View 2: Stage Detail

* stage metrics
* failure clusters
* affected trial counts

## View 3: Diagnosis

* observed pattern
* evidence grade
* supporting numbers
* representative trials
* source URLs
* suggested intervention

## View 4: Trial Trace

* task
* result
* chronological trace
* raw technical events
* verified final state

That's enough to validate the model.

---

# 13. Explicitly Out of Scope for Dashboard v0

Do not build yet:

* automatic Jira/GitHub issue creation
* automatic counterfactual generation
* regression scheduling
* sophisticated statistical causal inference
* custom executive dashboards
* team ownership mapping
* live monitoring
* real customer telemetry
* elaborate charts
* AI-generated prioritization models
* benchmarking across hundreds of companies

---

# 14. Success Criteria

The dashboard succeeds if an engineer can start at:

> **Setup score: 43**

and, without trusting an unexplained AI judgment, drill down to:

> **31 Setup trials failed because agents could not locate authentication instructions**

then further to:

> **Here are the exact 31 trials**

then:

> **Here is exactly what happened in one representative trial**

and finally:

> **Here is the raw evidence supporting the diagnosis and a reproducible test for verifying a fix.**

The key product promise is:

> **Funnelcake doesn't just tell you where your agentic PLG journey is leaking. It shows you the receipts for why, and gives you a way to prove you've fixed it.**

