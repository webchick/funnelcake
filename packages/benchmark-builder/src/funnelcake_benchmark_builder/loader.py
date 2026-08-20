from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from funnelcake_shared import DessertStage, TraceEventType

from .models import AssertionSpec, BenchmarkTask, CheckpointSpec, FinalStateSpec


def load_task_spec(path: str | Path) -> BenchmarkTask:
    with Path(path).open(encoding="utf-8") as task_file:
        raw = json.load(task_file)
    task = _task(raw)
    validate_task_spec(task)
    return task


def validate_task_spec(task: BenchmarkTask) -> None:
    if not task.id:
        raise ValueError("task id is required")
    if not task.name:
        raise ValueError("task name is required")
    if not task.prompt:
        raise ValueError("task prompt is required")
    if not task.final_state.expected:
        raise ValueError("task final_state.expected is required")
    if not task.final_state.verification:
        raise ValueError("task final_state.verification is required")

    assertion_ids: set[str] = set()
    for checkpoint in task.checkpoints:
        if checkpoint.stage != task.stage:
            raise ValueError(
                f"checkpoint {checkpoint.id} stage {checkpoint.stage.value} "
                f"does not match task stage {task.stage.value}"
            )
        for assertion in checkpoint.assertions:
            if assertion.id in assertion_ids:
                raise ValueError(f"duplicate assertion id: {assertion.id}")
            assertion_ids.add(assertion.id)


def format_task_spec(task: BenchmarkTask) -> str:
    lines = [
        f"Task {task.id}",
        f"name={task.name}",
        f"stage={task.stage.value}",
        f"family={task.task_family or ''}",
        f"prompt={task.prompt}",
        "",
        "Final State",
        f"expected={task.final_state.expected}",
        f"verification={task.final_state.verification}",
    ]

    if task.checkpoints:
        lines.extend(["", "Checkpoints"])
        for checkpoint in task.checkpoints:
            lines.append(f"- {checkpoint.id}: {checkpoint.description}")
            for assertion in checkpoint.assertions:
                lines.append(
                    f"  assertion={assertion.id} "
                    f"type={assertion.event_type.value} "
                    f"required={assertion.required}"
                )

    if task.failure_type_hints:
        lines.extend(["", "Failure Type Hints"])
        lines.extend(f"- {hint}" for hint in task.failure_type_hints)

    return "\n".join(lines)


def _task(record: dict[str, Any]) -> BenchmarkTask:
    return BenchmarkTask(
        id=record["id"],
        name=record["name"],
        stage=DessertStage(record["stage"]),
        prompt=record["prompt"],
        final_state=FinalStateSpec(
            expected=record["final_state"]["expected"],
            verification=record["final_state"]["verification"],
            required=record["final_state"].get("required", True),
        ),
        task_family=record.get("task_family"),
        checkpoints=tuple(_checkpoint(item) for item in record.get("checkpoints", [])),
        failure_type_hints=tuple(record.get("failure_type_hints", [])),
        expected_signals=tuple(record.get("expected_signals", [])),
    )


def _checkpoint(record: dict[str, Any]) -> CheckpointSpec:
    return CheckpointSpec(
        id=record["id"],
        description=record["description"],
        stage=DessertStage(record["stage"]),
        required=record.get("required", True),
        assertions=tuple(_assertion(item) for item in record.get("assertions", [])),
    )


def _assertion(record: dict[str, Any]) -> AssertionSpec:
    return AssertionSpec(
        id=record["id"],
        description=record["description"],
        event_type=TraceEventType(record["event_type"]),
        required=record.get("required", True),
        attributes=record.get("attributes", {}),
    )
