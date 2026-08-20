from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from funnelcake_benchmark_builder import BenchmarkTask, load_task_spec
from funnelcake_shared import DessertStage, Diagnosis, EvidenceGrade, EvidenceRef, Failure, TrialRun

from .capture import load_trial_run_artifact
from .evaluator import RunEvaluation, evaluate_run, load_run_evaluation

CHECKPOINT_FAILURE_HINTS = {
    "auth-docs-located": "auth_docs_not_found",
    "required-scopes-identified": "insufficient_scope",
    "token-existence-verified": "credential_not_created",
}


@dataclass(frozen=True)
class DiagnosisBundle:
    task_id: str
    trial_id: str
    diagnoses: tuple[Diagnosis, ...]


def load_diagnosis_bundle(path: str | Path) -> DiagnosisBundle:
    with Path(path).open(encoding="utf-8") as diagnosis_file:
        raw = json.load(diagnosis_file)

    return DiagnosisBundle(
        task_id=raw["task_id"],
        trial_id=raw["trial_id"],
        diagnoses=tuple(_diagnosis(record) for record in raw.get("diagnoses", [])),
    )


def load_diagnosis_bundles_dir(path: str | Path) -> tuple[DiagnosisBundle, ...]:
    runs_dir = Path(path)
    if not runs_dir.exists():
        return ()

    return tuple(
        load_diagnosis_bundle(diagnosis_file)
        for diagnosis_file in sorted(runs_dir.glob("*/diagnosis.json"))
    )


def diagnose_task_run(
    task_path: str | Path,
    run_path: str | Path,
    evaluation_path: str | Path | None = None,
) -> DiagnosisBundle:
    task = load_task_spec(task_path)
    run = load_trial_run_artifact(run_path)
    evaluation = (
        load_run_evaluation(evaluation_path)
        if evaluation_path is not None
        else _load_or_build_evaluation(task, run, run_path)
    )
    return diagnose_run(task, run, evaluation)


def diagnose_run(
    task: BenchmarkTask,
    run: TrialRun,
    evaluation: RunEvaluation,
) -> DiagnosisBundle:
    diagnoses = [
        _diagnosis_from_failure(index, run, failure)
        for index, failure in enumerate(run.failures, start=1)
    ]
    diagnoses.extend(_diagnoses_from_missing_checkpoints(task, run, evaluation))

    return DiagnosisBundle(
        task_id=task.id,
        trial_id=run.trial.id,
        diagnoses=tuple(diagnoses),
    )


def write_diagnosis_bundle(
    bundle: DiagnosisBundle,
    run_path: str | Path,
    output_path: str | Path | None = None,
) -> Path:
    if output_path is None:
        artifact_path = Path(run_path)
        output_path = (
            artifact_path / "diagnosis.json"
            if artifact_path.is_dir()
            else artifact_path.with_name("diagnosis.json")
        )

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as output_file:
        json.dump(asdict(bundle), output_file, indent=2)
        output_file.write("\n")
    return path


def format_diagnosis_bundle(bundle: DiagnosisBundle) -> str:
    lines = [
        f"Diagnosis {bundle.task_id}",
        f"trial={bundle.trial_id}",
        f"diagnoses={len(bundle.diagnoses)}",
    ]

    for diagnosis in bundle.diagnoses:
        lines.extend(
            [
                "",
                f"{diagnosis.id}: {diagnosis.title}",
                f"stage={diagnosis.stage.value}",
                f"evidence_grade={diagnosis.evidence_grade.value}",
                f"pattern={diagnosis.observed_pattern}",
            ]
        )
        for ref in diagnosis.evidence:
            lines.append(f"evidence={_format_evidence_ref(ref)}")
        if diagnosis.suggested_intervention:
            lines.append(f"suggested_intervention={diagnosis.suggested_intervention}")

    return "\n".join(lines)


def _load_or_build_evaluation(
    task: BenchmarkTask,
    run: TrialRun,
    run_path: str | Path,
) -> RunEvaluation:
    artifact_path = Path(run_path)
    if artifact_path.is_dir():
        evaluation_path = artifact_path / "evaluation.json"
        if evaluation_path.exists():
            return load_run_evaluation(evaluation_path)
    return evaluate_run(task, run)


def _diagnosis(record: dict[str, Any]) -> Diagnosis:
    return Diagnosis(
        id=record["id"],
        title=record["title"],
        stage=DessertStage(record["stage"]),
        evidence_grade=EvidenceGrade(record["evidence_grade"]),
        affected_trial_ids=tuple(record.get("affected_trial_ids", [])),
        observed_pattern=record["observed_pattern"],
        supporting_sources=tuple(record.get("supporting_sources", [])),
        suggested_intervention=record.get("suggested_intervention"),
        evidence=tuple(_evidence_ref(item) for item in record.get("evidence", [])),
    )


def _evidence_ref(record: dict[str, Any]) -> EvidenceRef:
    return EvidenceRef(
        trace_id=record["trace_id"],
        span_id=record.get("span_id"),
        event_id=record.get("event_id"),
        source_url=record.get("source_url"),
    )


def _diagnosis_from_failure(index: int, run: TrialRun, failure: Failure) -> Diagnosis:
    failure_label = failure.failure_type.replace("_", " ")
    return Diagnosis(
        id=f"{failure.failure_type.upper()}-{index:03d}",
        title=failure.summary or f"{failure_label.title()} observed",
        stage=failure.stage,
        evidence_grade=EvidenceGrade.OBSERVATION,
        affected_trial_ids=(run.trial.id,),
        observed_pattern=failure.summary or f"Run recorded failure type {failure.failure_type}.",
        evidence=failure.evidence,
    )


def _diagnoses_from_missing_checkpoints(
    task: BenchmarkTask,
    run: TrialRun,
    evaluation: RunEvaluation,
) -> list[Diagnosis]:
    diagnoses: list[Diagnosis] = []
    fallback_evidence = _fallback_evidence(run)
    if not fallback_evidence:
        return diagnoses

    for checkpoint in evaluation.checkpoints:
        if checkpoint.passed or not checkpoint.required:
            continue

        failed_assertions = tuple(
            assertion.assertion_id
            for assertion in checkpoint.assertions
            if assertion.required and not assertion.passed
        )
        failure_type = CHECKPOINT_FAILURE_HINTS.get(checkpoint.checkpoint_id, checkpoint.checkpoint_id)
        diagnoses.append(
            Diagnosis(
                id=f"{failure_type.upper()}-HYP",
                title=f"Required checkpoint missing: {checkpoint.checkpoint_id}",
                stage=task.stage,
                evidence_grade=EvidenceGrade.HYPOTHESIS,
                affected_trial_ids=(run.trial.id,),
                observed_pattern=(
                    "No matching non-placeholder trace evidence satisfied required "
                    f"assertions: {', '.join(failed_assertions) or 'none'}."
                ),
                suggested_intervention=_suggested_intervention(failure_type),
                evidence=fallback_evidence,
            )
        )

    return diagnoses


def _fallback_evidence(run: TrialRun) -> tuple[EvidenceRef, ...]:
    refs = [ref for failure in run.failures for ref in failure.evidence]
    refs.extend(run.final_state.evidence)
    unique: dict[tuple[Any, ...], EvidenceRef] = {}
    for ref in refs:
        unique[(ref.trace_id, ref.span_id, ref.event_id, ref.source_url)] = ref
    return tuple(unique.values())


def _suggested_intervention(failure_type: str) -> str | None:
    suggestions = {
        "auth_docs_not_found": "Link authentication and token-creation documentation directly from API onboarding.",
        "insufficient_scope": "Document required scopes near token creation and deployment examples.",
        "credential_not_created": "Provide a verifiable credential-creation path that can be completed autonomously.",
    }
    return suggestions.get(failure_type)


def _format_evidence_ref(ref: EvidenceRef) -> str:
    parts = [f"trace_id={ref.trace_id}"]
    if ref.span_id is not None:
        parts.append(f"span_id={ref.span_id}")
    if ref.event_id is not None:
        parts.append(f"event_id={ref.event_id}")
    if ref.source_url is not None:
        parts.append(f"source_url={ref.source_url}")
    return " ".join(parts)
