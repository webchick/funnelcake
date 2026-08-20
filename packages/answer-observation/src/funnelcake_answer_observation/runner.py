from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import AnswerObservation, Citation, ObservationSet, ProbePrompt, Product


def run_fixture_provider(path: str | Path) -> ObservationSet:
    with Path(path).open(encoding="utf-8") as config_file:
        raw = json.load(config_file)

    prompts = tuple(_prompt(item) for item in raw.get("prompts", []))
    products = tuple(_product(item) for item in raw.get("products", []))
    prompt_by_id = {prompt.id: prompt for prompt in prompts}
    provider = raw.get("provider", "fixture")
    model = raw.get("model", "fixture-model")
    surface = raw.get("surface", "fixture")
    search_enabled = raw.get("search_enabled", False)
    run_id = raw["id"]

    observations = []
    for index, answer in enumerate(raw.get("answers", []), start=1):
        prompt_id = _field(answer, "prompt_id", "promptId")
        if prompt_id not in prompt_by_id:
            raise ValueError(f"answer references unknown prompt_id: {prompt_id}")
        prompt = prompt_by_id[prompt_id]
        observations.append(
            AnswerObservation(
                id=answer.get("id", f"{run_id}-obs-{index:03d}"),
                run_id=run_id,
                prompt_id=prompt.id,
                prompt=prompt.prompt,
                raw_answer=_field(answer, "raw_answer", "answer", "response", default=""),
                engine=raw.get("engine", "fixture"),
                surface=answer.get("surface", surface),
                provider=answer.get("provider", provider),
                model=answer.get("model", model),
                model_version=_field(answer, "model_version", "modelVersion", default=raw.get("model_version")),
                search_enabled=answer.get("search_enabled", search_enabled),
                country=answer.get("country", raw.get("country")),
                region=answer.get("region", prompt.region),
                language=answer.get("language", prompt.language),
                timestamp=answer.get("timestamp"),
                run_number=answer.get("run_number", raw.get("run_number", 1)),
                repetition=answer.get("repetition", raw.get("repetition", 1)),
                raw_request={
                    "prompt_id": prompt.id,
                    "prompt": prompt.prompt,
                    "provider": provider,
                    **answer.get("raw_request", {}),
                },
                raw_response=answer.get("raw_response", {"fixture": True}),
                citations=tuple(_citation(item) for item in answer.get("citations", [])),
                attributes=answer.get("attributes", {}),
            )
        )

    if not observations:
        raise ValueError("fixture provider config requires at least one answer")

    return ObservationSet(
        id=run_id,
        subject_entity=_field(raw, "subject_entity", "subjectEntity"),
        subject_product_id=_field(raw, "subject_product_id", "subjectProductId"),
        description=raw.get("description"),
        prompts=prompts,
        products=products,
        observations=tuple(observations),
        attributes={
            "provider_config": str(path),
            "provider": provider,
            **raw.get("attributes", {}),
        },
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


def _citation(record: dict[str, Any]) -> Citation:
    return Citation(
        url=record["url"],
        title=record.get("title"),
        domain=record.get("domain"),
        entity=record.get("entity"),
        product_id=_field(record, "product_id", "productId"),
        attributes=record.get("attributes", {}),
    )


def _field(record: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in record:
            return record[key]
    return default
