from __future__ import annotations

from datetime import datetime, timedelta, timezone
from itertools import groupby

from funnelcake_shared import (
    FunnelEvidenceKind,
    FunnelTransitionResult,
    FunnelTransitionStatus,
    MeasurementQuality,
    MeasurementSource,
    MeasurementWindow,
    MetricUnit,
    PopulationDefinition,
    ProductFunnelStage,
)

from .models import ProductFunnelConfig, StageAttainment, TelemetryEvent, TelemetryEventType, TelemetryOutcome


def derive_stage_attainments(
    events: tuple[TelemetryEvent, ...],
    config: ProductFunnelConfig | None = None,
) -> tuple[StageAttainment, ...]:
    config = config or ProductFunnelConfig()
    sorted_events = tuple(sorted(events, key=lambda event: event.timestamp))
    attainments: list[StageAttainment] = []

    for event in sorted_events:
        entity_id = _entity_id(event, config)
        if entity_id is None:
            continue
        if event.event_type in config.activation_events:
            attainments.append(_attainment(entity_id, ProductFunnelStage.LAUNCH, event))
        if _is_value_event(event, config):
            attainments.append(_attainment(entity_id, ProductFunnelStage.INITIAL_VALUE, event))
        if event.event_type in config.revenue_events:
            attainments.append(_attainment(entity_id, ProductFunnelStage.GROW, event))

    attainments.extend(_retention_attainments(sorted_events, config))
    return tuple(sorted(attainments, key=lambda item: (item.entity_id, item.attained_at, item.stage.value)))


def calculate_transition(
    attainments: tuple[StageAttainment, ...],
    from_stage: ProductFunnelStage,
    to_stage: ProductFunnelStage,
    window: MeasurementWindow,
    population: PopulationDefinition,
    source: MeasurementSource = MeasurementSource.PRODUCTION,
    quality: MeasurementQuality = MeasurementQuality.MAPPED,
    evidence_kind: FunnelEvidenceKind = FunnelEvidenceKind.DERIVED,
    compatible_population: bool = True,
    incompatibility_reason: str | None = None,
    diagnostic_metric_ids: tuple[str, ...] = (),
) -> FunnelTransitionResult:
    if not compatible_population:
        return FunnelTransitionResult(
            transition_id=f"{from_stage.value}_to_{to_stage.value}",
            from_stage=from_stage,
            to_stage=to_stage,
            conversion_rate=None,
            numerator=None,
            denominator=None,
            unit=MetricUnit.PERCENTAGE,
            window=window,
            population=population,
            evidence_kind=evidence_kind,
            source=source,
            quality=quality,
            status=FunnelTransitionStatus.INCOMPATIBLE_POPULATION,
            status_reason=incompatibility_reason or "Funnel stages do not refer to a joinable population.",
            diagnostic_metric_ids=diagnostic_metric_ids,
        )

    from_entities = {item.entity_id for item in attainments if item.stage == from_stage}
    to_entities = {item.entity_id for item in attainments if item.stage == to_stage}
    denominator = len(from_entities)
    numerator = len(from_entities.intersection(to_entities))
    status = FunnelTransitionStatus.AVAILABLE if denominator else FunnelTransitionStatus.UNAVAILABLE
    return FunnelTransitionResult(
        transition_id=f"{from_stage.value}_to_{to_stage.value}",
        from_stage=from_stage,
        to_stage=to_stage,
        conversion_rate=(numerator / denominator) * 100 if denominator else None,
        numerator=numerator if denominator else None,
        denominator=denominator if denominator else None,
        unit=MetricUnit.PERCENTAGE,
        window=window,
        population=population,
        evidence_kind=evidence_kind,
        source=source,
        quality=quality,
        status=status,
        status_reason=None if denominator else "No entities attained the source stage.",
        diagnostic_metric_ids=diagnostic_metric_ids,
        contributing_event_ids=tuple(
            item.event_id for item in attainments if item.entity_id in from_entities.union(to_entities)
        ),
    )


def _attainment(entity_id: str, stage: ProductFunnelStage, event: TelemetryEvent) -> StageAttainment:
    return StageAttainment(
        entity_id=entity_id,
        stage=stage,
        attained_at=event.timestamp,
        event_id=event.id,
        event_type=event.event_type,
        derived_from_event_ids=(event.id,),
    )


def _retention_attainments(
    events: tuple[TelemetryEvent, ...],
    config: ProductFunnelConfig,
) -> tuple[StageAttainment, ...]:
    value_events = [event for event in events if _entity_id(event, config) is not None and _is_value_event(event, config)]
    retention: list[StageAttainment] = []

    key = lambda event: _entity_id(event, config) or ""
    for entity_id, grouped in groupby(sorted(value_events, key=lambda event: (key(event), event.timestamp)), key=key):
        entity_events = list(grouped)
        if len(entity_events) < 2:
            continue
        first_value = entity_events[0]
        first_value_time = _parse_time(first_value.timestamp)
        return_deadline = first_value_time + timedelta(days=config.return_interval_days)
        for later_event in entity_events[1:]:
            later_time = _parse_time(later_event.timestamp)
            if first_value_time < later_time <= return_deadline:
                retention.append(
                    StageAttainment(
                        entity_id=entity_id,
                        stage=ProductFunnelStage.NEXT_VALUE,
                        attained_at=later_event.timestamp,
                        event_id=later_event.id,
                        event_type=later_event.event_type,
                        derived_from_event_ids=(first_value.id, later_event.id),
                    )
                )
                break
    return tuple(retention)


def _is_value_event(event: TelemetryEvent, config: ProductFunnelConfig) -> bool:
    if event.event_type not in config.value_events:
        return False
    if event.event_type == TelemetryEventType.WORKLOAD_COMPLETED and event.outcome not in (None, TelemetryOutcome.SUCCESS):
        return False
    if config.value_task_families and event.task_family not in config.value_task_families:
        return False
    return True


def _entity_id(event: TelemetryEvent, config: ProductFunnelConfig) -> str | None:
    if config.entity_id_field == "user_id":
        return event.user_id
    return event.account_id


def _parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed
