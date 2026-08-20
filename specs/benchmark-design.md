# Funnelcake Benchmark Design

## Grain Size

Benchmark tasks should be the smallest independently valuable user outcome, not the smallest observable product action.

Use:

- journeys to measure overall success
- tasks to measure product capability
- checkpoints and assertions to diagnose failure

This keeps Funnelcake aligned with task-specific eval practice: evaluate realistic product outcomes, then use lower-level observations to explain why an outcome succeeded or failed.

## Definitions

### Journey

A journey is an end-to-end user or agent-mediated product path that may span multiple DESSERT stages.

Example:

```text
Launch a new website on Platform X.
```

Journeys answer whether the product journey works as a whole.

### Task

A task is the smallest independently valuable user outcome within a journey.

Examples:

```text
Create a new piece of content with title, body, author, and publish state.
Create an API token with the scopes required to deploy an example application.
Deploy the example application and verify the public URL responds successfully.
```

Tasks answer whether the product supports a concrete capability.

### Checkpoint

A checkpoint is an intermediate condition that should become true during a task.

Examples:

```text
Authentication documentation was located.
The agent identified the required OAuth scopes.
The deployment command returned a success response.
```

Checkpoints help localize progress and failure.

### Assertion

An assertion is a low-level observable fact used to verify behavior or diagnose failure.

Examples:

```text
The agent clicked the Foo button.
The browser navigated to /docs/authentication.
The API returned HTTP 403 with error type insufficient_scope.
```

Assertions are excellent trace evidence, but they are usually not benchmark tasks on their own.

## Examples

```text
Launch a new website on Platform X
```

Good journey. It is valuable, realistic, and broad enough to measure overall success.

```text
Create a new piece of content
```

Good task once concretely specified with content type, required fields, expected state, and final verification.

```text
Click the Foo button
```

Usually not a task. This is a good trace assertion when clicking the button is evidence inside a larger task.

## Modeling Rule

Funnelcake should store assertions and checkpoints as trace events, span attributes, or evidence references. Tasks and journeys should remain outcome-oriented so dashboard scores describe meaningful product capability rather than UI mechanics.
