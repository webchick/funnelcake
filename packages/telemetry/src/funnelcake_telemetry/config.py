from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from funnelcake_shared import ProductFunnelStage

from .models import ProductFunnelConfig, TelemetryEventType


def load_product_funnel_config(path: str | Path | None) -> ProductFunnelConfig:
    if path is None:
        return ProductFunnelConfig()

    raw = _load_payload(Path(path).read_text(encoding="utf-8"))
    filling = raw.get("filling", raw)
    return ProductFunnelConfig(
        entity_id_field=str(filling.get("entity_id_field", "account_id")),
        activation_events=_event_types(
            filling.get("activation_events"),
            ProductFunnelConfig().activation_events,
        ),
        value_events=_event_types(
            filling.get("value_events"),
            ProductFunnelConfig().value_events,
        ),
        revenue_events=_event_types(
            filling.get("revenue_events"),
            ProductFunnelConfig().revenue_events,
        ),
        value_task_families=tuple(filling.get("value_task_families", ())),
        return_interval_days=int(filling.get("return_interval_days", 7)),
        estimated_stage_counts={
            ProductFunnelStage(stage): float(count)
            for stage, count in dict(filling.get("estimated_stage_counts", {})).items()
        },
        incompatible_transitions={
            str(transition_id): str(reason)
            for transition_id, reason in dict(filling.get("incompatible_transitions", {})).items()
        },
    )


def _event_types(raw: object, default: tuple[TelemetryEventType, ...]) -> tuple[TelemetryEventType, ...]:
    if raw is None:
        return default
    return tuple(TelemetryEventType(item) for item in raw)


def _load_payload(text: str) -> dict[str, Any]:
    try:
        loaded = json.loads(text)
        if isinstance(loaded, dict):
            return loaded
    except json.JSONDecodeError:
        pass

    try:
        import yaml
    except ModuleNotFoundError as error:
        raise ValueError("FILLING config YAML requires PyYAML. Run `python3 -m pip install -e .`.") from error

    loaded = yaml.safe_load(text) or {}
    if not isinstance(loaded, dict):
        raise ValueError("FILLING config must be an object")
    return loaded
