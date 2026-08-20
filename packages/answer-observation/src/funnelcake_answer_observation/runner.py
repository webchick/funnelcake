from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import request

from .models import AnswerObservation, Citation, ObservationSet, ProbePrompt, Product, RetrievedSource


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


def run_openai_provider(path: str | Path, api_key: str | None = None) -> ObservationSet:
    with Path(path).open(encoding="utf-8") as config_file:
        raw = json.load(config_file)

    key = api_key or os.environ.get("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY is required for the OpenAI provider")

    prompts = tuple(_prompt(item) for item in raw.get("prompts", []))
    products = tuple(_product(item) for item in raw.get("products", []))
    provider = raw.get("provider", "openai")
    model = raw["model"]
    run_id = raw["id"]
    observations = []
    for index, prompt in enumerate(prompts, start=1):
        response = _openai_response(
            api_key=key,
            model=model,
            prompt=prompt.prompt,
            search_enabled=raw.get("search_enabled", False),
        )
        observations.append(
            AnswerObservation(
                id=f"{run_id}-obs-{index:03d}",
                run_id=run_id,
                prompt_id=prompt.id,
                prompt=prompt.prompt,
                raw_answer=_response_text(response),
                engine="responses",
                surface=raw.get("surface", "api"),
                provider=provider,
                model=model,
                model_version=raw.get("model_version"),
                search_enabled=raw.get("search_enabled", False),
                country=raw.get("country"),
                region=prompt.region,
                language=prompt.language,
                timestamp=_response_timestamp(response),
                run_number=raw.get("run_number", 1),
                repetition=raw.get("repetition", 1),
                raw_request={
                    "prompt_id": prompt.id,
                    "prompt": prompt.prompt,
                    "provider": provider,
                    "model": model,
                    "search_enabled": raw.get("search_enabled", False),
                },
                raw_response=response,
                citations=_response_citations(response),
            )
        )

    if not observations:
        raise ValueError("OpenAI provider config requires at least one prompt")

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


def run_perplexity_provider(path: str | Path, api_key: str | None = None) -> ObservationSet:
    with Path(path).open(encoding="utf-8") as config_file:
        raw = json.load(config_file)

    key = api_key or os.environ.get("PERPLEXITY_API_KEY")
    if not key:
        raise RuntimeError("PERPLEXITY_API_KEY is required for the Perplexity provider")

    prompts = tuple(_prompt(item) for item in raw.get("prompts", []))
    products = tuple(_product(item) for item in raw.get("products", []))
    provider = raw.get("provider", "perplexity")
    model = raw["model"]
    run_id = raw["id"]
    observations = []
    for index, prompt in enumerate(prompts, start=1):
        response = _perplexity_response(
            api_key=key,
            model=model,
            prompt=prompt.prompt,
        )
        observations.append(
            AnswerObservation(
                id=f"{run_id}-obs-{index:03d}",
                run_id=run_id,
                prompt_id=prompt.id,
                prompt=prompt.prompt,
                raw_answer=_chat_completion_text(response),
                engine="sonar",
                surface=raw.get("surface", "api"),
                provider=provider,
                model=response.get("model", model),
                model_version=raw.get("model_version"),
                search_enabled=True,
                country=raw.get("country"),
                region=prompt.region,
                language=prompt.language,
                timestamp=_chat_completion_timestamp(response),
                run_number=raw.get("run_number", 1),
                repetition=raw.get("repetition", 1),
                raw_request={
                    "prompt_id": prompt.id,
                    "prompt": prompt.prompt,
                    "provider": provider,
                    "model": model,
                },
                raw_response=response,
                citations=_perplexity_citations(response),
                retrieved_sources=_perplexity_retrieved_sources(response),
            )
        )

    if not observations:
        raise ValueError("Perplexity provider config requires at least one prompt")

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


def _openai_response(
    api_key: str,
    model: str,
    prompt: str,
    search_enabled: bool,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": model,
        "input": prompt,
        "store": False,
    }
    if search_enabled:
        payload["tools"] = [{"type": "web_search"}]
    body = json.dumps(payload).encode("utf-8")
    api_request = request.Request(
        "https://api.openai.com/v1/responses",
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with request.urlopen(api_request, timeout=120) as response:
        return json.loads(response.read().decode("utf-8"))


def _perplexity_response(
    api_key: str,
    model: str,
    prompt: str,
) -> dict[str, Any]:
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": prompt,
            }
        ],
    }
    body = json.dumps(payload).encode("utf-8")
    api_request = request.Request(
        "https://api.perplexity.ai/v1/sonar",
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with request.urlopen(api_request, timeout=120) as response:
        return json.loads(response.read().decode("utf-8"))


def _response_text(response: dict[str, Any]) -> str:
    if isinstance(response.get("output_text"), str):
        return response["output_text"]
    texts = []
    for item in response.get("output", []):
        for content in item.get("content", []):
            text = content.get("text")
            if isinstance(text, str):
                texts.append(text)
    return "\n".join(texts)


def _chat_completion_text(response: dict[str, Any]) -> str:
    choices = response.get("choices", [])
    if not choices:
        return ""
    message = choices[0].get("message", {})
    content = message.get("content")
    return content if isinstance(content, str) else ""


def _response_timestamp(response: dict[str, Any]) -> str | None:
    created_at = response.get("created_at")
    if isinstance(created_at, int | float):
        return datetime.fromtimestamp(created_at, timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(created_at, str):
        return created_at
    return None


def _chat_completion_timestamp(response: dict[str, Any]) -> str | None:
    created = response.get("created")
    if isinstance(created, int | float):
        return datetime.fromtimestamp(created, timezone.utc).isoformat().replace("+00:00", "Z")
    return None


def _response_citations(response: dict[str, Any]) -> tuple[Citation, ...]:
    citations = []
    seen_urls = set()
    for item in response.get("output", []):
        for content in item.get("content", []):
            for annotation in content.get("annotations", []):
                url = annotation.get("url")
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)
                citations.append(
                    Citation(
                        url=url,
                        title=annotation.get("title"),
                    )
                )
    return tuple(citations)


def _perplexity_citations(response: dict[str, Any]) -> tuple[Citation, ...]:
    return tuple(
        Citation(url=url)
        for url in response.get("citations", [])
        if isinstance(url, str)
    )


def _perplexity_retrieved_sources(response: dict[str, Any]) -> tuple[RetrievedSource, ...]:
    sources = []
    for index, item in enumerate(response.get("search_results", []), start=1):
        url = item.get("url")
        if not url:
            continue
        sources.append(
            RetrievedSource(
                url=url,
                title=item.get("title"),
                rank=index,
                attributes={
                    key: value
                    for key, value in item.items()
                    if key not in {"url", "title"}
                },
            )
        )
    return tuple(sources)


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
