from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from funnelcake_benchmark_builder import BenchmarkTask, load_task_spec
from funnelcake_shared import (
    EvidenceRef,
    Failure,
    Span,
    SpanKind,
    StateVerification,
    TraceEvent,
    TraceEventType,
    Trial,
    TrialRun,
    TrialStatus,
)

from .capture import validate_trial_run, write_trial_run


def run_task_spec(
    task_path: str | Path,
    artifacts_dir: str | Path = "artifacts",
    agent: str = "manual-placeholder",
) -> tuple[TrialRun, Path]:
    task = load_task_spec(task_path)
    run = build_placeholder_trial_run(task, agent)
    output_dir = write_trial_run(run, artifacts_dir)
    return run, output_dir


def build_placeholder_trial_run(task: BenchmarkTask, agent: str) -> TrialRun:
    trial_id = f"FC-{uuid4().hex[:8].upper()}"
    trace_id = uuid4().hex
    span_id = uuid4().hex[:16]
    start = datetime.now(timezone.utc).replace(microsecond=0)
    events = _checkpoint_events(task, trace_id, span_id, start)
    final_event = TraceEvent(
        id=f"event-{trial_id.lower()}-final-state",
        timestamp=_iso(start + timedelta(seconds=10 + len(events))),
        name="Placeholder final state verification",
        type=TraceEventType.STATE_VERIFICATION,
        attributes={
            "funnelcake.assertion": "placeholder_final_state",
            "funnelcake.assertion.passed": False,
            "funnelcake.runner.mode": "placeholder",
        },
        body="No real harness executed this task yet.",
    )
    all_events = (*events, final_event)
    final_ref = EvidenceRef(trace_id=trace_id, span_id=span_id, event_id=final_event.id)
    failure_ref = EvidenceRef(trace_id=trace_id, span_id=span_id, event_id=final_event.id)
    failure_type = task.failure_type_hints[0] if task.failure_type_hints else "not_executed"
    run = TrialRun(
        trial=Trial(
            id=trial_id,
            stage=task.stage,
            task=task.prompt,
            agent=agent,
            status=TrialStatus.INCONCLUSIVE,
            trace_id=trace_id,
            outcome_verified=True,
            task_family=task.task_family,
            attributes={
                "funnelcake.stage": task.stage.value,
                "funnelcake.task.id": task.id,
                "funnelcake.task.family": task.task_family or "",
                "funnelcake.runner.mode": "placeholder",
            },
        ),
        spans=(
            Span(
                id=span_id,
                trace_id=trace_id,
                name=task.name,
                start_time=_iso(start),
                end_time=_iso(start + timedelta(seconds=11 + len(events))),
                kind=SpanKind.INTERNAL,
                status_code="ERROR",
                status_message="Placeholder run did not execute a real harness.",
                attributes={
                    "funnelcake.trial.id": trial_id,
                    "funnelcake.stage": task.stage.value,
                    "funnelcake.task.id": task.id,
                    "funnelcake.task.family": task.task_family or "",
                    "funnelcake.runner.mode": "placeholder",
                    "openinference.span.kind": "EVALUATOR",
                    "service.name": "funnelcake",
                },
                events=all_events,
            ),
        ),
        final_state=StateVerification(
            expected=task.final_state.expected,
            observed="No real product state was observed; placeholder runner only emitted expected checkpoints.",
            passed=False,
            evidence=(final_ref,),
        ),
        failures=(
            Failure(
                trial_id=trial_id,
                failure_type=failure_type,
                stage=task.stage,
                summary="Placeholder runner produced a non-passing run because no real harness was executed.",
                evidence=(failure_ref,),
            ),
        ),
    )
    validate_trial_run(run)
    return run


def _checkpoint_events(
    task: BenchmarkTask,
    trace_id: str,
    span_id: str,
    start: datetime,
) -> tuple[TraceEvent, ...]:
    events: list[TraceEvent] = []
    offset = 1
    for checkpoint in task.checkpoints:
        for assertion in checkpoint.assertions:
            attributes = dict(assertion.attributes)
            attributes.update(
                {
                    "funnelcake.checkpoint.id": checkpoint.id,
                    "funnelcake.assertion": assertion.id,
                    "funnelcake.assertion.required": assertion.required,
                    "funnelcake.assertion.passed": False,
                    "funnelcake.runner.mode": "placeholder",
                    "funnelcake.trace.id": trace_id,
                    "funnelcake.span.id": span_id,
                }
            )
            events.append(
                TraceEvent(
                    id=f"event-{task.id}-{assertion.id}",
                    timestamp=_iso(start + timedelta(seconds=offset)),
                    name=assertion.description,
                    type=assertion.event_type,
                    attributes=attributes,
                    body="Expected assertion from task spec; no real observation captured yet.",
                )
            )
            offset += 1
    return tuple(events)


def _iso(timestamp: datetime) -> str:
    return timestamp.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
