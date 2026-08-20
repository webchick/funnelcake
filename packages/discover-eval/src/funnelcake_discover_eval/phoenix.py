from __future__ import annotations

import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from funnelcake_shared import JsonValue, SpanKind, TrialRun

from .capture import load_trial_run_artifact
from .otlp import _trial_attributes, _unix_nano

SPAN_KIND_TO_PROTO = {
    SpanKind.INTERNAL: 1,
    SpanKind.SERVER: 2,
    SpanKind.CLIENT: 3,
    SpanKind.PRODUCER: 4,
    SpanKind.CONSUMER: 5,
}

STATUS_CODE_TO_PROTO = {
    "OK": 1,
    "ERROR": 2,
}


class PhoenixDependencyError(RuntimeError):
    pass


def send_run_to_phoenix(
    path: str | Path,
    endpoint: str = "http://localhost:6006/v1/traces",
    project_name: str = "funnelcake",
    api_key: str | None = None,
) -> dict[str, Any]:
    run = load_trial_run_artifact(path)
    payload = trial_run_to_otlp_protobuf(run, project_name)
    headers = {
        "Content-Type": "application/x-protobuf",
        "User-Agent": "funnelcake/0.1.0",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    request = urllib.request.Request(
        endpoint,
        data=payload,
        headers=headers,
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
            }
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Phoenix rejected OTLP payload: {exc.code} {exc.reason}: {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Could not reach Phoenix at {endpoint}: {exc.reason}") from exc


def trial_run_to_otlp_protobuf(run: TrialRun, project_name: str = "funnelcake") -> bytes:
    try:
        from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import (
            ExportTraceServiceRequest,
        )
        from opentelemetry.proto.common.v1.common_pb2 import (
            AnyValue,
            ArrayValue,
            InstrumentationScope,
            KeyValue,
            KeyValueList,
        )
        from opentelemetry.proto.resource.v1.resource_pb2 import Resource
        from opentelemetry.proto.trace.v1.trace_pb2 import ResourceSpans, ScopeSpans, Span, Status
    except ModuleNotFoundError as exc:
        raise PhoenixDependencyError(
            "Phoenix export requires opentelemetry-proto. "
            "Install it with: python3 -m pip install -e '.[phoenix]'"
        ) from exc

    def any_value(value: JsonValue) -> AnyValue:
        result = AnyValue()
        if isinstance(value, bool):
            result.bool_value = value
        elif isinstance(value, int):
            result.int_value = value
        elif isinstance(value, float):
            result.double_value = value
        elif isinstance(value, str):
            result.string_value = value
        elif isinstance(value, list):
            result.array_value.CopyFrom(ArrayValue(values=[any_value(item) for item in value]))
        elif isinstance(value, dict):
            result.kvlist_value.CopyFrom(
                KeyValueList(
                    values=[
                        KeyValue(key=key, value=any_value(item))
                        for key, item in sorted(value.items())
                    ]
                )
            )
        else:
            result.string_value = ""
        return result

    def attributes(values: dict[str, JsonValue]) -> list[KeyValue]:
        return [
            KeyValue(key=key, value=any_value(value))
            for key, value in sorted(values.items())
            if value is not None
        ]

    resource_attrs: dict[str, JsonValue] = {
        "service.name": "funnelcake",
        "funnelcake.project.name": project_name,
        "funnelcake.trial.id": run.trial.id,
        "funnelcake.stage": run.trial.stage.value,
        "funnelcake.task.family": run.trial.task_family or "",
    }
    resource = Resource(attributes=attributes(resource_attrs))
    scope = InstrumentationScope(name="funnelcake.discover_eval", version="0.1.0")

    proto_spans = []
    for span in run.spans:
        span_attrs = dict(span.attributes)
        if span.trace_id == run.trial.trace_id and span.parent_span_id is None:
            span_attrs.update(_trial_attributes(run))

        proto_span = Span(
            trace_id=bytes.fromhex(span.trace_id),
            span_id=bytes.fromhex(span.id),
            name=span.name,
            kind=SPAN_KIND_TO_PROTO[span.kind],
            start_time_unix_nano=int(_unix_nano(span.start_time)),
            end_time_unix_nano=int(_unix_nano(span.end_time)),
            attributes=attributes(span_attrs),
            status=Status(
                code=STATUS_CODE_TO_PROTO.get(span.status_code, 0),
                message=span.status_message,
            ),
        )
        if span.parent_span_id is not None:
            proto_span.parent_span_id = bytes.fromhex(span.parent_span_id)

        for event in span.events:
            event_attrs = dict(event.attributes)
            event_attrs["funnelcake.event.type"] = event.type.value
            if event.body is not None:
                event_attrs["funnelcake.event.body"] = event.body
            if event.severity_text is not None:
                event_attrs["funnelcake.event.severity_text"] = event.severity_text
            proto_span.events.add(
                time_unix_nano=int(_unix_nano(event.timestamp)),
                name=event.name,
                attributes=attributes(event_attrs),
            )

        proto_spans.append(proto_span)

    request = ExportTraceServiceRequest(
        resource_spans=[
            ResourceSpans(
                resource=resource,
                scope_spans=[ScopeSpans(scope=scope, spans=proto_spans)],
            )
        ]
    )
    return request.SerializeToString()
