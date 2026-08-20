from __future__ import annotations

import json
import re
from dataclasses import asdict
from pathlib import Path
from typing import Any

from funnelcake_shared import (
    DessertStage,
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

OTEL_TRACE_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")
OTEL_SPAN_ID_PATTERN = re.compile(r"^[0-9a-f]{16}$")


def _evidence_ref(record: dict[str, Any]) -> EvidenceRef:
    return EvidenceRef(
        trace_id=record["trace_id"],
        span_id=record.get("span_id"),
        event_id=record.get("event_id"),
        source_url=record.get("source_url"),
    )


def _trace_event(record: dict[str, Any]) -> TraceEvent:
    return TraceEvent(
        id=record["id"],
        timestamp=record["timestamp"],
        name=record["name"],
        type=TraceEventType(record["type"]),
        attributes=record.get("attributes", {}),
        body=record.get("body"),
        severity_text=record.get("severity_text"),
    )


def _span(record: dict[str, Any]) -> Span:
    return Span(
        id=record["id"],
        trace_id=record["trace_id"],
        name=record["name"],
        start_time=record["start_time"],
        end_time=record["end_time"],
        parent_span_id=record.get("parent_span_id"),
        kind=SpanKind(record.get("kind", "internal")),
        status_code=record.get("status_code", "OK"),
        status_message=record.get("status_message", ""),
        attributes=record.get("attributes", {}),
        events=tuple(_trace_event(item) for item in record.get("events", [])),
    )


def load_trial_run(path: str | Path) -> TrialRun:
    with Path(path).open(encoding="utf-8") as capture_file:
        raw = json.load(capture_file)

    trial_record = raw["trial"]
    trial = Trial(
        id=trial_record["id"],
        stage=DessertStage(trial_record["stage"]),
        task=trial_record["task"],
        agent=trial_record["agent"],
        status=TrialStatus(trial_record["status"]),
        trace_id=trial_record["trace_id"],
        outcome_verified=trial_record["outcome_verified"],
        task_family=trial_record.get("task_family"),
        attributes=trial_record.get("attributes", {}),
    )
    final_state_record = raw["final_state"]
    run = TrialRun(
        trial=trial,
        spans=tuple(_span(record) for record in raw.get("spans", [])),
        final_state=StateVerification(
            expected=final_state_record["expected"],
            observed=final_state_record["observed"],
            passed=final_state_record["passed"],
            evidence=tuple(
                _evidence_ref(item) for item in final_state_record.get("evidence", [])
            ),
        ),
        failures=tuple(
            Failure(
                trial_id=record["trial_id"],
                failure_type=record["failure_type"],
                stage=DessertStage(record["stage"]),
                evidence=tuple(_evidence_ref(item) for item in record.get("evidence", [])),
                summary=record.get("summary"),
            )
            for record in raw.get("failures", [])
        ),
    )
    validate_trial_run(run)
    return run


def validate_trial_run(run: TrialRun) -> None:
    _validate_trace_id(run.trial.trace_id)
    if run.trial.trace_id not in {span.trace_id for span in run.spans}:
        raise ValueError(f"trial {run.trial.id} has no span for trace {run.trial.trace_id}")

    span_ids = {span.id for span in run.spans}
    event_ids = {event.id for span in run.spans for event in span.events}

    for span in run.spans:
        _validate_trace_id(span.trace_id)
        _validate_span_id(span.id)
        if span.parent_span_id is not None:
            _validate_span_id(span.parent_span_id)

    for failure in run.failures:
        if failure.trial_id != run.trial.id:
            raise ValueError(
                f"failure for {failure.trial_id} does not belong to trial {run.trial.id}"
            )
        for ref in failure.evidence:
            _validate_evidence_ref(ref, run.trial.trace_id, span_ids, event_ids)

    for ref in run.final_state.evidence:
        _validate_evidence_ref(ref, run.trial.trace_id, span_ids, event_ids)


def _validate_evidence_ref(
    ref: EvidenceRef,
    trace_id: str,
    span_ids: set[str],
    event_ids: set[str],
) -> None:
    _validate_trace_id(ref.trace_id)
    if ref.trace_id != trace_id:
        raise ValueError(f"evidence trace {ref.trace_id} does not match trial trace {trace_id}")
    if ref.span_id is not None and ref.span_id not in span_ids:
        raise ValueError(f"evidence span {ref.span_id} was not found")
    if ref.event_id is not None and ref.event_id not in event_ids:
        raise ValueError(f"evidence event {ref.event_id} was not found")


def _validate_trace_id(trace_id: str) -> None:
    if not OTEL_TRACE_ID_PATTERN.match(trace_id) or trace_id == "0" * 32:
        raise ValueError(f"trace_id must be a non-zero 32-character lowercase hex value: {trace_id}")


def _validate_span_id(span_id: str) -> None:
    if not OTEL_SPAN_ID_PATTERN.match(span_id) or span_id == "0" * 16:
        raise ValueError(f"span_id must be a non-zero 16-character lowercase hex value: {span_id}")


def write_trial_run(run: TrialRun, artifacts_dir: str | Path) -> Path:
    run_dir = Path(artifacts_dir) / "runs" / run.trial.id
    run_dir.mkdir(parents=True, exist_ok=True)
    payload = asdict(run)

    for filename, content in {
        "run.json": payload,
        "trial.json": payload["trial"],
        "spans.json": payload["spans"],
        "final_state.json": payload["final_state"],
        "failures.json": payload["failures"],
    }.items():
        with (run_dir / filename).open("w", encoding="utf-8") as output_file:
            json.dump(content, output_file, indent=2)
            output_file.write("\n")

    return run_dir


def load_trial_run_artifact(path: str | Path) -> TrialRun:
    artifact_path = Path(path)
    if artifact_path.is_dir():
        artifact_path = artifact_path / "run.json"
    return load_trial_run(artifact_path)


def format_trial_run(run: TrialRun) -> str:
    lines = [
        f"Trial {run.trial.id}",
        f"stage={run.trial.stage.value}",
        f"task={run.trial.task}",
        f"agent={run.trial.agent}",
        f"status={run.trial.status.value}",
        f"trace_id={run.trial.trace_id}",
        "",
        "Final State",
        f"expected={run.final_state.expected}",
        f"observed={run.final_state.observed}",
        f"passed={run.final_state.passed}",
    ]

    if run.failures:
        lines.extend(["", "Failures"])
        for failure in run.failures:
            lines.append(f"- {failure.failure_type}: {failure.summary or 'No summary'}")
            for ref in failure.evidence:
                lines.append(f"  evidence={_format_evidence_ref(ref)}")

    lines.extend(["", "Trace"])
    for span in sorted(run.spans, key=lambda item: item.start_time):
        lines.append(
            f"[{span.start_time} -> {span.end_time}] "
            f"{span.name} status={span.status_code}"
        )
        if span.status_message:
            lines.append(f"  status_message={span.status_message}")
        for event in sorted(span.events, key=lambda item: item.timestamp):
            lines.append(f"  {event.timestamp}  {event.type.value}  {event.name}")
            if event.body is not None:
                lines.append(f"    body={event.body}")
            for key, value in sorted(event.attributes.items()):
                lines.append(f"    {key}={value}")

    return "\n".join(lines)


def _format_evidence_ref(ref: EvidenceRef) -> str:
    parts = [f"trace_id={ref.trace_id}"]
    if ref.span_id is not None:
        parts.append(f"span_id={ref.span_id}")
    if ref.event_id is not None:
        parts.append(f"event_id={ref.event_id}")
    if ref.source_url is not None:
        parts.append(f"source_url={ref.source_url}")
    return " ".join(parts)
