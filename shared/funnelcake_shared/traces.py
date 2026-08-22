from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TypeAlias

JsonScalar: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]
Attributes: TypeAlias = dict[str, JsonValue]


class DessertStage(StrEnum):
    DISCOVER = "discover"
    EVALUATE = "evaluate"
    SELECT = "select"
    SETUP = "setup"
    EXECUTE = "execute"
    RETAIN = "retain"
    TRUST = "trust"

    @classmethod
    def _missing_(cls, value: object) -> DessertStage | None:
        if value == "repeat":
            return cls.RETAIN
        return None


class EvidenceGrade(StrEnum):
    CONFIRMED = "confirmed"
    STRONGLY_SUPPORTED = "strongly_supported"
    HYPOTHESIS = "hypothesis"
    OBSERVATION = "observation"


class TrialStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    INCONCLUSIVE = "inconclusive"


class SpanKind(StrEnum):
    INTERNAL = "internal"
    CLIENT = "client"
    SERVER = "server"
    PRODUCER = "producer"
    CONSUMER = "consumer"


class TraceEventType(StrEnum):
    SEARCH = "search"
    NAVIGATION = "navigation"
    TOOL_CALL = "tool_call"
    HTTP_REQUEST = "http_request"
    API_RESPONSE = "api_response"
    ERROR = "error"
    RETRY = "retry"
    HUMAN_INTERVENTION = "human_intervention"
    STATE_VERIFICATION = "state_verification"
    LLM_CALL = "llm_call"


@dataclass(frozen=True)
class StateVerification:
    expected: str
    observed: str
    passed: bool
    evidence: tuple["EvidenceRef", ...] = ()


@dataclass(frozen=True)
class EvidenceRef:
    trace_id: str
    span_id: str | None = None
    event_id: str | None = None
    source_url: str | None = None


@dataclass(frozen=True)
class TraceEvent:
    id: str
    timestamp: str
    name: str
    type: TraceEventType
    attributes: Attributes = field(default_factory=dict)
    body: JsonValue = None
    severity_text: str | None = None


@dataclass(frozen=True)
class Span:
    id: str
    trace_id: str
    name: str
    start_time: str
    end_time: str
    parent_span_id: str | None = None
    kind: SpanKind = SpanKind.INTERNAL
    status_code: str = "OK"
    status_message: str = ""
    attributes: Attributes = field(default_factory=dict)
    events: tuple[TraceEvent, ...] = ()


@dataclass(frozen=True)
class Trial:
    id: str
    stage: DessertStage
    task: str
    agent: str
    status: TrialStatus
    trace_id: str
    outcome_verified: bool
    task_family: str | None = None
    attributes: Attributes = field(default_factory=dict)


@dataclass(frozen=True)
class TrialRun:
    trial: Trial
    spans: tuple[Span, ...]
    final_state: StateVerification
    failures: tuple["Failure", ...] = ()


@dataclass(frozen=True)
class Failure:
    trial_id: str
    failure_type: str
    stage: DessertStage
    evidence: tuple[EvidenceRef, ...]
    summary: str | None = None


@dataclass(frozen=True)
class Diagnosis:
    id: str
    title: str
    stage: DessertStage
    evidence_grade: EvidenceGrade
    affected_trial_ids: tuple[str, ...]
    observed_pattern: str
    supporting_sources: tuple[str, ...] = ()
    suggested_intervention: str | None = None
    evidence: tuple[EvidenceRef, ...] = ()


@dataclass(frozen=True)
class StageMetric:
    stage: DessertStage
    name: str
    score: float
    numerator: int | None = None
    denominator: int | None = None
    evidence: tuple[EvidenceRef, ...] = ()
