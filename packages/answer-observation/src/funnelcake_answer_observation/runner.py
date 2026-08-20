from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import request
from urllib.parse import quote

from .models import AnswerObservation, Citation, ObservationSet, ProbePrompt, Product, RetrievedSource


PROVIDER_DEFAULT_MODELS = {
    "fixture": "fixture-answer-engine",
    "openai": "gpt-5.6",
    "gemini": "gemini-3.5-flash",
    "perplexity": "sonar-pro",
}


def run_provider_corpus(
    path: str | Path,
    providers: tuple[str, ...],
    repeat: int = 1,
) -> ObservationSet:
    raw = _load_config(path)
    if repeat < 1:
        raise ValueError("repeat must be at least 1")
    if not providers:
        raise ValueError("at least one provider is required")

    prompts = tuple(_prompt(item) for item in raw.get("prompts", []))
    products = tuple(_product(item) for item in raw.get("products", []))
    if not prompts:
        raise ValueError("provider corpus requires at least one prompt")

    run_id = raw.get("id", f"geo-run-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}")
    observations = []
    observation_index = 0
    for repetition in range(1, repeat + 1):
        for provider in providers:
            normalized_provider = provider.strip().lower()
            if not normalized_provider:
                continue
            for prompt in prompts:
                observation_index += 1
                observations.append(
                    _run_provider_observation(
                        raw=raw,
                        run_id=run_id,
                        observation_index=observation_index,
                        prompt=prompt,
                        provider=normalized_provider,
                        repetition=repetition,
                    )
                )

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
            "providers": tuple(providers),
            "repeat": repeat,
            **raw.get("attributes", {}),
        },
    )


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


def run_gemini_provider(path: str | Path, api_key: str | None = None) -> ObservationSet:
    with Path(path).open(encoding="utf-8") as config_file:
        raw = json.load(config_file)

    key = api_key or os.environ.get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY is required for the Gemini provider")

    prompts = tuple(_prompt(item) for item in raw.get("prompts", []))
    products = tuple(_product(item) for item in raw.get("products", []))
    provider = raw.get("provider", "google")
    model = raw["model"]
    run_id = raw["id"]
    search_enabled = raw.get("search_enabled", True)
    observations = []
    for index, prompt in enumerate(prompts, start=1):
        observed_at = _current_timestamp()
        response = _gemini_response(
            api_key=key,
            model=model,
            prompt=prompt.prompt,
            search_enabled=search_enabled,
        )
        observations.append(
            AnswerObservation(
                id=f"{run_id}-obs-{index:03d}",
                run_id=run_id,
                prompt_id=prompt.id,
                prompt=prompt.prompt,
                raw_answer=_gemini_text(response),
                engine="generateContent",
                surface=raw.get("surface", "api"),
                provider=provider,
                model=model,
                model_version=raw.get("model_version"),
                search_enabled=search_enabled,
                country=raw.get("country"),
                region=prompt.region,
                language=prompt.language,
                timestamp=observed_at,
                run_number=raw.get("run_number", 1),
                repetition=raw.get("repetition", 1),
                raw_request={
                    "prompt_id": prompt.id,
                    "prompt": prompt.prompt,
                    "provider": provider,
                    "model": model,
                    "search_enabled": search_enabled,
                },
                raw_response=response,
                citations=_gemini_citations(response),
                retrieved_sources=_gemini_retrieved_sources(response),
                attributes={
                    "web_search_queries": _gemini_web_search_queries(response),
                },
            )
        )

    if not observations:
        raise ValueError("Gemini provider config requires at least one prompt")

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


def _run_provider_observation(
    raw: dict[str, Any],
    run_id: str,
    observation_index: int,
    prompt: ProbePrompt,
    provider: str,
    repetition: int,
) -> AnswerObservation:
    model = _provider_model(raw, provider)
    observed_at = _current_timestamp()
    raw_request = {
        "prompt_id": prompt.id,
        "prompt": prompt.prompt,
        "provider": provider,
        "model": model,
        "search_enabled": _provider_search_enabled(raw, provider),
        "repetition": repetition,
    }
    try:
        response = _provider_response(raw, provider, model, prompt)
        return _successful_provider_observation(
            raw=raw,
            run_id=run_id,
            observation_index=observation_index,
            prompt=prompt,
            provider=provider,
            model=model,
            repetition=repetition,
            observed_at=observed_at,
            raw_request=raw_request,
            response=response,
        )
    except Exception as exc:
        return AnswerObservation(
            id=f"{run_id}-obs-{observation_index:03d}",
            run_id=run_id,
            prompt_id=prompt.id,
            prompt=prompt.prompt,
            raw_answer="",
            engine=_provider_engine(provider),
            surface=raw.get("surface", "api"),
            provider=provider,
            model=model,
            search_enabled=_provider_search_enabled(raw, provider),
            country=raw.get("country"),
            region=prompt.region,
            language=prompt.language,
            timestamp=observed_at,
            run_number=raw.get("run_number", 1),
            repetition=repetition,
            success=False,
            failure_type="provider_error",
            error_message=str(exc),
            raw_request=raw_request,
            raw_response={},
        )


def _successful_provider_observation(
    raw: dict[str, Any],
    run_id: str,
    observation_index: int,
    prompt: ProbePrompt,
    provider: str,
    model: str,
    repetition: int,
    observed_at: str,
    raw_request: dict[str, Any],
    response: dict[str, Any],
) -> AnswerObservation:
    raw_answer = _provider_text(provider, response)
    return AnswerObservation(
        id=f"{run_id}-obs-{observation_index:03d}",
        run_id=run_id,
        prompt_id=prompt.id,
        prompt=prompt.prompt,
        raw_answer=raw_answer,
        engine=_provider_engine(provider),
        surface=raw.get("surface", "api"),
        provider=provider,
        model=response.get("model", model),
        model_version=raw.get("model_version"),
        search_enabled=_provider_search_enabled(raw, provider),
        country=raw.get("country"),
        region=prompt.region,
        language=prompt.language,
        timestamp=_provider_timestamp(provider, response) or observed_at,
        run_number=raw.get("run_number", 1),
        repetition=repetition,
        raw_request=raw_request,
        raw_response=response,
        citations=_provider_citations(provider, response),
        retrieved_sources=_provider_retrieved_sources(provider, response),
        attributes=_provider_attributes(provider, response),
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


def _load_config(path: str | Path) -> dict[str, Any]:
    config_path = Path(path)
    with config_path.open(encoding="utf-8") as config_file:
        if config_path.suffix.lower() in {".yaml", ".yml"}:
            try:
                import yaml
            except ModuleNotFoundError:
                loaded = json.load(config_file)
            else:
                loaded = yaml.safe_load(config_file)
        else:
            loaded = json.load(config_file)
    if not isinstance(loaded, dict):
        raise ValueError(f"config must be a mapping: {path}")
    return loaded


def _provider_config(raw: dict[str, Any], provider: str) -> dict[str, Any]:
    providers = raw.get("providers", {})
    if isinstance(providers, dict):
        config = providers.get(provider, {})
        return config if isinstance(config, dict) else {}
    return {}


def _provider_model(raw: dict[str, Any], provider: str) -> str:
    config = _provider_config(raw, provider)
    models = raw.get("models", {})
    if isinstance(models, dict) and isinstance(models.get(provider), str):
        return models[provider]
    if isinstance(config.get("model"), str):
        return config["model"]
    if isinstance(raw.get("model"), str):
        return raw["model"]
    if provider in PROVIDER_DEFAULT_MODELS:
        return PROVIDER_DEFAULT_MODELS[provider]
    raise ValueError(f"unknown provider: {provider}")


def _provider_search_enabled(raw: dict[str, Any], provider: str) -> bool:
    config = _provider_config(raw, provider)
    if "search_enabled" in config:
        return bool(config["search_enabled"])
    return bool(raw.get("search_enabled", provider in {"gemini", "perplexity"}))


def _provider_response(
    raw: dict[str, Any],
    provider: str,
    model: str,
    prompt: ProbePrompt,
) -> dict[str, Any]:
    if provider == "fixture":
        return _fixture_response(raw, prompt, model)
    if provider == "openai":
        key = os.environ.get("OPENAI_API_KEY")
        if not key:
            raise RuntimeError("OPENAI_API_KEY is required for the OpenAI provider")
        return _openai_response(
            api_key=key,
            model=model,
            prompt=prompt.prompt,
            search_enabled=_provider_search_enabled(raw, provider),
        )
    if provider == "gemini":
        key = os.environ.get("GEMINI_API_KEY")
        if not key:
            raise RuntimeError("GEMINI_API_KEY is required for the Gemini provider")
        return _gemini_response(
            api_key=key,
            model=model,
            prompt=prompt.prompt,
            search_enabled=_provider_search_enabled(raw, provider),
        )
    if provider == "perplexity":
        key = os.environ.get("PERPLEXITY_API_KEY")
        if not key:
            raise RuntimeError("PERPLEXITY_API_KEY is required for the Perplexity provider")
        return _perplexity_response(api_key=key, model=model, prompt=prompt.prompt)
    raise ValueError(f"unknown provider: {provider}")


def _fixture_response(raw: dict[str, Any], prompt: ProbePrompt, model: str) -> dict[str, Any]:
    answer = None
    for item in raw.get("answers", []):
        if _field(item, "prompt_id", "promptId", default=None) == prompt.id:
            answer = _field(item, "raw_answer", "answer", "response", default=None)
            break
    if answer is None:
        answer = prompt.attributes.get("fixture_answer") if isinstance(prompt.attributes, dict) else None
    if answer is None:
        answer = f"Fixture answer for {prompt.id}."
    return {
        "model": model,
        "created_at": _current_timestamp(),
        "output_text": answer,
        "output": [],
        "fixture": True,
    }


def _provider_engine(provider: str) -> str:
    return {
        "fixture": "fixture",
        "openai": "responses",
        "gemini": "generateContent",
        "perplexity": "sonar",
    }.get(provider, provider)


def _provider_text(provider: str, response: dict[str, Any]) -> str:
    if provider == "gemini":
        return _gemini_text(response)
    if provider == "perplexity":
        return _chat_completion_text(response)
    return _response_text(response)


def _provider_timestamp(provider: str, response: dict[str, Any]) -> str | None:
    if provider == "perplexity":
        return _chat_completion_timestamp(response)
    return _response_timestamp(response)


def _provider_citations(provider: str, response: dict[str, Any]) -> tuple[Citation, ...]:
    if provider == "gemini":
        return _gemini_citations(response)
    if provider == "perplexity":
        return _perplexity_citations(response)
    return _response_citations(response)


def _provider_retrieved_sources(provider: str, response: dict[str, Any]) -> tuple[RetrievedSource, ...]:
    if provider == "gemini":
        return _gemini_retrieved_sources(response)
    if provider == "perplexity":
        return _perplexity_retrieved_sources(response)
    return ()


def _provider_attributes(provider: str, response: dict[str, Any]) -> dict[str, Any]:
    if provider == "gemini":
        return {"web_search_queries": _gemini_web_search_queries(response)}
    return {}


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


def _gemini_response(
    api_key: str,
    model: str,
    prompt: str,
    search_enabled: bool,
) -> dict[str, Any]:
    model_path = model if model.startswith("models/") else f"models/{model}"
    payload: dict[str, Any] = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": prompt,
                    }
                ],
            }
        ],
    }
    if search_enabled:
        payload["tools"] = [{"google_search": {}}]
    body = json.dumps(payload).encode("utf-8")
    api_request = request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/{quote(model_path, safe='/-_.')}:generateContent",
        data=body,
        headers={
            "x-goog-api-key": api_key,
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with request.urlopen(api_request, timeout=120) as response:
        return json.loads(response.read().decode("utf-8"))


def _current_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


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


def _gemini_text(response: dict[str, Any]) -> str:
    candidates = response.get("candidates", [])
    if not candidates:
        return ""
    parts = candidates[0].get("content", {}).get("parts", [])
    texts = [part.get("text") for part in parts if isinstance(part.get("text"), str)]
    return "\n".join(texts)


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


def _gemini_grounding_metadata(response: dict[str, Any]) -> dict[str, Any]:
    candidates = response.get("candidates", [])
    if not candidates:
        return {}
    metadata = candidates[0].get("groundingMetadata", {})
    return metadata if isinstance(metadata, dict) else {}


def _gemini_citations(response: dict[str, Any]) -> tuple[Citation, ...]:
    citations = []
    seen_urls = set()
    for chunk in _gemini_grounding_metadata(response).get("groundingChunks", []):
        web = chunk.get("web", {})
        url = web.get("uri")
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        citations.append(Citation(url=url, title=web.get("title")))
    return tuple(citations)


def _gemini_retrieved_sources(response: dict[str, Any]) -> tuple[RetrievedSource, ...]:
    sources = []
    for index, chunk in enumerate(_gemini_grounding_metadata(response).get("groundingChunks", []), start=1):
        web = chunk.get("web", {})
        url = web.get("uri")
        if not url:
            continue
        sources.append(
            RetrievedSource(
                url=url,
                title=web.get("title"),
                rank=index,
                attributes={
                    key: value
                    for key, value in web.items()
                    if key not in {"uri", "title"}
                },
            )
        )
    return tuple(sources)


def _gemini_web_search_queries(response: dict[str, Any]) -> tuple[str, ...]:
    return tuple(
        query
        for query in _gemini_grounding_metadata(response).get("webSearchQueries", [])
        if isinstance(query, str)
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
