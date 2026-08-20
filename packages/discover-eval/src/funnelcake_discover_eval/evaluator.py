from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from funnelcake_benchmark_builder import AssertionSpec, BenchmarkTask, CheckpointSpec, load_task_spec
from funnelcake_shared import EvidenceRef, JsonValue, TraceEvent, TrialRun

from .capture import load_trial_run_artifact


@dataclass(frozen=True)
class AssertionEvaluation:
    assertion_id: str
    passed: bool
    required: bool
    evidence: tuple[EvidenceRef, ...] = ()


@dataclass(frozen=True)
class CheckpointEvaluation:
    checkpoint_id: str
    passed: bool
    required: bool
    assertions: tuple[AssertionEvaluation, ...]


@dataclass(frozen=True)
class RunEvaluation:
    task_id: str
    trial_id: str
    passed: bool
    final_state_passed: bool
    checkpoints: tuple[CheckpointEvaluation, ...]


def evaluate_task_run(
    task_path: str | Path,
    run_path: str | Path,
) -> RunEvaluation:
    task = load_task_spec(task_path)
    run = load_trial_run_artifact(run_path)
    return evaluate_run(task, run)


def load_run_evaluation(path: str | Path) -> RunEvaluation:
    with Path(path).open(encoding="utf-8") as evaluation_file:
        raw = json.load(evaluation_file)

    return RunEvaluation(
        task_id=raw["task_id"],
        trial_id=raw["trial_id"],
        passed=raw["passed"],
        final_state_passed=raw["final_state_passed"],
        checkpoints=tuple(
            CheckpointEvaluation(
                checkpoint_id=checkpoint["checkpoint_id"],
                passed=checkpoint["passed"],
                required=checkpoint["required"],
                assertions=tuple(
                    AssertionEvaluation(
                        assertion_id=assertion["assertion_id"],
                        passed=assertion["passed"],
                        required=assertion["required"],
                        evidence=tuple(
                            EvidenceRef(
                                trace_id=ref["trace_id"],
                                span_id=ref.get("span_id"),
                                event_id=ref.get("event_id"),
                                source_url=ref.get("source_url"),
                            )
                            for ref in assertion.get("evidence", [])
                        ),
                    )
                    for assertion in checkpoint.get("assertions", [])
                ),
            )
            for checkpoint in raw.get("checkpoints", [])
        ),
    )


def write_run_evaluation(
    evaluation: RunEvaluation,
    run_path: str | Path,
    output_path: str | Path | None = None,
) -> Path:
    if output_path is None:
        artifact_path = Path(run_path)
        output_path = (
            artifact_path / "evaluation.json"
            if artifact_path.is_dir()
            else artifact_path.with_name("evaluation.json")
        )

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as output_file:
        json.dump(asdict(evaluation), output_file, indent=2)
        output_file.write("\n")
    return path


def evaluate_run(task: BenchmarkTask, run: TrialRun) -> RunEvaluation:
    checkpoints = tuple(_evaluate_checkpoint(checkpoint, run) for checkpoint in task.checkpoints)
    required_checkpoints_passed = all(
        checkpoint.passed for checkpoint in checkpoints if checkpoint.required
    )
    passed = required_checkpoints_passed and run.final_state.passed

    return RunEvaluation(
        task_id=task.id,
        trial_id=run.trial.id,
        passed=passed,
        final_state_passed=run.final_state.passed,
        checkpoints=checkpoints,
    )


def format_run_evaluation(evaluation: RunEvaluation) -> str:
    lines = [
        f"Evaluation {evaluation.task_id}",
        f"trial={evaluation.trial_id}",
        f"passed={evaluation.passed}",
        f"final_state_passed={evaluation.final_state_passed}",
        "",
        "Checkpoints",
    ]

    for checkpoint in evaluation.checkpoints:
        lines.append(
            f"- {checkpoint.checkpoint_id}: "
            f"passed={checkpoint.passed} required={checkpoint.required}"
        )
        for assertion in checkpoint.assertions:
            evidence = ", ".join(_format_evidence_ref(ref) for ref in assertion.evidence)
            lines.append(
                f"  assertion={assertion.assertion_id} "
                f"passed={assertion.passed} required={assertion.required}"
            )
            if evidence:
                lines.append(f"    evidence={evidence}")

    return "\n".join(lines)


def _evaluate_checkpoint(
    checkpoint: CheckpointSpec,
    run: TrialRun,
) -> CheckpointEvaluation:
    assertions = tuple(_evaluate_assertion(assertion, run) for assertion in checkpoint.assertions)
    required_assertions_passed = all(
        assertion.passed for assertion in assertions if assertion.required
    )
    return CheckpointEvaluation(
        checkpoint_id=checkpoint.id,
        passed=required_assertions_passed,
        required=checkpoint.required,
        assertions=assertions,
    )


def _evaluate_assertion(
    assertion: AssertionSpec,
    run: TrialRun,
) -> AssertionEvaluation:
    evidence = []
    for span in run.spans:
        for event in span.events:
            if _event_matches_assertion(event, assertion):
                evidence.append(
                    EvidenceRef(
                        trace_id=span.trace_id,
                        span_id=span.id,
                        event_id=event.id,
                    )
                )

    return AssertionEvaluation(
        assertion_id=assertion.id,
        passed=bool(evidence),
        required=assertion.required,
        evidence=tuple(evidence),
    )


def _event_matches_assertion(event: TraceEvent, assertion: AssertionSpec) -> bool:
    if event.type != assertion.event_type:
        return False
    if event.attributes.get("funnelcake.runner.mode") == "placeholder":
        return False

    return all(
        _attribute_matches(event.attributes.get(key), expected)
        for key, expected in assertion.attributes.items()
    )


def _attribute_matches(actual: JsonValue, expected: JsonValue) -> bool:
    if isinstance(actual, str) and isinstance(expected, str):
        return actual == expected or (expected.startswith("/") and actual.endswith(expected))
    return actual == expected


def _format_evidence_ref(ref: EvidenceRef) -> str:
    parts = [f"trace_id={ref.trace_id}"]
    if ref.span_id is not None:
        parts.append(f"span_id={ref.span_id}")
    if ref.event_id is not None:
        parts.append(f"event_id={ref.event_id}")
    return " ".join(parts)
