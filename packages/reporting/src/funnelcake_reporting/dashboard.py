from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from funnelcake_shared import (
    DESSERT_DIAGNOSTIC_METRIC_BY_STAGE,
    DessertStage,
    Diagnosis,
    EvidenceGrade,
    Failure,
    StageMetric,
    Trial,
    TrialRun,
)

STAGE_ORDER = (
    DessertStage.DISCOVER,
    DessertStage.EVALUATE,
    DessertStage.SELECT,
    DessertStage.SETUP,
    DessertStage.EXECUTE,
    DessertStage.RETAIN,
    DessertStage.TRUST,
)


@dataclass(frozen=True)
class StageScore:
    stage: DessertStage
    score: float
    trial_count: int
    metric_id: str | None = None
    label: str | None = None
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
    evidence_grades: tuple[EvidenceGrade, ...] = ()


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
            metric_id=DESSERT_DIAGNOSTIC_METRIC_BY_STAGE[stage].id,
            label=DESSERT_DIAGNOSTIC_METRIC_BY_STAGE[stage].label,
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
                if failure.trial_id == trial_id and _diagnosis_matches_failure_type(
                    diagnosis,
                    failure.failure_type,
                ):
                    key = (failure.stage, failure.failure_type)
                    diagnosis_index.setdefault(key, []).append(diagnosis.id)
                    break

    summaries = [
        FailureClusterSummary(
            stage=stage,
            failure_type=failure_type,
            affected_trials=count,
            diagnosis_ids=tuple(sorted(set(diagnosis_index.get((stage, failure_type), [])))),
            evidence_grades=_evidence_grades_for_cluster(stage, failure_type, failures, diagnoses),
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
        conversion=(),
        biggest_leak=find_biggest_leak(trials, failures, clusters),
        top_failure_clusters=clusters[:3],
    )


def build_dashboard_from_trial_runs(
    runs: tuple[TrialRun, ...],
    eligible_count: int | None = None,
    diagnoses: tuple[Diagnosis, ...] = (),
) -> DashboardOverview:
    trials = tuple(run.trial for run in runs)
    failures = tuple(failure for run in runs for failure in run.failures)
    metrics = build_stage_metrics_from_runs(runs)

    return build_dashboard_overview(
        trials=trials,
        failures=failures,
        diagnoses=diagnoses,
        metrics=metrics,
        eligible_count=eligible_count if eligible_count is not None else max(len(runs), 1),
    )


def build_stage_metrics_from_runs(runs: tuple[TrialRun, ...]) -> tuple[StageMetric, ...]:
    by_stage: dict[DessertStage, list[TrialRun]] = {stage: [] for stage in STAGE_ORDER}
    for run in runs:
        by_stage[run.trial.stage].append(run)

    metrics = []
    for stage in STAGE_ORDER:
        stage_runs = by_stage[stage]
        if not stage_runs:
            metrics.append(StageMetric(stage=stage, name="score", score=0.0))
            continue

        passed = sum(1 for run in stage_runs if run.final_state.passed)
        metrics.append(
            StageMetric(
                stage=stage,
                name="score",
                score=(passed / len(stage_runs)) * 100,
                numerator=passed,
                denominator=len(stage_runs),
            )
        )

    return tuple(metrics)


def format_dashboard_overview(overview: DashboardOverview) -> str:
    lines = ["DESSERT dashboard summary", "", "DESSERT Diagnostics"]
    for score in overview.stage_scores:
        label = score.label or score.stage.value
        metric_id = f" metric={score.metric_id}" if score.metric_id else ""
        lines.append(
            f"{score.stage.value}: {score.score:.0f} "
            f"{label}{metric_id} trials={score.trial_count}"
        )

    if overview.biggest_leak is not None:
        leak = overview.biggest_leak
        lines.extend(
            [
                "",
                "Biggest Leak",
                f"{leak.stage.value}: {leak.failed_trials}/{leak.total_trials} "
                f"({leak.failure_rate:.0%})",
            ]
        )
        for cluster in leak.top_clusters:
            lines.append(_format_cluster_line(cluster, include_stage=False))

    if overview.top_failure_clusters:
        lines.extend(["", "Top Failure Clusters"])
        for cluster in overview.top_failure_clusters:
            lines.append(_format_cluster_line(cluster, include_stage=True))

    return "\n".join(lines)


def _evidence_grades_for_cluster(
    stage: DessertStage,
    failure_type: str,
    failures: tuple[Failure, ...],
    diagnoses: tuple[Diagnosis, ...],
) -> tuple[EvidenceGrade, ...]:
    affected_trial_ids = {
        failure.trial_id
        for failure in failures
        if failure.stage == stage and failure.failure_type == failure_type
    }
    grades = {
        diagnosis.evidence_grade
        for diagnosis in diagnoses
        if affected_trial_ids.intersection(diagnosis.affected_trial_ids)
        and _diagnosis_matches_failure_type(diagnosis, failure_type)
    }
    return tuple(sorted(grades, key=lambda grade: grade.value))


def _diagnosis_matches_failure_type(diagnosis: Diagnosis, failure_type: str) -> bool:
    return diagnosis.id.lower().startswith(failure_type.lower())


def _format_cluster_line(cluster: FailureClusterSummary, include_stage: bool) -> str:
    prefix = f"{cluster.stage.value}/{cluster.failure_type}" if include_stage else cluster.failure_type
    parts = [f"- {prefix}: {cluster.affected_trials}"]
    if cluster.diagnosis_ids:
        parts.append(f"diagnoses={','.join(cluster.diagnosis_ids)}")
    if cluster.evidence_grades:
        parts.append(f"grades={','.join(grade.value for grade in cluster.evidence_grades)}")
    return " ".join(parts)
