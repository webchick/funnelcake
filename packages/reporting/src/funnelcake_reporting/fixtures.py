from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from funnelcake_shared import (
    DessertStage,
    Diagnosis,
    EvidenceGrade,
    EvidenceRef,
    Failure,
    Span,
    SpanKind,
    StageMetric,
    TraceEvent,
    TraceEventType,
    Trial,
    TrialStatus,
)


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


def load_dashboard_fixture(path: str | Path) -> dict[str, Any]:
    with Path(path).open(encoding="utf-8") as fixture_file:
        raw = json.load(fixture_file)

    return {
        "eligible_count": raw["eligible_count"],
        "metrics": tuple(
            StageMetric(
                stage=DessertStage(record["stage"]),
                name=record["name"],
                score=record["score"],
                numerator=record.get("numerator"),
                denominator=record.get("denominator"),
                evidence=tuple(_evidence_ref(item) for item in record.get("evidence", [])),
            )
            for record in raw.get("metrics", [])
        ),
        "trials": tuple(
            Trial(
                id=record["id"],
                stage=DessertStage(record["stage"]),
                task=record["task"],
                agent=record["agent"],
                status=TrialStatus(record["status"]),
                trace_id=record["trace_id"],
                outcome_verified=record["outcome_verified"],
                task_family=record.get("task_family"),
                attributes=record.get("attributes", {}),
            )
            for record in raw.get("trials", [])
        ),
        "spans": tuple(
            Span(
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
            for record in raw.get("spans", [])
        ),
        "failures": tuple(
            Failure(
                trial_id=record["trial_id"],
                failure_type=record["failure_type"],
                stage=DessertStage(record["stage"]),
                evidence=tuple(_evidence_ref(item) for item in record.get("evidence", [])),
                summary=record.get("summary"),
            )
            for record in raw.get("failures", [])
        ),
        "diagnoses": tuple(
            Diagnosis(
                id=record["id"],
                title=record["title"],
                stage=DessertStage(record["stage"]),
                evidence_grade=EvidenceGrade(record["evidence_grade"]),
                affected_trial_ids=tuple(record.get("affected_trial_ids", [])),
                observed_pattern=record["observed_pattern"],
                supporting_sources=tuple(record.get("supporting_sources", [])),
                suggested_intervention=record.get("suggested_intervention"),
                evidence=tuple(_evidence_ref(item) for item in record.get("evidence", [])),
            )
            for record in raw.get("diagnoses", [])
        ),
    }
