from __future__ import annotations

from .models import AnswerObservation, ObservationSet


def format_observation_detail(
    observation_set: ObservationSet,
    observation_id: str,
) -> str:
    observation = next(
        (item for item in observation_set.observations if item.id == observation_id),
        None,
    )
    if observation is None:
        available = ", ".join(item.id for item in observation_set.observations) or "none"
        raise ValueError(f"observation {observation_id} not found; available: {available}")

    lines = [
        f"Observation {observation.id}",
        f"set={observation_set.id}",
        f"prompt_id={observation.prompt_id}",
        f"provider={observation.provider or ''}",
        f"engine={observation.engine or ''}",
        f"surface={observation.surface or ''}",
        f"model={_format_model(observation)}",
        f"search_enabled={_format_optional_bool(observation.search_enabled)}",
        f"region={observation.region or ''}",
        f"language={observation.language or ''}",
        f"timestamp={observation.timestamp or ''}",
        f"repetition={observation.repetition if observation.repetition is not None else ''}",
        f"success={observation.success}",
    ]
    if not observation.success:
        lines.append(f"failure_type={observation.failure_type or ''}")
        lines.append(f"error_message={observation.error_message or ''}")
        lines.append(f"retry_count={observation.retry_count}")

    lines.extend(["", "Prompt", observation.prompt, "", "Raw Answer", observation.raw_answer])
    lines.extend(["", "Mentions"])
    lines.extend(_format_mentions(observation))
    lines.extend(["", "Citations"])
    lines.extend(_format_citations(observation))
    lines.extend(["", "Retrieved Sources"])
    lines.extend(_format_retrieved_sources(observation))
    lines.extend(["", "Claims"])
    lines.extend(_format_claims(observation))
    lines.extend(["", "Raw Provider Payloads"])
    lines.append(f"raw_request_keys={','.join(sorted(observation.raw_request)) or 'none'}")
    lines.append(f"raw_response_keys={','.join(sorted(observation.raw_response)) or 'none'}")

    return "\n".join(lines)


def format_product_detail(
    observation_set: ObservationSet,
    product: str,
) -> str:
    product_id, product_name = _resolve_product(observation_set, product)
    matching_observations = tuple(
        observation
        for observation in observation_set.observations
        if _observation_mentions_product(observation, product_id, product_name)
    )
    recommended = tuple(
        observation
        for observation in matching_observations
        if _observation_recommends_product(observation, product_id, product_name)
    )

    lines = [
        f"Product {product_name}",
        f"product_id={product_id or ''}",
        f"set={observation_set.id}",
        f"observations={len(matching_observations)}/{len(observation_set.observations)}",
        f"recommended={len(recommended)}/{len(observation_set.observations)}",
        "",
        "Matching Observations",
    ]
    if not matching_observations:
        lines.append("- none")
        return "\n".join(lines)

    for observation in matching_observations:
        matching_mentions = tuple(
            mention
            for mention in observation.mentions
            if _matches_product(mention.entity, mention.product_id, product_id, product_name)
        )
        lines.extend(
            [
                f"- {observation.id} prompt={observation.prompt_id} "
                f"provider={observation.provider or observation.engine or ''} "
                f"recommended={_observation_recommends_product(observation, product_id, product_name)}",
                f"  prompt_text={observation.prompt}",
            ]
        )
        for mention in matching_mentions:
            detail = [f"  mention_role={mention.role}"]
            if mention.rank is not None:
                detail.append(f"rank={mention.rank}")
            if mention.stance:
                detail.append(f"stance={mention.stance}")
            lines.append(" ".join(detail))

        citations = tuple(
            citation
            for citation in observation.citations
            if _matches_product(citation.entity, citation.product_id, product_id, product_name)
        )
        if citations:
            lines.append("  citations:")
            lines.extend(f"    {line}" for line in _format_citations_for_items(citations))

        product_claims = tuple(
            claim
            for claim in observation.claims
            if claim.entity is None or claim.entity == product_name or claim.entity == product_id
        )
        if product_claims:
            lines.append("  claims:")
            lines.extend(f"    {line}" for line in _format_claims_for_items(product_claims))

    return "\n".join(lines)


def format_prompt_detail(
    observation_set: ObservationSet,
    prompt_id: str,
) -> str:
    prompt = next((item for item in observation_set.prompts if item.id == prompt_id), None)
    matching_observations = tuple(
        observation
        for observation in observation_set.observations
        if observation.prompt_id == prompt_id
    )
    if prompt is None and not matching_observations:
        available = sorted(
            {item.id for item in observation_set.prompts}
            | {item.prompt_id for item in observation_set.observations}
        )
        raise ValueError(
            f"prompt {prompt_id} not found; available: {', '.join(available) or 'none'}"
        )

    prompt_text = prompt.prompt if prompt is not None else matching_observations[0].prompt
    lines = [
        f"Prompt {prompt_id}",
        f"set={observation_set.id}",
        f"observations={len(matching_observations)}",
    ]
    if prompt is not None:
        lines.extend(
            [
                f"intent={prompt.intent or ''}",
                f"persona={prompt.persona or ''}",
                f"task={prompt.task or ''}",
                f"funnel_stage={prompt.funnel_stage or ''}",
                f"region={prompt.region or ''}",
                f"language={prompt.language or ''}",
                f"tags={','.join(prompt.tags)}",
            ]
        )

    lines.extend(["", "Prompt Text", prompt_text, "", "Answers"])
    if not matching_observations:
        lines.append("- none")
        return "\n".join(lines)

    for observation in sorted(
        matching_observations,
        key=lambda item: (
            item.provider or item.engine or "",
            item.repetition if item.repetition is not None else -1,
            item.id,
        ),
    ):
        lines.extend(
            [
                "",
                f"{observation.id}",
                f"provider={observation.provider or observation.engine or ''}",
                f"model={_format_model(observation)}",
                f"repetition={observation.repetition if observation.repetition is not None else ''}",
                f"timestamp={observation.timestamp or ''}",
                f"success={observation.success}",
                "",
                observation.raw_answer,
                "",
                "Mentions",
            ]
        )
        lines.extend(_indent(_format_mentions(observation)))
        lines.extend(["", "Citations"])
        lines.extend(_indent(_format_citations(observation)))
        if observation.claims:
            lines.extend(["", "Claims"])
            lines.extend(_indent(_format_claims(observation)))

    return "\n".join(lines)


def _format_model(observation: AnswerObservation) -> str:
    if observation.model and observation.model_version:
        return f"{observation.model}@{observation.model_version}"
    return observation.model or ""


def _format_optional_bool(value: bool | None) -> str:
    if value is None:
        return ""
    return str(value)


def _format_mentions(observation: AnswerObservation) -> list[str]:
    if not observation.mentions:
        return ["- none"]

    lines = []
    for mention in observation.mentions:
        label = mention.display_name or mention.entity
        parts = [
            f"- {label}",
            f"role={mention.role}",
        ]
        if mention.product_id:
            parts.append(f"product_id={mention.product_id}")
        if mention.rank is not None:
            parts.append(f"rank={mention.rank}")
        if mention.stance:
            parts.append(f"stance={mention.stance}")
        lines.append(" ".join(parts))
        lines.extend(f"  claim={claim}" for claim in mention.claims)
    return lines


def _format_citations(observation: AnswerObservation) -> list[str]:
    if not observation.citations:
        return ["- none"]
    return _format_citations_for_items(observation.citations)


def _format_citations_for_items(citations) -> list[str]:
    lines = []
    for citation in citations:
        parts = [f"- {citation.url}"]
        if citation.domain:
            parts.append(f"domain={citation.domain}")
        if citation.title:
            parts.append(f"title={citation.title}")
        if citation.product_id:
            parts.append(f"product_id={citation.product_id}")
        elif citation.entity:
            parts.append(f"entity={citation.entity}")
        lines.append(" ".join(parts))
    return lines


def _format_retrieved_sources(observation: AnswerObservation) -> list[str]:
    if not observation.retrieved_sources:
        return ["- none"]

    lines = []
    for source in observation.retrieved_sources:
        parts = [f"- {source.url}"]
        if source.rank is not None:
            parts.append(f"rank={source.rank}")
        if source.domain:
            parts.append(f"domain={source.domain}")
        if source.title:
            parts.append(f"title={source.title}")
        if source.product_id:
            parts.append(f"product_id={source.product_id}")
        elif source.entity:
            parts.append(f"entity={source.entity}")
        lines.append(" ".join(parts))
    return lines


def _format_claims(observation: AnswerObservation) -> list[str]:
    if not observation.claims:
        return ["- none"]
    return _format_claims_for_items(observation.claims)


def _format_claims_for_items(claims) -> list[str]:
    lines = []
    for claim in claims:
        parts = [f"- {claim.text}", f"support={claim.support}"]
        if claim.entity:
            parts.append(f"entity={claim.entity}")
        lines.append(" ".join(parts))
        lines.extend(f"  source={source_url}" for source_url in claim.source_urls)
    return lines


def _resolve_product(observation_set: ObservationSet, product: str) -> tuple[str | None, str]:
    query = product.lower()
    for candidate in observation_set.products:
        names = {candidate.id.lower(), candidate.name.lower()}
        names.update(alias.lower() for alias in candidate.aliases)
        if query in names:
            return candidate.id, candidate.name
    return None, product


def _observation_mentions_product(
    observation: AnswerObservation,
    product_id: str | None,
    product_name: str,
) -> bool:
    return any(
        _matches_product(mention.entity, mention.product_id, product_id, product_name)
        for mention in observation.mentions
    )


def _observation_recommends_product(
    observation: AnswerObservation,
    product_id: str | None,
    product_name: str,
) -> bool:
    return any(
        _matches_product(mention.entity, mention.product_id, product_id, product_name)
        and mention.role in {"recommended", "selected", "preferred"}
        for mention in observation.mentions
    )


def _matches_product(
    entity: str | None,
    product_id: str | None,
    expected_product_id: str | None,
    expected_name: str,
) -> bool:
    if expected_product_id is not None and product_id == expected_product_id:
        return True
    return entity == expected_name


def _indent(lines: list[str]) -> list[str]:
    return [f"  {line}" for line in lines]
