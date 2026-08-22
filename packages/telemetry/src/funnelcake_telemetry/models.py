from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from funnelcake_shared import Attributes, FunnelStageCount, FunnelTransitionResult, ProductFunnelStage


class TelemetryEventType(StrEnum):
    ACCOUNT_CREATED = "account.created"
    SETUP_STARTED = "setup.started"
    SETUP_COMPLETED = "setup.completed"
    WORKLOAD_STARTED = "workload.started"
    WORKLOAD_COMPLETED = "workload.completed"
    VALUE_REALIZED = "value.realized"
    SUBSCRIPTION_STARTED = "subscription.started"
    SUBSCRIPTION_UPGRADED = "subscription.upgraded"
    SUBSCRIPTION_EXPANDED = "subscription.expanded"
    HUMAN_INTERVENTION_REQUIRED = "human.intervention_required"
    APPROVAL_REQUESTED = "approval.requested"
    PERMISSION_GRANTED = "permission.granted"
    PERMISSION_REVOKED = "permission.revoked"


class TelemetryActor(StrEnum):
    HUMAN = "human"
    AGENT = "agent"
    SYSTEM = "system"
    UNKNOWN = "unknown"


class TelemetryOutcome(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"
    ABANDONED = "abandoned"


@dataclass(frozen=True)
class TelemetryEvent:
    id: str
    timestamp: str
    event_type: TelemetryEventType
    user_id: str | None = None
    account_id: str | None = None
    session_id: str | None = None
    actor: TelemetryActor = TelemetryActor.UNKNOWN
    agent_provider: str | None = None
    agent_surface: str | None = None
    agent_id: str | None = None
    workload_id: str | None = None
    task_family: str | None = None
    capability: str | None = None
    outcome: TelemetryOutcome | None = None
    failure_type: str | None = None
    autonomy_level: str | None = None
    approval_required: bool | None = None
    human_intervention: bool | None = None
    intervention_type: str | None = None
    source: str | None = None
    source_event_id: str | None = None
    trace_id: str | None = None
    attributes: Attributes = field(default_factory=dict)


@dataclass(frozen=True)
class StageRule:
    stage: ProductFunnelStage
    event_types: tuple[TelemetryEventType, ...]
    task_families: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProductFunnelConfig:
    entity_id_field: str = "account_id"
    activation_events: tuple[TelemetryEventType, ...] = (TelemetryEventType.SETUP_COMPLETED,)
    value_events: tuple[TelemetryEventType, ...] = (
        TelemetryEventType.VALUE_REALIZED,
        TelemetryEventType.WORKLOAD_COMPLETED,
    )
    revenue_events: tuple[TelemetryEventType, ...] = (
        TelemetryEventType.SUBSCRIPTION_STARTED,
        TelemetryEventType.SUBSCRIPTION_UPGRADED,
        TelemetryEventType.SUBSCRIPTION_EXPANDED,
    )
    value_task_families: tuple[str, ...] = ()
    return_interval_days: int = 7
    estimated_stage_counts: dict[ProductFunnelStage, float] = field(default_factory=dict)
    incompatible_transitions: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class StageAttainment:
    entity_id: str
    stage: ProductFunnelStage
    attained_at: str
    event_id: str
    event_type: TelemetryEventType
    derived_from_event_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class MappingRule:
    source_event: str
    funnelcake_event: TelemetryEventType
    fields: dict[str, str] = field(default_factory=dict)
    constants: dict[str, object] = field(default_factory=dict)
    rules: dict[str, dict[str, object]] = field(default_factory=dict)


@dataclass(frozen=True)
class TelemetryMapping:
    mappings: tuple[MappingRule, ...]


@dataclass(frozen=True)
class FillingSnapshot:
    window_start: str
    window_end: str
    stage_counts: tuple[FunnelStageCount, ...]
    transitions: tuple[FunnelTransitionResult, ...]
    attainments: tuple[StageAttainment, ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class StageCountComparison:
    stage: ProductFunnelStage
    baseline_count: float | int | None
    current_count: float | int | None
    delta: float | int | None
    baseline_status: str
    current_status: str


@dataclass(frozen=True)
class TransitionComparison:
    transition_id: str
    from_stage: ProductFunnelStage
    to_stage: ProductFunnelStage
    baseline_rate: float | None
    current_rate: float | None
    delta_percentage_points: float | None
    baseline_status: str
    current_status: str
    status_note: str | None = None


@dataclass(frozen=True)
class FillingSnapshotComparison:
    baseline_window_start: str
    baseline_window_end: str
    current_window_start: str
    current_window_end: str
    stage_counts: tuple[StageCountComparison, ...]
    transitions: tuple[TransitionComparison, ...]
