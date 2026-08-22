from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from funnelcake_shared import (
    FunnelEvidenceKind,
    FunnelStageCount,
    FunnelTransitionResult,
    FunnelTransitionStatus,
    MeasurementIntervalType,
    MeasurementQuality,
    MeasurementSource,
    MeasurementWindow,
    MetricStatus,
    MetricUnit,
    PopulationDefinition,
    PRODUCT_FUNNEL_STAGE_ORDER,
    PRODUCT_FUNNEL_TRANSITIONS,
    ProductFunnelStage,
)

from .attainment import calculate_transition, derive_stage_attainments
from .models import (
    FillingSnapshot,
    FillingSnapshotComparison,
    ProductFunnelConfig,
    StageAttainment,
    StageCountComparison,
    TelemetryEvent,
    TelemetryEventType,
    TransitionComparison,
)


def build_filling_snapshot(
    events: tuple[TelemetryEvent, ...],
    config: ProductFunnelConfig | None = None,
) -> FillingSnapshot:
    config = config or ProductFunnelConfig()
    attainments = derive_stage_attainments(events, config)
    window = MeasurementWindow(
        period_start=min((event.timestamp for event in events), default=""),
        period_end=max((event.timestamp for event in events), default=""),
        interval_type=MeasurementIntervalType.COHORT,
    )
    population = PopulationDefinition(
        id="telemetry_entities",
        label="Telemetry entities",
        description=f"Entities joined by {config.entity_id_field} in canonical telemetry.",
    )
    stage_counts = _stage_counts(attainments, config, window, population)
    transitions = _transitions(attainments, config, window, population)
    warnings = tuple(
        transition.status_reason
        for transition in transitions
        if transition.status in {
            FunnelTransitionStatus.INCOMPATIBLE_POPULATION,
            FunnelTransitionStatus.UNAVAILABLE,
            FunnelTransitionStatus.PARTIAL,
        }
        and transition.status_reason
    )
    return FillingSnapshot(
        window_start=window.period_start,
        window_end=window.period_end,
        stage_counts=stage_counts,
        transitions=transitions,
        attainments=attainments,
        warnings=warnings,
    )


def _stage_counts(
    attainments: tuple[StageAttainment, ...],
    config: ProductFunnelConfig,
    window: MeasurementWindow,
    population: PopulationDefinition,
) -> tuple[FunnelStageCount, ...]:
    entities_by_stage: dict[object, set[str]] = defaultdict(set)
    event_ids_by_stage: dict[object, list[str]] = defaultdict(list)
    for attainment in attainments:
        entities_by_stage[attainment.stage].add(attainment.entity_id)
        event_ids_by_stage[attainment.stage].append(attainment.event_id)

    counts = []
    for stage in PRODUCT_FUNNEL_STAGE_ORDER:
        if stage in config.estimated_stage_counts:
            counts.append(
                FunnelStageCount(
                    stage=stage,
                    count=config.estimated_stage_counts[stage],
                    window=window,
                    population=population,
                    evidence_kind=FunnelEvidenceKind.ESTIMATED,
                    source=MeasurementSource.SYNTHETIC,
                    quality=MeasurementQuality.PROXY,
                    status=MetricStatus.AVAILABLE,
                )
            )
            continue

        count = len(entities_by_stage.get(stage, set()))
        if count:
            counts.append(
                FunnelStageCount(
                    stage=stage,
                    count=count,
                    window=window,
                    population=population,
                    evidence_kind=FunnelEvidenceKind.DERIVED,
                    source=MeasurementSource.PRODUCTION,
                    quality=MeasurementQuality.MAPPED,
                    status=MetricStatus.AVAILABLE,
                    contributing_event_ids=tuple(event_ids_by_stage.get(stage, ())),
                )
            )
            continue

        counts.append(
            FunnelStageCount(
                stage=stage,
                count=None,
                window=window,
                population=population,
                evidence_kind=FunnelEvidenceKind.OBSERVED,
                source=MeasurementSource.PRODUCTION,
                quality=MeasurementQuality.MAPPED,
                status=MetricStatus.UNAVAILABLE,
                diagnostics={"reason": "No compatible observed, estimated, or derived evidence for this stage."},
            )
        )
    return tuple(counts)


def _transitions(
    attainments: tuple[StageAttainment, ...],
    config: ProductFunnelConfig,
    window: MeasurementWindow,
    population: PopulationDefinition,
) -> tuple[FunnelTransitionResult, ...]:
    results = []
    for transition in PRODUCT_FUNNEL_TRANSITIONS:
        incompatible_reason = config.incompatible_transitions.get(transition.id)
        if incompatible_reason:
            results.append(
                calculate_transition(
                    attainments,
                    transition.from_stage,
                    transition.to_stage,
                    window=window,
                    population=population,
                    compatible_population=False,
                    incompatibility_reason=incompatible_reason,
                )
            )
            continue

        from_estimate = config.estimated_stage_counts.get(transition.from_stage)
        to_estimate = config.estimated_stage_counts.get(transition.to_stage)
        if from_estimate is not None and to_estimate is not None:
            results.append(
                FunnelTransitionResult(
                    transition_id=transition.id,
                    from_stage=transition.from_stage,
                    to_stage=transition.to_stage,
                    conversion_rate=(to_estimate / from_estimate) * 100 if from_estimate else None,
                    numerator=to_estimate if from_estimate else None,
                    denominator=from_estimate if from_estimate else None,
                    unit=MetricUnit.PERCENTAGE,
                    window=window,
                    population=population,
                    evidence_kind=FunnelEvidenceKind.ESTIMATED,
                    source=MeasurementSource.SYNTHETIC,
                    quality=MeasurementQuality.PROXY,
                    status=FunnelTransitionStatus.AVAILABLE if from_estimate else FunnelTransitionStatus.UNAVAILABLE,
                    status_reason=None if from_estimate else "Estimated source stage count is zero.",
                )
            )
            continue

        results.append(
            calculate_transition(
                attainments,
                transition.from_stage,
                transition.to_stage,
                window=window,
                population=population,
                source=MeasurementSource.PRODUCTION,
                quality=MeasurementQuality.MAPPED,
                evidence_kind=FunnelEvidenceKind.DERIVED,
            )
        )
    return tuple(results)


def snapshot_to_dict(snapshot: FillingSnapshot) -> dict[str, object]:
    return {
        "window_start": snapshot.window_start,
        "window_end": snapshot.window_end,
        "stage_counts": [_stage_count_to_dict(count) for count in snapshot.stage_counts],
        "transitions": [_transition_to_dict(transition) for transition in snapshot.transitions],
        "attainments": [
            {
                "entity_id": item.entity_id,
                "stage": item.stage.value,
                "attained_at": item.attained_at,
                "event_id": item.event_id,
                "event_type": item.event_type.value,
                "derived_from_event_ids": list(item.derived_from_event_ids),
            }
            for item in snapshot.attainments
        ],
        "warnings": list(snapshot.warnings),
    }


def write_filling_snapshot(snapshot: FillingSnapshot, path: str | Path) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(snapshot_to_dict(snapshot), indent=2), encoding="utf-8")
    return output_path


def load_filling_snapshot(path: str | Path) -> FillingSnapshot:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    window = MeasurementWindow(
        period_start=raw.get("window_start", ""),
        period_end=raw.get("window_end", ""),
        interval_type=MeasurementIntervalType.COHORT,
    )
    population = PopulationDefinition(
        id="loaded_snapshot",
        label="Loaded snapshot",
        description=f"Snapshot loaded from {path}.",
    )
    return FillingSnapshot(
        window_start=raw.get("window_start", ""),
        window_end=raw.get("window_end", ""),
        stage_counts=tuple(_stage_count_from_dict(item, window, population) for item in raw.get("stage_counts", [])),
        transitions=tuple(_transition_from_dict(item, window, population) for item in raw.get("transitions", [])),
        attainments=tuple(_attainment_from_dict(item) for item in raw.get("attainments", [])),
        warnings=tuple(raw.get("warnings", [])),
    )


def compare_filling_snapshots(
    baseline: FillingSnapshot,
    current: FillingSnapshot,
) -> FillingSnapshotComparison:
    baseline_counts = {count.stage: count for count in baseline.stage_counts}
    current_counts = {count.stage: count for count in current.stage_counts}
    stage_comparisons = []
    for stage in PRODUCT_FUNNEL_STAGE_ORDER:
        baseline_count = baseline_counts.get(stage)
        current_count = current_counts.get(stage)
        baseline_value = baseline_count.count if baseline_count else None
        current_value = current_count.count if current_count else None
        delta = (
            current_value - baseline_value
            if baseline_value is not None and current_value is not None
            else None
        )
        stage_comparisons.append(
            StageCountComparison(
                stage=stage,
                baseline_count=baseline_value,
                current_count=current_value,
                delta=delta,
                baseline_status=baseline_count.status.value if baseline_count else MetricStatus.UNAVAILABLE.value,
                current_status=current_count.status.value if current_count else MetricStatus.UNAVAILABLE.value,
            )
        )

    baseline_transitions = {transition.transition_id: transition for transition in baseline.transitions}
    current_transitions = {transition.transition_id: transition for transition in current.transitions}
    transition_comparisons = []
    for transition in PRODUCT_FUNNEL_TRANSITIONS:
        baseline_transition = baseline_transitions.get(transition.id)
        current_transition = current_transitions.get(transition.id)
        baseline_status = (
            baseline_transition.status
            if baseline_transition is not None
            else FunnelTransitionStatus.UNAVAILABLE
        )
        current_status = (
            current_transition.status
            if current_transition is not None
            else FunnelTransitionStatus.UNAVAILABLE
        )
        can_compare = (
            baseline_status == FunnelTransitionStatus.AVAILABLE
            and current_status == FunnelTransitionStatus.AVAILABLE
            and baseline_transition is not None
            and current_transition is not None
            and baseline_transition.conversion_rate is not None
            and current_transition.conversion_rate is not None
        )
        note = None
        if baseline_status != current_status:
            note = f"status changed from {baseline_status.value} to {current_status.value}"
        elif not can_compare:
            note = f"no delta for status {current_status.value}"
        transition_comparisons.append(
            TransitionComparison(
                transition_id=transition.id,
                from_stage=transition.from_stage,
                to_stage=transition.to_stage,
                baseline_rate=baseline_transition.conversion_rate if baseline_transition else None,
                current_rate=current_transition.conversion_rate if current_transition else None,
                delta_percentage_points=(
                    current_transition.conversion_rate - baseline_transition.conversion_rate
                    if can_compare
                    else None
                ),
                baseline_status=baseline_status.value,
                current_status=current_status.value,
                status_note=note,
            )
        )

    return FillingSnapshotComparison(
        baseline_window_start=baseline.window_start,
        baseline_window_end=baseline.window_end,
        current_window_start=current.window_start,
        current_window_end=current.window_end,
        stage_counts=tuple(stage_comparisons),
        transitions=tuple(transition_comparisons),
    )


def comparison_to_dict(comparison: FillingSnapshotComparison) -> dict[str, object]:
    return {
        "baseline_window_start": comparison.baseline_window_start,
        "baseline_window_end": comparison.baseline_window_end,
        "current_window_start": comparison.current_window_start,
        "current_window_end": comparison.current_window_end,
        "stage_counts": [
            {
                "stage": item.stage.value,
                "baseline_count": item.baseline_count,
                "current_count": item.current_count,
                "delta": item.delta,
                "baseline_status": item.baseline_status,
                "current_status": item.current_status,
            }
            for item in comparison.stage_counts
        ],
        "transitions": [
            {
                "transition_id": item.transition_id,
                "from_stage": item.from_stage.value,
                "to_stage": item.to_stage.value,
                "baseline_rate": item.baseline_rate,
                "current_rate": item.current_rate,
                "delta_percentage_points": item.delta_percentage_points,
                "baseline_status": item.baseline_status,
                "current_status": item.current_status,
                "status_note": item.status_note,
            }
            for item in comparison.transitions
        ],
    }


def format_filling_snapshot(snapshot: FillingSnapshot) -> str:
    lines = ["FILLING snapshot", "", "Stages"]
    for count in snapshot.stage_counts:
        value = "" if count.count is None else _format_count(count.count)
        reason = ""
        if count.status == MetricStatus.UNAVAILABLE:
            reason = f" reason={count.diagnostics.get('reason', '')}"
        lines.append(
            f"{count.stage.value}: {value} "
            f"{count.evidence_kind.value} status={count.status.value}{reason}"
        )

    lines.extend(["", "Transitions"])
    for transition in snapshot.transitions:
        rate = "" if transition.conversion_rate is None else f"{transition.conversion_rate:.1f}%"
        reason = f" reason={transition.status_reason}" if transition.status_reason else ""
        lines.append(
            f"{transition.from_stage.value}->{transition.to_stage.value}: "
            f"{rate} status={transition.status.value}{reason}"
        )

    if snapshot.warnings:
        lines.extend(["", "Warnings"])
        lines.extend(f"- {warning}" for warning in snapshot.warnings)
    return "\n".join(lines)


def format_filling_comparison(comparison: FillingSnapshotComparison) -> str:
    lines = [
        "FILLING comparison",
        f"baseline={comparison.baseline_window_start}..{comparison.baseline_window_end}",
        f"current={comparison.current_window_start}..{comparison.current_window_end}",
        "",
        "Stage Counts",
    ]
    for item in comparison.stage_counts:
        delta = "" if item.delta is None else f" delta={_format_signed(item.delta)}"
        lines.append(
            f"{item.stage.value}: {item.baseline_count or ''}->{item.current_count or ''}{delta} "
            f"status={item.baseline_status}->{item.current_status}"
        )

    lines.extend(["", "Transitions"])
    for item in comparison.transitions:
        delta = (
            ""
            if item.delta_percentage_points is None
            else f" delta={_format_signed(item.delta_percentage_points)}pp"
        )
        note = f" note={item.status_note}" if item.status_note else ""
        baseline = "" if item.baseline_rate is None else f"{item.baseline_rate:.1f}%"
        current = "" if item.current_rate is None else f"{item.current_rate:.1f}%"
        lines.append(
            f"{item.from_stage.value}->{item.to_stage.value}: {baseline}->{current}{delta} "
            f"status={item.baseline_status}->{item.current_status}{note}"
        )
    return "\n".join(lines)


def _stage_count_to_dict(count: FunnelStageCount) -> dict[str, object]:
    return {
        "stage": count.stage.value,
        "count": count.count,
        "evidence_kind": count.evidence_kind.value,
        "source": count.source.value,
        "quality": count.quality.value,
        "status": count.status.value,
        "contributing_event_ids": list(count.contributing_event_ids),
        "diagnostics": count.diagnostics,
    }


def _stage_count_from_dict(
    raw: dict[str, object],
    window: MeasurementWindow,
    population: PopulationDefinition,
) -> FunnelStageCount:
    return FunnelStageCount(
        stage=ProductFunnelStage(raw["stage"]),
        count=raw.get("count"),
        window=window,
        population=population,
        evidence_kind=FunnelEvidenceKind(raw["evidence_kind"]),
        source=MeasurementSource(raw["source"]),
        quality=MeasurementQuality(raw["quality"]),
        status=MetricStatus(raw["status"]),
        contributing_event_ids=tuple(raw.get("contributing_event_ids", [])),
        diagnostics=dict(raw.get("diagnostics", {})),
    )


def _transition_to_dict(transition: FunnelTransitionResult) -> dict[str, object]:
    return {
        "transition_id": transition.transition_id,
        "from_stage": transition.from_stage.value,
        "to_stage": transition.to_stage.value,
        "conversion_rate": transition.conversion_rate,
        "numerator": transition.numerator,
        "denominator": transition.denominator,
        "unit": transition.unit.value if transition.unit == MetricUnit.PERCENTAGE else transition.unit.value,
        "evidence_kind": transition.evidence_kind.value,
        "source": transition.source.value,
        "quality": transition.quality.value,
        "status": transition.status.value,
        "status_reason": transition.status_reason,
        "diagnostic_metric_ids": list(transition.diagnostic_metric_ids),
        "contributing_event_ids": list(transition.contributing_event_ids),
        "diagnostics": transition.diagnostics,
    }


def _transition_from_dict(
    raw: dict[str, object],
    window: MeasurementWindow,
    population: PopulationDefinition,
) -> FunnelTransitionResult:
    return FunnelTransitionResult(
        transition_id=str(raw["transition_id"]),
        from_stage=ProductFunnelStage(raw["from_stage"]),
        to_stage=ProductFunnelStage(raw["to_stage"]),
        conversion_rate=raw.get("conversion_rate"),
        numerator=raw.get("numerator"),
        denominator=raw.get("denominator"),
        unit=MetricUnit(raw["unit"]),
        window=window,
        population=population,
        evidence_kind=FunnelEvidenceKind(raw["evidence_kind"]),
        source=MeasurementSource(raw["source"]),
        quality=MeasurementQuality(raw["quality"]),
        status=FunnelTransitionStatus(raw["status"]),
        status_reason=raw.get("status_reason"),
        diagnostic_metric_ids=tuple(raw.get("diagnostic_metric_ids", [])),
        contributing_event_ids=tuple(raw.get("contributing_event_ids", [])),
        diagnostics=dict(raw.get("diagnostics", {})),
    )


def _attainment_from_dict(raw: dict[str, object]) -> StageAttainment:
    return StageAttainment(
        entity_id=str(raw["entity_id"]),
        stage=ProductFunnelStage(raw["stage"]),
        attained_at=str(raw["attained_at"]),
        event_id=str(raw["event_id"]),
        event_type=TelemetryEventType(raw["event_type"]),
        derived_from_event_ids=tuple(raw.get("derived_from_event_ids", [])),
    )


def _format_count(value: float | int) -> str:
    return str(int(value)) if float(value).is_integer() else str(value)


def _format_signed(value: float | int) -> str:
    prefix = "+" if value > 0 else ""
    return f"{prefix}{value:.1f}" if isinstance(value, float) else f"{prefix}{value}"
