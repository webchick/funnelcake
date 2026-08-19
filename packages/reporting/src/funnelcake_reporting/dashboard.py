from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from funnelcake_shared import DessertStage, Diagnosis, Failure, StageMetric, Trial

STAGE_ORDER = (
    DessertStage.DISCOVER,
    DessertStage.EVALUATE,
    DessertStage.SELECT,
    DessertStage.SETUP,
    DessertStage.EXECUTE,
    DessertStage.REPEAT,
    DessertStage.TRUST,
)


@dataclass(frozen=True)
class StageScore:
    stage: DessertStage
    score: float
    trial_count: int
    evidence_quality: str | None = None


@dataclass(frozen=True)
class ConversionStep:
    stage: DessertStage
    eligible_count: int
    converted_count: int
    conversion_rate: float


@dataclass(frozen=True)
class FailureClusterSummary:
    stage: DessertStage
    failure_type: str
    affected_trials: int
    diagnosis_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class BiggestLeak:
    stage: DessertStage
    failed_trials: int
    total_trials: int
    failure_rate: float
    top_clusters: tuple[FailureClusterSummary, ...]


@dataclass(frozen=True)
class DashboardOverview:
    stage_scores: tuple[StageScore, ...]
    conversion: tuple[ConversionStep, ...]
    biggest_leak: BiggestLeak | None
    top_failure_clusters: tuple[FailureClusterSummary, ...]


def build_stage_scores(
    trials: tuple[Trial, ...],
    metrics: tuple[StageMetric, ...],
) -> tuple[StageScore, ...]:
    trial_counts = Counter(trial.stage for trial in trials)
    primary_scores = {metric.stage: metric.score for metric in metrics if metric.name == "score"}

    return tuple(
        StageScore(
            stage=stage,
            score=primary_scores.get(stage, 0.0),
            trial_count=trial_counts.get(stage, 0),
        )
        for stage in STAGE_ORDER
    )


def build_conversion(
    metrics: tuple[StageMetric, ...],
    eligible_count: int,
) -> tuple[ConversionStep, ...]:
    primary_scores = {metric.stage: metric.score for metric in metrics if metric.name == "score"}
    current = eligible_count
    steps: list[ConversionStep] = []

    for stage in STAGE_ORDER:
        rate = primary_scores.get(stage, 0.0) / 100
        converted = round(current * rate)
        steps.append(
            ConversionStep(
                stage=stage,
                eligible_count=current,
                converted_count=converted,
                conversion_rate=rate,
            )
        )
        current = converted

    return tuple(steps)


def summarize_failure_clusters(
    failures: tuple[Failure, ...],
    diagnoses: tuple[Diagnosis, ...],
) -> tuple[FailureClusterSummary, ...]:
    counts = Counter((failure.stage, failure.failure_type) for failure in failures)
    diagnosis_index: dict[tuple[DessertStage, str], list[str]] = {}

    for diagnosis in diagnoses:
        for trial_id in diagnosis.affected_trial_ids:
            for failure in failures:
                if failure.trial_id == trial_id:
                    key = (failure.stage, failure.failure_type)
                    diagnosis_index.setdefault(key, []).append(diagnosis.id)

    summaries = [
        FailureClusterSummary(
            stage=stage,
            failure_type=failure_type,
            affected_trials=count,
            diagnosis_ids=tuple(sorted(set(diagnosis_index.get((stage, failure_type), [])))),
        )
        for (stage, failure_type), count in counts.items()
    ]

    return tuple(
        sorted(
            summaries,
            key=lambda summary: (-summary.affected_trials, summary.stage.value, summary.failure_type),
        )
    )


def find_biggest_leak(
    trials: tuple[Trial, ...],
    failures: tuple[Failure, ...],
    clusters: tuple[FailureClusterSummary, ...],
) -> BiggestLeak | None:
    trial_counts = Counter(trial.stage for trial in trials)
    failure_counts = Counter(failure.stage for failure in failures)
    candidates = []

    for stage, failed_count in failure_counts.items():
        total = trial_counts.get(stage, 0)
        if total == 0:
            continue
        candidates.append((failed_count / total, failed_count, total, stage))

    if not candidates:
        return None

    failure_rate, failed_count, total, stage = max(candidates)
    top_clusters = tuple(cluster for cluster in clusters if cluster.stage == stage)[:3]

    return BiggestLeak(
        stage=stage,
        failed_trials=failed_count,
        total_trials=total,
        failure_rate=failure_rate,
        top_clusters=top_clusters,
    )


def build_dashboard_overview(
    trials: tuple[Trial, ...],
    failures: tuple[Failure, ...],
    diagnoses: tuple[Diagnosis, ...],
    metrics: tuple[StageMetric, ...],
    eligible_count: int,
) -> DashboardOverview:
    clusters = summarize_failure_clusters(failures, diagnoses)

    return DashboardOverview(
        stage_scores=build_stage_scores(trials, metrics),
        conversion=build_conversion(metrics, eligible_count),
        biggest_leak=find_biggest_leak(trials, failures, clusters),
        top_failure_clusters=clusters[:3],
    )
