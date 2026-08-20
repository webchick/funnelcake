from __future__ import annotations

from dataclasses import dataclass, field

from funnelcake_shared import Attributes


@dataclass(frozen=True)
class EntityMention:
    entity: str
    role: str = "mentioned"
    rank: int | None = None
    sentiment: str | None = None
    attributes: Attributes = field(default_factory=dict)


@dataclass(frozen=True)
class Citation:
    url: str
    title: str | None = None
    entity: str | None = None
    attributes: Attributes = field(default_factory=dict)


@dataclass(frozen=True)
class RetrievedSource:
    url: str
    title: str | None = None
    rank: int | None = None
    entity: str | None = None
    attributes: Attributes = field(default_factory=dict)


@dataclass(frozen=True)
class Claim:
    text: str
    entity: str | None = None
    support: str = "observed"
    source_urls: tuple[str, ...] = ()
    attributes: Attributes = field(default_factory=dict)


@dataclass(frozen=True)
class AnswerObservation:
    id: str
    prompt_id: str
    prompt: str
    raw_answer: str
    engine: str | None = None
    surface: str | None = None
    model: str | None = None
    model_version: str | None = None
    provider: str | None = None
    search_enabled: bool | None = None
    country: str | None = None
    language: str | None = None
    timestamp: str | None = None
    run_number: int | None = None
    run_id: str | None = None
    mentions: tuple[EntityMention, ...] = ()
    citations: tuple[Citation, ...] = ()
    retrieved_sources: tuple[RetrievedSource, ...] = ()
    claims: tuple[Claim, ...] = ()
    attributes: Attributes = field(default_factory=dict)


@dataclass(frozen=True)
class ObservationSet:
    id: str
    subject_entity: str
    observations: tuple[AnswerObservation, ...]
    description: str | None = None
    attributes: Attributes = field(default_factory=dict)


@dataclass(frozen=True)
class EntityVisibility:
    entity: str
    response_count: int
    mention_count: int
    mention_rate: float
    recommended_count: int
    recommended_rate: float
    citation_count: int
    retrieved_count: int
    average_rank: float | None = None


@dataclass(frozen=True)
class ObservationSummary:
    observation_set_id: str
    response_count: int
    subject_entity: str
    subject_visibility: EntityVisibility
    entity_visibility: tuple[EntityVisibility, ...]
    top_cited_urls: tuple[tuple[str, int], ...]
    top_retrieved_urls: tuple[tuple[str, int], ...]
    top_claims: tuple[tuple[str, int], ...]
