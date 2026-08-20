from __future__ import annotations

from dataclasses import dataclass, field

from funnelcake_shared import Attributes


@dataclass(frozen=True)
class ProbePrompt:
    id: str
    prompt: str
    intent: str | None = None
    persona: str | None = None
    task: str | None = None
    funnel_stage: str | None = None
    language: str | None = None
    region: str | None = None
    tags: tuple[str, ...] = ()
    attributes: Attributes = field(default_factory=dict)


@dataclass(frozen=True)
class Product:
    id: str
    name: str
    aliases: tuple[str, ...] = ()
    attributes: Attributes = field(default_factory=dict)


@dataclass(frozen=True)
class EntityMention:
    entity: str
    product_id: str | None = None
    display_name: str | None = None
    role: str = "mentioned"
    rank: int | None = None
    stance: str | None = None
    claims: tuple[str, ...] = ()
    attributes: Attributes = field(default_factory=dict)


@dataclass(frozen=True)
class Citation:
    url: str
    title: str | None = None
    domain: str | None = None
    entity: str | None = None
    product_id: str | None = None
    attributes: Attributes = field(default_factory=dict)


@dataclass(frozen=True)
class RetrievedSource:
    url: str
    title: str | None = None
    domain: str | None = None
    rank: int | None = None
    entity: str | None = None
    product_id: str | None = None
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
    region: str | None = None
    language: str | None = None
    timestamp: str | None = None
    run_number: int | None = None
    repetition: int | None = None
    run_id: str | None = None
    success: bool = True
    failure_type: str | None = None
    error_message: str | None = None
    retry_count: int = 0
    raw_request: Attributes = field(default_factory=dict)
    raw_response: Attributes = field(default_factory=dict)
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
    subject_product_id: str | None = None
    description: str | None = None
    prompts: tuple[ProbePrompt, ...] = ()
    products: tuple[Product, ...] = ()
    attributes: Attributes = field(default_factory=dict)


@dataclass(frozen=True)
class EntityVisibility:
    entity: str
    response_count: int
    mention_count: int
    mention_rate: float
    recommended_count: int
    recommended_rate: float
    first_choice_count: int
    first_choice_rate: float
    citation_count: int
    retrieved_count: int
    recommendation_share: float
    average_rank: float | None = None
    display_name: str | None = None


@dataclass(frozen=True)
class ObservationSummary:
    observation_set_id: str
    response_count: int
    subject_entity: str
    subject_visibility: EntityVisibility
    entity_visibility: tuple[EntityVisibility, ...]
    top_cited_urls: tuple[tuple[str, int], ...]
    top_cited_domains: tuple[tuple[str, int], ...]
    top_retrieved_urls: tuple[tuple[str, int], ...]
    top_retrieved_domains: tuple[tuple[str, int], ...]
    top_claims: tuple[tuple[str, int], ...]
    recommendation_consistency: tuple[tuple[str, str, int, int, float], ...]


@dataclass(frozen=True)
class EntityVisibilityChange:
    entity: str
    display_name: str | None
    before_mention_rate: float
    after_mention_rate: float
    mention_rate_change: float
    before_recommended_rate: float
    after_recommended_rate: float
    recommended_rate_change: float
    before_first_choice_rate: float
    after_first_choice_rate: float
    first_choice_rate_change: float
    before_recommendation_share: float
    after_recommendation_share: float
    recommendation_share_change: float


@dataclass(frozen=True)
class ObservationComparison:
    baseline_id: str
    followup_id: str
    subject_entity: str
    baseline_response_count: int
    followup_response_count: int
    entity_changes: tuple[EntityVisibilityChange, ...]


@dataclass(frozen=True)
class ObservationValidationReport:
    path: str
    valid: bool
    observation_set_id: str | None = None
    observation_count: int = 0
    prompt_count: int = 0
    product_count: int = 0
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
