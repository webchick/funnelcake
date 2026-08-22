from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from funnelcake_shared import Attributes, DessertStage, JsonValue, ProductFunnelStage


class CollectorCapability(StrEnum):
    ANSWER_OBSERVATION = "answer_observation"
    MCP_INSPECTION = "mcp_inspection"
    AGENT_EVALUATION = "agent_evaluation"
    TRACE_IMPORT = "trace_import"
    DOCS_CRAWL = "docs_crawl"
    BROWSER_RUN = "browser_run"
    MANUAL_OBSERVATION = "manual_observation"


class ObservationConfidence(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class EvidenceArtifactKind(StrEnum):
    JSON = "json"
    TRANSCRIPT = "transcript"
    TRACE = "trace"
    SCREENSHOT = "screenshot"
    URL = "url"
    TEXT = "text"


@dataclass(frozen=True)
class Experiment:
    id: str
    capability: CollectorCapability
    input_path: str | None = None
    task_id: str | None = None
    actor: str | None = None
    attributes: Attributes = field(default_factory=dict)


@dataclass(frozen=True)
class EvidenceArtifact:
    id: str
    kind: EvidenceArtifactKind
    uri: str | None = None
    summary: str | None = None
    content: JsonValue = None


@dataclass(frozen=True)
class ObservationProvenance:
    collector: str
    collector_version: str
    source: str | None = None
    raw_artifact_id: str | None = None


@dataclass(frozen=True)
class Observation:
    id: str
    experiment_id: str
    task_id: str | None
    actor: str | None
    journey_stage: ProductFunnelStage | None
    dessert_stage: DessertStage | None
    signal: str
    value: JsonValue
    success: bool | None
    timestamp: str | None
    evidence: tuple[EvidenceArtifact, ...]
    provenance: ObservationProvenance
    confidence: ObservationConfidence = ObservationConfidence.MEDIUM
    attributes: Attributes = field(default_factory=dict)


class Collector(Protocol):
    id: str
    version: str

    def supports(self, capability: CollectorCapability) -> bool:
        ...

    def collect(self, experiment: Experiment) -> tuple[Observation, ...]:
        ...


def require_input_path(experiment: Experiment) -> Path:
    if experiment.input_path is None:
        raise ValueError(f"experiment {experiment.id} requires input_path")
    return Path(experiment.input_path)
