from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import (
    MappingRule,
    TelemetryActor,
    TelemetryEvent,
    TelemetryEventType,
    TelemetryMapping,
    TelemetryOutcome,
)


def load_raw_events(path: str | Path) -> tuple[dict[str, Any], ...]:
    event_path = Path(path)
    text = event_path.read_text(encoding="utf-8").strip()
    if not text:
        return ()
    if event_path.suffix == ".jsonl":
        return tuple(json.loads(line) for line in text.splitlines() if line.strip())
    data = json.loads(text)
    if isinstance(data, list):
        return tuple(data)
    if isinstance(data, dict) and isinstance(data.get("events"), list):
        return tuple(data["events"])
    if isinstance(data, dict):
        return (data,)
    raise ValueError(f"unsupported raw event payload in {event_path}")


def load_mapping(path: str | Path) -> TelemetryMapping:
    text = Path(path).read_text(encoding="utf-8")
    raw = _load_mapping_payload(text)

    mappings = []
    for record in raw.get("mappings", []):
        mappings.append(
            MappingRule(
                source_event=record["source_event"],
                funnelcake_event=TelemetryEventType(record["funnelcake_event"]),
                fields=dict(record.get("fields", {})),
                constants=dict(record.get("constants", {})),
                rules=dict(record.get("rules", {})),
            )
        )
    return TelemetryMapping(mappings=tuple(mappings))


def _load_mapping_payload(text: str) -> dict[str, Any]:
    try:
        loaded = json.loads(text)
        if isinstance(loaded, dict):
            return loaded
    except json.JSONDecodeError:
        pass

    try:
        import yaml  # type: ignore[import-not-found]
    except ModuleNotFoundError as error:
        raise ValueError(
            "YAML mappings require PyYAML unless the mapping file uses JSON syntax."
        ) from error

    loaded = yaml.safe_load(text) or {}
    if not isinstance(loaded, dict):
        raise ValueError("telemetry mapping must be an object")
    return loaded


def normalize_events(
    raw_events: tuple[dict[str, Any], ...],
    mapping: TelemetryMapping,
    source: str | None = None,
) -> tuple[TelemetryEvent, ...]:
    normalized = []
    for index, raw_event in enumerate(raw_events, start=1):
        rule = _matching_rule(raw_event, mapping)
        if rule is None:
            continue
        values: dict[str, Any] = {
            "id": _string_or_default(_field(raw_event, "id"), f"evt-{index:04d}"),
            "timestamp": _string_or_default(_field(raw_event, "timestamp"), ""),
            "event_type": rule.funnelcake_event,
            "source": source,
            "source_event_id": _as_string(_field(raw_event, "id")),
            "attributes": {"raw_event": raw_event},
        }

        for target, field_path in rule.fields.items():
            values[target] = _field(raw_event, field_path)
        values.update(rule.constants)
        for target, rule_config in rule.rules.items():
            values[target] = _apply_rule(raw_event, rule_config)

        values["actor"] = _enum_value(TelemetryActor, values.get("actor"), TelemetryActor.UNKNOWN)
        values["outcome"] = _enum_value(TelemetryOutcome, values.get("outcome"), None)

        normalized.append(TelemetryEvent(**values))
    return tuple(normalized)


def normalize_file(path: str | Path, mapping_path: str | Path, source: str | None = None) -> tuple[TelemetryEvent, ...]:
    return normalize_events(load_raw_events(path), load_mapping(mapping_path), source=source)


def event_to_dict(event: TelemetryEvent) -> dict[str, Any]:
    return {
        "id": event.id,
        "timestamp": event.timestamp,
        "event_type": event.event_type.value,
        "user_id": event.user_id,
        "account_id": event.account_id,
        "session_id": event.session_id,
        "actor": event.actor.value,
        "agent_provider": event.agent_provider,
        "agent_surface": event.agent_surface,
        "agent_id": event.agent_id,
        "workload_id": event.workload_id,
        "task_family": event.task_family,
        "capability": event.capability,
        "outcome": event.outcome.value if event.outcome else None,
        "failure_type": event.failure_type,
        "autonomy_level": event.autonomy_level,
        "approval_required": event.approval_required,
        "human_intervention": event.human_intervention,
        "intervention_type": event.intervention_type,
        "source": event.source,
        "source_event_id": event.source_event_id,
        "trace_id": event.trace_id,
        "attributes": event.attributes,
    }


def write_normalized_events(events: tuple[TelemetryEvent, ...], path: str | Path) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"events": [event_to_dict(event) for event in events]}
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return output_path


def load_normalized_events(path: str | Path) -> tuple[TelemetryEvent, ...]:
    raw_events = load_raw_events(path)
    events = []
    for raw in raw_events:
        values = dict(raw)
        values["event_type"] = TelemetryEventType(values["event_type"])
        values["actor"] = TelemetryActor(values.get("actor", "unknown"))
        if values.get("outcome") is not None:
            values["outcome"] = TelemetryOutcome(values["outcome"])
        events.append(TelemetryEvent(**values))
    return tuple(events)


def _matching_rule(raw_event: dict[str, Any], mapping: TelemetryMapping) -> MappingRule | None:
    event_name = _field(raw_event, "event") or _field(raw_event, "event_name") or _field(raw_event, "type")
    for rule in mapping.mappings:
        if event_name == rule.source_event:
            return rule
    return None


def _field(record: dict[str, Any], path: str) -> Any:
    current: Any = record
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _apply_rule(raw_event: dict[str, Any], rule_config: dict[str, object]) -> object:
    condition = rule_config.get("if")
    if isinstance(condition, dict):
        field_value = _field(raw_event, str(condition.get("field", "")))
        if condition.get("exists") is True:
            return rule_config.get("then") if field_value is not None else rule_config.get("else")
    return rule_config.get("else")


def _enum_value(enum_type: type, value: object, default: Any) -> Any:
    if value is None:
        return default
    return enum_type(value)


def _as_string(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def _string_or_default(value: object, default: str) -> str:
    if value is None:
        return default
    return str(value)
