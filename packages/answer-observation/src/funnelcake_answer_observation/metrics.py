from __future__ import annotations

from collections import Counter
from urllib.parse import urlparse

from .models import EntityVisibility, ObservationSet, ObservationSummary

RECOMMENDATION_ROLES = {"recommended", "selected", "preferred"}


def summarize_observations(observation_set: ObservationSet) -> ObservationSummary:
    response_count = len(observation_set.observations)
    entities = sorted(
        {
            _mention_key(mention.entity, mention.product_id)
            for observation in observation_set.observations
            for mention in observation.mentions
        }
        | {_mention_key(observation_set.subject_entity, observation_set.subject_product_id)}
    )
    entity_visibility = tuple(
        _entity_visibility(observation_set, entity, response_count)
        for entity in entities
    )
    subject_visibility = next(
        visibility
        for visibility in entity_visibility
        if visibility.entity == observation_set.subject_entity
        or visibility.entity == observation_set.subject_product_id
    )

    cited_urls = Counter(
        citation.url
        for observation in observation_set.observations
        for citation in observation.citations
    )
    retrieved_urls = Counter(
        source.url
        for observation in observation_set.observations
        for source in observation.retrieved_sources
    )
    cited_domains = Counter(
        citation.domain or _domain(citation.url)
        for observation in observation_set.observations
        for citation in observation.citations
    )
    retrieved_domains = Counter(
        source.domain or _domain(source.url)
        for observation in observation_set.observations
        for source in observation.retrieved_sources
    )
    claims = Counter(
        claim.text
        for observation in observation_set.observations
        for claim in observation.claims
        if claim.entity in {None, observation_set.subject_entity}
    )

    return ObservationSummary(
        observation_set_id=observation_set.id,
        response_count=response_count,
        subject_entity=observation_set.subject_entity,
        subject_visibility=subject_visibility,
        entity_visibility=tuple(
            sorted(
                entity_visibility,
                key=lambda visibility: (
                    -visibility.mention_count,
                    -visibility.recommended_count,
                    -visibility.first_choice_count,
                    visibility.entity,
                ),
            )
        ),
        top_cited_urls=tuple(cited_urls.most_common(5)),
        top_cited_domains=tuple(cited_domains.most_common(5)),
        top_retrieved_urls=tuple(retrieved_urls.most_common(5)),
        top_retrieved_domains=tuple(retrieved_domains.most_common(5)),
        top_claims=tuple(claims.most_common(5)),
        recommendation_consistency=_recommendation_consistency(observation_set),
    )


def format_observation_summary(summary: ObservationSummary) -> str:
    subject = summary.subject_visibility
    subject_label = subject.display_name or summary.subject_entity
    lines = [
        f"Observation set {summary.observation_set_id}",
        f"subject={summary.subject_entity}",
        f"responses={summary.response_count}",
        "",
        "Level 1: Observation",
        (
            f"{subject_label} appeared in "
            f"{subject.mention_count}/{subject.response_count} responses "
            f"({subject.mention_rate:.0%})."
        ),
        (
            f"{subject_label} was recommended in "
            f"{subject.recommended_count}/{subject.response_count} responses "
            f"({subject.recommended_rate:.0%})."
        ),
        (
            f"{subject_label} was first choice in "
            f"{subject.first_choice_count}/{subject.response_count} responses "
            f"({subject.first_choice_rate:.0%})."
        ),
        "",
        "Entity Visibility",
    ]
    for visibility in summary.entity_visibility:
        label = visibility.display_name or visibility.entity
        rank = (
            f" avg_rank={visibility.average_rank:.1f}"
            if visibility.average_rank is not None
            else ""
        )
        lines.append(
            f"- {label}: appeared={visibility.mention_count} "
            f"recommended={visibility.recommended_count} "
            f"first_choice={visibility.first_choice_count} "
            f"recommendation_share={visibility.recommendation_share:.0%} "
            f"citations={visibility.citation_count} "
            f"retrieved={visibility.retrieved_count}{rank}"
        )

    lines.extend(["", "Level 2: Evidence", "Top Cited URLs"])
    lines.extend(_format_counted_items(summary.top_cited_urls))
    lines.extend(["", "Top Cited Domains"])
    lines.extend(_format_counted_items(summary.top_cited_domains))
    lines.extend(["", "Top Retrieved URLs"])
    lines.extend(_format_counted_items(summary.top_retrieved_urls))
    lines.extend(["", "Top Retrieved Domains"])
    lines.extend(_format_counted_items(summary.top_retrieved_domains))
    lines.extend(["", "Top Claims"])
    lines.extend(_format_counted_items(summary.top_claims))
    lines.extend(["", "Consistency"])
    lines.extend(_format_consistency(summary.recommendation_consistency))

    return "\n".join(lines)


def _entity_visibility(
    observation_set: ObservationSet,
    entity: str,
    response_count: int,
) -> EntityVisibility:
    mentioned_response_ids = set()
    recommended_response_ids = set()
    first_choice_response_ids = set()
    ranks = []
    total_recommendations = 0
    entity_recommendations = 0

    for observation in observation_set.observations:
        for mention in observation.mentions:
            if mention.role in RECOMMENDATION_ROLES:
                total_recommendations += 1
            if _mention_key(mention.entity, mention.product_id) != entity:
                continue
            mentioned_response_ids.add(observation.id)
            if mention.role in RECOMMENDATION_ROLES:
                entity_recommendations += 1
                recommended_response_ids.add(observation.id)
                if mention.rank == 1:
                    first_choice_response_ids.add(observation.id)
            if mention.rank is not None:
                ranks.append(mention.rank)

    retrieved_count = sum(
        1
        for observation in observation_set.observations
        for source in observation.retrieved_sources
        if _mention_key(source.entity or "", source.product_id) == entity
    )
    citation_count = sum(
        1
        for observation in observation_set.observations
        for citation in observation.citations
        if _mention_key(citation.entity or "", citation.product_id) == entity
    )

    return EntityVisibility(
        entity=entity,
        response_count=response_count,
        mention_count=len(mentioned_response_ids),
        mention_rate=len(mentioned_response_ids) / response_count,
        recommended_count=len(recommended_response_ids),
        recommended_rate=len(recommended_response_ids) / response_count,
        first_choice_count=len(first_choice_response_ids),
        first_choice_rate=len(first_choice_response_ids) / response_count,
        citation_count=citation_count,
        retrieved_count=retrieved_count,
        recommendation_share=(
            entity_recommendations / total_recommendations
            if total_recommendations
            else 0.0
        ),
        average_rank=sum(ranks) / len(ranks) if ranks else None,
        display_name=_display_name(observation_set, entity),
    )


def _recommendation_consistency(
    observation_set: ObservationSet,
) -> tuple[tuple[str, str, int, int, float], ...]:
    subject = observation_set.subject_entity
    subject_product_id = observation_set.subject_product_id
    buckets: dict[tuple[str, str], list[bool]] = {}
    for observation in observation_set.observations:
        provider = observation.provider or observation.engine or "unknown"
        key = (observation.prompt_id, provider)
        recommended = any(
            _mention_matches_subject(mention.entity, mention.product_id, subject, subject_product_id)
            and mention.role in RECOMMENDATION_ROLES
            for mention in observation.mentions
        )
        buckets.setdefault(key, []).append(recommended)

    consistency = []
    for (prompt_id, provider), results in buckets.items():
        recommended_count = sum(1 for result in results if result)
        total = len(results)
        consistency.append((prompt_id, provider, recommended_count, total, recommended_count / total))

    return tuple(sorted(consistency, key=lambda item: (item[0], item[1])))


def _domain(url: str) -> str:
    return urlparse(url).netloc.removeprefix("www.")


def _mention_key(entity: str, product_id: str | None) -> str:
    return product_id or entity


def _mention_matches_subject(
    entity: str,
    product_id: str | None,
    subject: str,
    subject_product_id: str | None,
) -> bool:
    return product_id == subject_product_id if subject_product_id is not None else entity == subject


def _display_name(observation_set: ObservationSet, entity: str) -> str | None:
    for product in observation_set.products:
        if product.id == entity:
            return product.name
    for observation in observation_set.observations:
        for mention in observation.mentions:
            if _mention_key(mention.entity, mention.product_id) == entity:
                return mention.display_name or mention.entity
    return None


def _format_counted_items(items: tuple[tuple[str, int], ...]) -> list[str]:
    if not items:
        return ["- none"]
    return [f"- {item}: {count}" for item, count in items]


def _format_consistency(items: tuple[tuple[str, str, int, int, float], ...]) -> list[str]:
    if not items:
        return ["- none"]
    return [
        f"- prompt={prompt_id} provider={provider}: {recommended}/{total} ({rate:.0%})"
        for prompt_id, provider, recommended, total, rate in items
    ]
