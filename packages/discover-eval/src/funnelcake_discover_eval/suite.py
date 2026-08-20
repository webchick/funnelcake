from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .diagnosis import diagnose_task_run, write_diagnosis_bundle
from .evaluator import evaluate_task_run, write_run_evaluation
from .runner import run_task_spec


@dataclass(frozen=True)
class SuiteRunResult:
    task_path: Path
    trial_id: str
    trace_id: str
    run_dir: Path
    passed: bool
    diagnosis_count: int


@dataclass(frozen=True)
class SuiteRun:
    artifacts_dir: Path
    results: tuple[SuiteRunResult, ...]


def run_task_suite(
    task_paths: tuple[str | Path, ...],
    artifacts_dir: str | Path = "artifacts",
    agent: str = "manual-placeholder",
) -> SuiteRun:
    resolved_tasks = discover_task_specs(task_paths)
    results = []

    for task_path in resolved_tasks:
        run, run_dir = run_task_spec(task_path, artifacts_dir=artifacts_dir, agent=agent)
        evaluation = evaluate_task_run(task_path, run_dir)
        write_run_evaluation(evaluation, run_dir)
        diagnosis = diagnose_task_run(task_path, run_dir)
        write_diagnosis_bundle(diagnosis, run_dir)
        results.append(
            SuiteRunResult(
                task_path=task_path,
                trial_id=run.trial.id,
                trace_id=run.trial.trace_id,
                run_dir=run_dir,
                passed=evaluation.passed,
                diagnosis_count=len(diagnosis.diagnoses),
            )
        )

    return SuiteRun(
        artifacts_dir=Path(artifacts_dir),
        results=tuple(results),
    )


def discover_task_specs(paths: tuple[str | Path, ...]) -> tuple[Path, ...]:
    task_files = []
    for raw_path in paths:
        path = Path(raw_path)
        if path.is_dir():
            task_files.extend(sorted(path.glob("*.json")))
        else:
            task_files.append(path)

    return tuple(dict.fromkeys(task_files))


def format_suite_run(suite: SuiteRun) -> str:
    lines = [
        "Suite run",
        f"artifacts_dir={suite.artifacts_dir}",
        f"tasks={len(suite.results)}",
        "",
        "Runs",
    ]

    for result in suite.results:
        lines.append(
            f"- task={result.task_path} trial={result.trial_id} "
            f"passed={result.passed} diagnoses={result.diagnosis_count} "
            f"run_dir={result.run_dir}"
        )

    return "\n".join(lines)
