from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import (
    AnswerObservation,
    Citation,
    Claim,
    EntityMention,
    ObservationSet,
    ProbePrompt,
    Product,
    RetrievedSource,
)


def load_observation_set(path: str | Path) -> ObservationSet:
    with Path(path).open(encoding="utf-8") as observation_file:
        raw = json.load(observation_file)

    observation_set = ObservationSet(
        id=raw["id"],
        subject_entity=raw["subject_entity"],
        subject_product_id=raw.get("subject_product_id"),
        description=raw.get("description"),
        prompts=tuple(_prompt(item) for item in raw.get("prompts", [])),
        products=tuple(_product(item) for item in raw.get("products", [])),
        observations=tuple(_observation(item) for item in raw.get("observations", [])),
        attributes=raw.get("attributes", {}),
    )
    validate_observation_set(observation_set)
    return observation_set


def validate_observation_set(observation_set: ObservationSet) -> None:
    if not observation_set.id:
        raise ValueError("observation set id is required")
    if not observation_set.subject_entity:
        raise ValueError("subject_entity is required")
    if not observation_set.observations:
        raise ValueError("at least one observation is required")

    observation_ids: set[str] = set()
    for observation in observation_set.observations:
        if observation.id in observation_ids:
            raise ValueError(f"duplicate observation id: {observation.id}")
        observation_ids.add(observation.id)
        if not observation.prompt_id:
            raise ValueError(f"observation {observation.id} prompt_id is required")
        if not observation.prompt:
            raise ValueError(f"observation {observation.id} prompt is required")


def _observation(record: dict[str, Any]) -> AnswerObservation:
    region = record.get("region", record.get("country"))
    return AnswerObservation(
        id=record["id"],
        prompt_id=record.get("prompt_id", record.get("promptId")),
        prompt=record["prompt"],
        raw_answer=record.get("raw_answer", record.get("answer", record.get("response", ""))),
        engine=record.get("engine"),
        surface=record.get("surface"),
        model=record.get("model"),
        model_version=record.get("model_version"),
        provider=record.get("provider"),
        search_enabled=record.get("search_enabled"),
        country=record.get("country"),
        region=region,
        language=record.get("language"),
        timestamp=record.get("timestamp"),
        run_number=record.get("run_number"),
        repetition=record.get("repetition", record.get("run_number")),
        run_id=record.get("run_id", record.get("runId")),
        success=record.get("success", True),
        failure_type=record.get("failure_type", record.get("failureType")),
        error_message=record.get("error_message", record.get("errorMessage")),
        retry_count=record.get("retry_count", record.get("retryCount", 0)),
        raw_request=record.get("raw_request", record.get("rawRequest", {})),
        raw_response=record.get("raw_response", record.get("rawResponse", {})),
        mentions=tuple(_mention(item) for item in record.get("mentions", [])),
        citations=tuple(_citation(item) for item in record.get("citations", [])),
        retrieved_sources=tuple(_retrieved_source(item) for item in record.get("retrieved_sources", [])),
        claims=tuple(_claim(item) for item in record.get("claims", [])),
        attributes=record.get("attributes", {}),
    )


def _prompt(record: dict[str, Any]) -> ProbePrompt:
    return ProbePrompt(
        id=record["id"],
        prompt=record["prompt"],
        intent=record.get("intent"),
        persona=record.get("persona"),
        task=record.get("task"),
        funnel_stage=record.get("funnel_stage", record.get("funnelStage")),
        language=record.get("language"),
        region=record.get("region"),
        tags=tuple(record.get("tags", [])),
        attributes=record.get("attributes", {}),
    )


def _product(record: dict[str, Any]) -> Product:
    return Product(
        id=record["id"],
        name=record["name"],
        aliases=tuple(record.get("aliases", [])),
        attributes=record.get("attributes", {}),
    )


def _mention(record: dict[str, Any]) -> EntityMention:
    return EntityMention(
        entity=record.get("entity", record.get("display_name", record.get("displayName", ""))),
        product_id=record.get("product_id", record.get("productId")),
        display_name=record.get("display_name", record.get("displayName")),
        role=record.get("role", "mentioned"),
        rank=record.get("rank", record.get("recommendation_position", record.get("recommendationPosition"))),
        stance=record.get("stance", record.get("sentiment")),
        claims=tuple(record.get("claims", [])),
        attributes=record.get("attributes", {}),
    )


def _citation(record: dict[str, Any]) -> Citation:
    return Citation(
        url=record["url"],
        title=record.get("title"),
        domain=record.get("domain"),
        entity=record.get("entity"),
        product_id=record.get("product_id", record.get("productId")),
        attributes=record.get("attributes", {}),
    )


def _retrieved_source(record: dict[str, Any]) -> RetrievedSource:
    return RetrievedSource(
        url=record["url"],
        title=record.get("title"),
        domain=record.get("domain"),
        rank=record.get("rank"),
        entity=record.get("entity"),
        product_id=record.get("product_id", record.get("productId")),
        attributes=record.get("attributes", {}),
    )


def _claim(record: dict[str, Any]) -> Claim:
    return Claim(
        text=record["text"],
        entity=record.get("entity"),
        support=record.get("support", "observed"),
        source_urls=tuple(record.get("source_urls", [])),
        attributes=record.get("attributes", {}),
    )
