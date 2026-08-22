from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from .traces import Attributes, DessertStage, EvidenceRef, JsonValue


class ProductFunnelStage(StrEnum):
    FIT = "fit"
    INVESTIGATE = "investigate"
    LAND = "land"
    LAUNCH = "launch"
    INITIAL_VALUE = "initial_value"
    NEXT_VALUE = "next_value"
    GROW = "grow"

    @classmethod
    def _missing_(cls, value: object) -> ProductFunnelStage | None:
        aliases = {
            "eligible_demand": cls.FIT,
            "considered": cls.INVESTIGATE,
            "selected": cls.LAND,
            "activated": cls.LAUNCH,
            "first_value": cls.INITIAL_VALUE,
            "retained": cls.NEXT_VALUE,
            "paid_expanded": cls.GROW,
        }
        if isinstance(value, str):
            return aliases.get(value)
        return None


class FunnelEvidenceKind(StrEnum):
    OBSERVED = "observed"
    ESTIMATED = "estimated"
    DERIVED = "derived"


class FunnelTransitionStatus(StrEnum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    PARTIAL = "partial"
    INCOMPATIBLE_POPULATION = "incompatible_population"


class MetricUnit(StrEnum):
    PERCENTAGE = "percentage"
    COUNT = "count"
    RATIO = "ratio"


class MeasurementSource(StrEnum):
    SYNTHETIC = "synthetic"
    PRODUCTION = "production"


class MeasurementQuality(StrEnum):
    NATIVE = "native"
    MAPPED = "mapped"
    INFERRED = "inferred"
    PROXY = "proxy"


class MetricStatus(StrEnum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    INSUFFICIENT_DATA = "insufficient_data"
    PARTIAL = "partial"


class MeasurementIntervalType(StrEnum):
    CALENDAR = "calendar"
    COHORT = "cohort"


class DurationUnit(StrEnum):
    DAY = "day"
    WEEK = "week"
    MONTH = "month"


@dataclass(frozen=True)
class Duration:
    value: int
    unit: DurationUnit


@dataclass(frozen=True)
class MeasurementWindow:
    period_start: str
    period_end: str
    interval_type: MeasurementIntervalType = MeasurementIntervalType.CALENDAR
    return_interval: Duration | None = None


@dataclass(frozen=True)
class PopulationDefinition:
    id: str
    label: str
    description: str
    attributes: Attributes = field(default_factory=dict)


@dataclass(frozen=True)
class ProductFunnelTransition:
    id: str
    from_stage: ProductFunnelStage
    to_stage: ProductFunnelStage
    label: str


@dataclass(frozen=True)
class ProductFunnelStageDefinition:
    stage: ProductFunnelStage
    label: str
    plg_meaning: str
    description: str


@dataclass(frozen=True)
class MetricDefinition:
    id: str
    stage: DessertStage
    label: str
    unit: MetricUnit
    numerator: str
    denominator: str
    population: str
    preferred_sources: tuple[MeasurementSource, ...]
    diagnostic_for: tuple[str, ...] = ()
    diagnostics: tuple[str, ...] = ()


@dataclass(frozen=True)
class MetricResult:
    metric_id: str
    stage: DessertStage
    value: float | None
    unit: MetricUnit
    numerator: float | int | None
    denominator: float | int | None
    window: MeasurementWindow
    source: MeasurementSource
    quality: MeasurementQuality
    population: PopulationDefinition
    status: MetricStatus = MetricStatus.AVAILABLE
    contributing_event_ids: tuple[str, ...] = ()
    contributing_trial_ids: tuple[str, ...] = ()
    evidence_refs: tuple[EvidenceRef, ...] = ()
    diagnostics: dict[str, JsonValue] = field(default_factory=dict)


@dataclass(frozen=True)
class FunnelStageCount:
    stage: ProductFunnelStage
    count: int | float | None
    window: MeasurementWindow
    population: PopulationDefinition
    evidence_kind: FunnelEvidenceKind
    source: MeasurementSource
    quality: MeasurementQuality
    status: MetricStatus = MetricStatus.AVAILABLE
    contributing_event_ids: tuple[str, ...] = ()
    contributing_trial_ids: tuple[str, ...] = ()
    diagnostics: dict[str, JsonValue] = field(default_factory=dict)


@dataclass(frozen=True)
class FunnelTransitionResult:
    transition_id: str
    from_stage: ProductFunnelStage
    to_stage: ProductFunnelStage
    conversion_rate: float | None
    numerator: int | float | None
    denominator: int | float | None
    unit: MetricUnit
    window: MeasurementWindow
    population: PopulationDefinition
    evidence_kind: FunnelEvidenceKind
    source: MeasurementSource
    quality: MeasurementQuality
    status: FunnelTransitionStatus = FunnelTransitionStatus.AVAILABLE
    status_reason: str | None = None
    diagnostic_metric_ids: tuple[str, ...] = ()
    contributing_event_ids: tuple[str, ...] = ()
    contributing_trial_ids: tuple[str, ...] = ()
    evidence_refs: tuple[EvidenceRef, ...] = ()
    diagnostics: dict[str, JsonValue] = field(default_factory=dict)


PRODUCT_FUNNEL_STAGE_ORDER: tuple[ProductFunnelStage, ...] = (
    ProductFunnelStage.FIT,
    ProductFunnelStage.INVESTIGATE,
    ProductFunnelStage.LAND,
    ProductFunnelStage.LAUNCH,
    ProductFunnelStage.INITIAL_VALUE,
    ProductFunnelStage.NEXT_VALUE,
    ProductFunnelStage.GROW,
)

PRODUCT_FUNNEL_STAGE_DEFINITIONS: tuple[ProductFunnelStageDefinition, ...] = (
    ProductFunnelStageDefinition(
        stage=ProductFunnelStage.FIT,
        label="FIT",
        plg_meaning="eligible demand",
        description="Relevant intents or prospective workloads where the product is a plausible solution.",
    ),
    ProductFunnelStageDefinition(
        stage=ProductFunnelStage.INVESTIGATE,
        label="INVESTIGATE",
        plg_meaning="consideration",
        description="The product is surfaced or considered for an eligible intent or workload.",
    ),
    ProductFunnelStageDefinition(
        stage=ProductFunnelStage.LAND,
        label="LAND",
        plg_meaning="selection",
        description="The product is selected, recommended, or chosen for the eligible need.",
    ),
    ProductFunnelStageDefinition(
        stage=ProductFunnelStage.LAUNCH,
        label="LAUNCH",
        plg_meaning="activation",
        description="The configured activation event occurs for an identifiable user or account.",
    ),
    ProductFunnelStageDefinition(
        stage=ProductFunnelStage.INITIAL_VALUE,
        label="INITIAL_VALUE",
        plg_meaning="first value",
        description="A configured qualifying value event occurs for the first time.",
    ),
    ProductFunnelStageDefinition(
        stage=ProductFunnelStage.NEXT_VALUE,
        label="NEXT_VALUE",
        plg_meaning="retention",
        description="Another qualifying value event occurs within the configured return window.",
    ),
    ProductFunnelStageDefinition(
        stage=ProductFunnelStage.GROW,
        label="GROW",
        plg_meaning="paid/expansion",
        description="A qualifying revenue, paid conversion, upgrade, or expansion event occurs.",
    ),
)

PRODUCT_FUNNEL_TRANSITIONS: tuple[ProductFunnelTransition, ...] = (
    ProductFunnelTransition(
        id="fit_to_investigate",
        from_stage=ProductFunnelStage.FIT,
        to_stage=ProductFunnelStage.INVESTIGATE,
        label="FIT to INVESTIGATE",
    ),
    ProductFunnelTransition(
        id="investigate_to_land",
        from_stage=ProductFunnelStage.INVESTIGATE,
        to_stage=ProductFunnelStage.LAND,
        label="INVESTIGATE to LAND",
    ),
    ProductFunnelTransition(
        id="land_to_launch",
        from_stage=ProductFunnelStage.LAND,
        to_stage=ProductFunnelStage.LAUNCH,
        label="LAND to LAUNCH",
    ),
    ProductFunnelTransition(
        id="launch_to_initial_value",
        from_stage=ProductFunnelStage.LAUNCH,
        to_stage=ProductFunnelStage.INITIAL_VALUE,
        label="LAUNCH to INITIAL_VALUE",
    ),
    ProductFunnelTransition(
        id="initial_value_to_next_value",
        from_stage=ProductFunnelStage.INITIAL_VALUE,
        to_stage=ProductFunnelStage.NEXT_VALUE,
        label="INITIAL_VALUE to NEXT_VALUE",
    ),
    ProductFunnelTransition(
        id="next_value_to_grow",
        from_stage=ProductFunnelStage.NEXT_VALUE,
        to_stage=ProductFunnelStage.GROW,
        label="NEXT_VALUE to GROW",
    ),
)

DESSERT_DIAGNOSTIC_METRIC_DEFINITIONS: tuple[MetricDefinition, ...] = (
    MetricDefinition(
        id="eligible_intent_visibility_rate",
        stage=DessertStage.DISCOVER,
        label="Eligible Intent Visibility",
        unit=MetricUnit.PERCENTAGE,
        numerator="Eligible benchmark intents where the agent surfaces the product.",
        denominator="Benchmark intents where the product is a plausible candidate.",
        population="Eligible intents, excluding ambiguous benchmark scenarios.",
        preferred_sources=(MeasurementSource.SYNTHETIC,),
        diagnostic_for=("fit_to_investigate",),
        diagnostics=("ambiguous_intent_count", "source_visibility_rate", "recommendation_position"),
    ),
    MetricDefinition(
        id="fit_evaluation_accuracy",
        stage=DessertStage.EVALUATE,
        label="Fit Evaluation Accuracy",
        unit=MetricUnit.PERCENTAGE,
        numerator="Evaluations where the agent correctly understands fit, constraints, and suitability.",
        denominator="Evaluation scenarios with benchmark truth.",
        population="Benchmark scenarios with known product-fit truth.",
        preferred_sources=(MeasurementSource.SYNTHETIC,),
        diagnostic_for=("investigate_to_land",),
        diagnostics=("false_positive_rate", "false_negative_rate", "constraint_miss_rate"),
    ),
    MetricDefinition(
        id="appropriate_selection_rate",
        stage=DessertStage.SELECT,
        label="Appropriate Selection",
        unit=MetricUnit.PERCENTAGE,
        numerator="Selection scenarios where the product is appropriately recommended or chosen.",
        denominator="Selection scenarios where the product is eligible or should be rejected.",
        population="Benchmark scenarios with a defensible solution set.",
        preferred_sources=(MeasurementSource.SYNTHETIC,),
        diagnostic_for=("investigate_to_land",),
        diagnostics=("eligible_not_selected_rate", "ineligible_selected_rate"),
    ),
    MetricDefinition(
        id="autonomous_setup_completion_rate",
        stage=DessertStage.SETUP,
        label="Autonomous Setup Completion",
        unit=MetricUnit.PERCENTAGE,
        numerator="Eligible setup attempts completed successfully without human intervention.",
        denominator="Eligible setup attempts.",
        population="Setup attempts for supported auth, credential, permission, MCP, or API connection flows.",
        preferred_sources=(MeasurementSource.SYNTHETIC, MeasurementSource.PRODUCTION),
        diagnostic_for=("land_to_launch",),
        diagnostics=(
            "first_attempt_success_rate",
            "human_intervention_rate",
            "median_time_to_ready",
            "credential_failure_rate",
            "permission_failure_rate",
        ),
    ),
    MetricDefinition(
        id="verified_task_success_rate",
        stage=DessertStage.EXECUTE,
        label="Verified Task Success",
        unit=MetricUnit.PERCENTAGE,
        numerator="Eligible task attempts that complete with verified product value.",
        denominator="Eligible task attempts.",
        population="Configured eligible workloads under the tested conditions.",
        preferred_sources=(MeasurementSource.SYNTHETIC, MeasurementSource.PRODUCTION),
        diagnostic_for=("launch_to_initial_value",),
        diagnostics=("execution_reliability", "failure_type_rate", "median_time_to_value"),
    ),
    MetricDefinition(
        id="value_retention_rate",
        stage=DessertStage.RETAIN,
        label="Value Retention",
        unit=MetricUnit.PERCENTAGE,
        numerator="Activated cohort members with another qualifying value event during the return interval.",
        denominator="Activated cohort members with enough observable time to complete the return interval.",
        population="Accounts or users activated by a configured value event during the cohort window.",
        preferred_sources=(MeasurementSource.PRODUCTION,),
        diagnostic_for=("initial_value_to_next_value",),
        diagnostics=("activated_count", "observable_cohort_count", "return_interval"),
    ),
    MetricDefinition(
        id="autonomous_workload_share",
        stage=DessertStage.TRUST,
        label="Autonomous Workload Share",
        unit=MetricUnit.PERCENTAGE,
        numerator="Successful eligible workloads completed at or above the configured autonomous delegation level.",
        denominator="All successful eligible workloads during the same period.",
        population="Successful eligible workloads in the measurement period.",
        preferred_sources=(MeasurementSource.PRODUCTION,),
        diagnostic_for=(
            "launch_to_initial_value",
            "initial_value_to_next_value",
            "next_value_to_grow",
        ),
        diagnostics=("classified_workload_rate", "approval_required_rate", "human_takeover_rate"),
    ),
)

DESSERT_DIAGNOSTIC_METRIC_BY_STAGE = {
    definition.stage: definition for definition in DESSERT_DIAGNOSTIC_METRIC_DEFINITIONS
}

DESSERT_DIAGNOSTIC_METRIC_BY_ID = {
    definition.id: definition for definition in DESSERT_DIAGNOSTIC_METRIC_DEFINITIONS
}

PRODUCT_FUNNEL_TRANSITION_BY_ID = {
    transition.id: transition for transition in PRODUCT_FUNNEL_TRANSITIONS
}

PRODUCT_FUNNEL_STAGE_DEFINITION_BY_STAGE = {
    definition.stage: definition for definition in PRODUCT_FUNNEL_STAGE_DEFINITIONS
}

# Backwards-compatible names for early reporting code that still renders DESSERT
# diagnostics as stage rows.
HEADLINE_METRIC_DEFINITIONS = DESSERT_DIAGNOSTIC_METRIC_DEFINITIONS
HEADLINE_METRIC_BY_STAGE = DESSERT_DIAGNOSTIC_METRIC_BY_STAGE
HEADLINE_METRIC_BY_ID = DESSERT_DIAGNOSTIC_METRIC_BY_ID
