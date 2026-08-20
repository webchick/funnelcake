from __future__ import annotations

from dataclasses import dataclass, field

from funnelcake_shared import Attributes, DessertStage, TraceEventType


@dataclass(frozen=True)
class AssertionSpec:
    id: str
    description: str
    event_type: TraceEventType
    required: bool = True
    attributes: Attributes = field(default_factory=dict)


@dataclass(frozen=True)
class CheckpointSpec:
    id: str
    description: str
    stage: DessertStage
    required: bool = True
    assertions: tuple[AssertionSpec, ...] = ()


@dataclass(frozen=True)
class FinalStateSpec:
    expected: str
    verification: str
    required: bool = True


@dataclass(frozen=True)
class BenchmarkTask:
    id: str
    name: str
    stage: DessertStage
    prompt: str
    final_state: FinalStateSpec
    task_family: str | None = None
    checkpoints: tuple[CheckpointSpec, ...] = ()
    failure_type_hints: tuple[str, ...] = ()
    expected_signals: tuple[str, ...] = ()


TaskSpec = BenchmarkTask


@dataclass(frozen=True)
class JourneySpec:
    id: str
    name: str
    description: str
    tasks: tuple[BenchmarkTask, ...]


@dataclass(frozen=True)
class BenchmarkSpec:
    platform: str
    tasks: tuple[BenchmarkTask, ...]
