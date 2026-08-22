from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from funnelcake_shared import JsonValue, Span, SpanKind, TraceEvent, TrialRun

SPAN_KIND_TO_OTLP = {
    SpanKind.INTERNAL: "SPAN_KIND_INTERNAL",
    SpanKind.CLIENT: "SPAN_KIND_CLIENT",
    SpanKind.SERVER: "SPAN_KIND_SERVER",
    SpanKind.PRODUCER: "SPAN_KIND_PRODUCER",
    SpanKind.CONSUMER: "SPAN_KIND_CONSUMER",
}

STATUS_CODE_TO_OTLP = {
    "OK": "STATUS_CODE_OK",
    "ERROR": "STATUS_CODE_ERROR",
}


def trial_run_to_otlp_json(run: TrialRun) -> dict[str, Any]:
    resource_attributes = {
        "service.name": "funnelcake",
        "funnelcake.trial.id": run.trial.id,
        "funnelcake.stage": run.trial.stage.value,
        "funnelcake.task.family": run.trial.task_family or "",
    }

    return {
        "resourceSpans": [
            {
                "resource": {
                    "attributes": _attributes(resource_attributes),
                },
                "scopeSpans": [
                    {
                        "scope": {
                            "name": "funnelcake.discover_eval",
                            "version": "0.1.0",
                        },
                        "spans": [_span_to_otlp(span, run) for span in run.spans],
                    }
                ],
            }
        ]
    }


def write_otlp_json(run: TrialRun, output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as output_file:
        json.dump(trial_run_to_otlp_json(run), output_file, indent=2)
        output_file.write("\n")
    return path


def send_run_to_otlp(
    run: TrialRun,
    endpoint: str,
    *,
    api_key: str | None = None,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    payload = json.dumps(trial_run_to_otlp_json(run)).encode("utf-8")
    request_headers = {
        "Content-Type": "application/json",
        "User-Agent": "funnelcake/0.1.0",
    }
    if api_key:
        request_headers["Authorization"] = f"Bearer {api_key}"
    request_headers.update(headers or {})

    request = urllib.request.Request(
        endpoint,
        data=payload,
        headers=request_headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return {
                "trial_id": run.trial.id,
                "trace_id": run.trial.trace_id,
                "endpoint": endpoint,
                "status": response.status,
                "reason": response.reason,
                "content_type": request_headers["Content-Type"],
            }
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OTLP endpoint rejected payload: {exc.code} {exc.reason}: {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Could not reach OTLP endpoint at {endpoint}: {exc.reason}") from exc


def _span_to_otlp(span: Span, run: TrialRun) -> dict[str, Any]:
    attributes = dict(span.attributes)
    if span.trace_id == run.trial.trace_id and span.parent_span_id is None:
        attributes.update(_trial_attributes(run))

    payload: dict[str, Any] = {
        "traceId": span.trace_id,
        "spanId": span.id,
        "name": span.name,
        "kind": SPAN_KIND_TO_OTLP[span.kind],
        "startTimeUnixNano": _unix_nano(span.start_time),
        "endTimeUnixNano": _unix_nano(span.end_time),
        "attributes": _attributes(attributes),
        "events": [_event_to_otlp(event) for event in span.events],
        "status": {
            "code": STATUS_CODE_TO_OTLP.get(span.status_code, "STATUS_CODE_UNSET"),
            "message": span.status_message,
        },
    }

    if span.parent_span_id is not None:
        payload["parentSpanId"] = span.parent_span_id

    return payload


def _event_to_otlp(event: TraceEvent) -> dict[str, Any]:
    attributes = dict(event.attributes)
    attributes["funnelcake.event.id"] = event.id
    attributes["funnelcake.event.type"] = event.type.value
    if event.body is not None:
        attributes["funnelcake.event.body"] = event.body
    if event.severity_text is not None:
        attributes["funnelcake.event.severity_text"] = event.severity_text

    return {
        "timeUnixNano": _unix_nano(event.timestamp),
        "name": event.name,
        "attributes": _attributes(attributes),
    }


def _trial_attributes(run: TrialRun) -> dict[str, JsonValue]:
    attributes: dict[str, JsonValue] = dict(run.trial.attributes)
    attributes.update(
        {
            "service.name": "funnelcake",
            "funnelcake.trial.id": run.trial.id,
            "funnelcake.stage": run.trial.stage.value,
            "funnelcake.task": run.trial.task,
            "funnelcake.task.family": run.trial.task_family or "",
            "funnelcake.actor": run.trial.agent,
            "funnelcake.agent": run.trial.agent,
            "funnelcake.trial.status": run.trial.status.value,
            "funnelcake.outcome.verified": run.trial.outcome_verified,
            "funnelcake.final_state.expected": run.final_state.expected,
            "funnelcake.final_state.observed": run.final_state.observed,
            "funnelcake.final_state.passed": run.final_state.passed,
            "funnelcake.failure.count": len(run.failures),
        }
    )
    if run.failures:
        attributes["funnelcake.failure.types"] = [
            failure.failure_type for failure in run.failures
        ]
    return attributes


def _attributes(attributes: dict[str, JsonValue]) -> list[dict[str, Any]]:
    return [
        {
            "key": key,
            "value": _any_value(value),
        }
        for key, value in sorted(attributes.items())
        if value is not None
    ]


def _any_value(value: JsonValue) -> dict[str, Any]:
    if isinstance(value, bool):
        return {"boolValue": value}
    if isinstance(value, int):
        return {"intValue": str(value)}
    if isinstance(value, float):
        return {"doubleValue": value}
    if isinstance(value, str):
        return {"stringValue": value}
    if isinstance(value, list):
        return {"arrayValue": {"values": [_any_value(item) for item in value]}}
    if isinstance(value, dict):
        return {
            "kvlistValue": {
                "values": [
                    {"key": key, "value": _any_value(item)}
                    for key, item in sorted(value.items())
                ]
            }
        }
    return {"stringValue": ""}


def _unix_nano(timestamp: str) -> str:
    normalized = timestamp.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return str(int(parsed.timestamp() * 1_000_000_000))
