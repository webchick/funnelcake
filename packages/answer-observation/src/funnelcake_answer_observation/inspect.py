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

    lines = []
    for citation in observation.citations:
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

    lines = []
    for claim in observation.claims:
        parts = [f"- {claim.text}", f"support={claim.support}"]
        if claim.entity:
            parts.append(f"entity={claim.entity}")
        lines.append(" ".join(parts))
        lines.extend(f"  source={source_url}" for source_url in claim.source_urls)
    return lines
