from __future__ import annotations

import json
from dataclasses import asdict
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
        subject_entity=_field(raw, "subject_entity", "subjectEntity"),
        subject_product_id=_field(raw, "subject_product_id", "subjectProductId"),
        description=raw.get("description"),
        prompts=tuple(_prompt(item) for item in raw.get("prompts", [])),
        products=tuple(_product(item) for item in raw.get("products", [])),
        observations=tuple(_observation(item) for item in raw.get("observations", [])),
        attributes=raw.get("attributes", {}),
    )
    validate_observation_set(observation_set)
    return observation_set


def write_observation_set(observation_set: ObservationSet, path: str | Path) -> Path:
    validate_observation_set(observation_set)
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as observation_file:
        json.dump(asdict(observation_set), observation_file, indent=2)
        observation_file.write("\n")
    return output_path


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
        prompt_id=_field(record, "prompt_id", "promptId"),
        prompt=record["prompt"],
        raw_answer=_field(record, "raw_answer", "answer", "response", "output", default=""),
        engine=record.get("engine"),
        surface=record.get("surface"),
        model=record.get("model"),
        model_version=_field(record, "model_version", "modelVersion"),
        provider=record.get("provider"),
        search_enabled=_field(record, "search_enabled", "searchEnabled"),
        country=record.get("country"),
        region=region,
        language=record.get("language"),
        timestamp=record.get("timestamp"),
        run_number=_field(record, "run_number", "runNumber"),
        repetition=_field(record, "repetition", "run_number", "runNumber"),
        run_id=_field(record, "run_id", "runId"),
        success=record.get("success", True),
        failure_type=_field(record, "failure_type", "failureType"),
        error_message=_field(record, "error_message", "errorMessage"),
        retry_count=_field(record, "retry_count", "retryCount", default=0),
        raw_request=_field(record, "raw_request", "rawRequest", default={}),
        raw_response=_field(record, "raw_response", "rawResponse", default={}),
        mentions=tuple(_mention(item) for item in record.get("mentions", [])),
        citations=tuple(_citation(item) for item in record.get("citations", [])),
        retrieved_sources=tuple(
            _retrieved_source(item)
            for item in _field(record, "retrieved_sources", "retrievedSources", default=[])
        ),
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
        funnel_stage=_field(record, "funnel_stage", "funnelStage"),
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
        entity=_field(record, "entity", "display_name", "displayName", default=""),
        product_id=_field(record, "product_id", "productId"),
        display_name=_field(record, "display_name", "displayName"),
        role=record.get("role", "mentioned"),
        rank=_field(record, "rank", "recommendation_position", "recommendationPosition"),
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
        product_id=_field(record, "product_id", "productId"),
        attributes=record.get("attributes", {}),
    )


def _retrieved_source(record: dict[str, Any]) -> RetrievedSource:
    return RetrievedSource(
        url=record["url"],
        title=record.get("title"),
        domain=record.get("domain"),
        rank=record.get("rank"),
        entity=record.get("entity"),
        product_id=_field(record, "product_id", "productId"),
        attributes=record.get("attributes", {}),
    )


def _claim(record: dict[str, Any]) -> Claim:
    return Claim(
        text=record["text"],
        entity=record.get("entity"),
        support=record.get("support", "observed"),
        source_urls=tuple(_field(record, "source_urls", "sourceUrls", default=[])),
        attributes=record.get("attributes", {}),
    )


def _field(record: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in record:
            return record[key]
    return default
