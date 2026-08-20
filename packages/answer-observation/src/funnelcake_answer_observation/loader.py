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
    RetrievedSource,
)


def load_observation_set(path: str | Path) -> ObservationSet:
    with Path(path).open(encoding="utf-8") as observation_file:
        raw = json.load(observation_file)

    observation_set = ObservationSet(
        id=raw["id"],
        subject_entity=raw["subject_entity"],
        description=raw.get("description"),
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
    return AnswerObservation(
        id=record["id"],
        prompt_id=record["prompt_id"],
        prompt=record["prompt"],
        raw_answer=record.get("raw_answer", record.get("response", "")),
        engine=record.get("engine"),
        surface=record.get("surface"),
        model=record.get("model"),
        model_version=record.get("model_version"),
        provider=record.get("provider"),
        search_enabled=record.get("search_enabled"),
        country=record.get("country"),
        language=record.get("language"),
        timestamp=record.get("timestamp"),
        run_number=record.get("run_number"),
        run_id=record.get("run_id"),
        mentions=tuple(_mention(item) for item in record.get("mentions", [])),
        citations=tuple(_citation(item) for item in record.get("citations", [])),
        retrieved_sources=tuple(_retrieved_source(item) for item in record.get("retrieved_sources", [])),
        claims=tuple(_claim(item) for item in record.get("claims", [])),
        attributes=record.get("attributes", {}),
    )


def _mention(record: dict[str, Any]) -> EntityMention:
    return EntityMention(
        entity=record["entity"],
        role=record.get("role", "mentioned"),
        rank=record.get("rank"),
        sentiment=record.get("sentiment"),
        attributes=record.get("attributes", {}),
    )


def _citation(record: dict[str, Any]) -> Citation:
    return Citation(
        url=record["url"],
        title=record.get("title"),
        entity=record.get("entity"),
        attributes=record.get("attributes", {}),
    )


def _retrieved_source(record: dict[str, Any]) -> RetrievedSource:
    return RetrievedSource(
        url=record["url"],
        title=record.get("title"),
        rank=record.get("rank"),
        entity=record.get("entity"),
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
