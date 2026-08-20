from __future__ import annotations

from collections import Counter

from .models import EntityVisibility, ObservationSet, ObservationSummary

RECOMMENDATION_ROLES = {"recommended", "selected", "preferred"}


def summarize_observations(observation_set: ObservationSet) -> ObservationSummary:
    response_count = len(observation_set.observations)
    entities = sorted(
        {
            mention.entity
            for observation in observation_set.observations
            for mention in observation.mentions
        }
        | {observation_set.subject_entity}
    )
    entity_visibility = tuple(
        _entity_visibility(observation_set, entity, response_count)
        for entity in entities
    )
    subject_visibility = next(
        visibility
        for visibility in entity_visibility
        if visibility.entity == observation_set.subject_entity
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
                    visibility.entity,
                ),
            )
        ),
        top_cited_urls=tuple(cited_urls.most_common(5)),
        top_retrieved_urls=tuple(retrieved_urls.most_common(5)),
        top_claims=tuple(claims.most_common(5)),
    )


def format_observation_summary(summary: ObservationSummary) -> str:
    subject = summary.subject_visibility
    lines = [
        f"Observation set {summary.observation_set_id}",
        f"subject={summary.subject_entity}",
        f"responses={summary.response_count}",
        "",
        "Level 1: Observation",
        (
            f"{subject.entity} appeared in "
            f"{subject.mention_count}/{subject.response_count} responses "
            f"({subject.mention_rate:.0%})."
        ),
        (
            f"{subject.entity} was recommended in "
            f"{subject.recommended_count}/{subject.response_count} responses "
            f"({subject.recommended_rate:.0%})."
        ),
        "",
        "Entity Visibility",
    ]
    for visibility in summary.entity_visibility:
        rank = (
            f" avg_rank={visibility.average_rank:.1f}"
            if visibility.average_rank is not None
            else ""
        )
        lines.append(
            f"- {visibility.entity}: appeared={visibility.mention_count} "
            f"recommended={visibility.recommended_count} "
            f"citations={visibility.citation_count} "
            f"retrieved={visibility.retrieved_count}{rank}"
        )

    lines.extend(["", "Level 2: Evidence", "Top Cited URLs"])
    lines.extend(_format_counted_items(summary.top_cited_urls))
    lines.extend(["", "Top Retrieved URLs"])
    lines.extend(_format_counted_items(summary.top_retrieved_urls))
    lines.extend(["", "Top Claims"])
    lines.extend(_format_counted_items(summary.top_claims))

    return "\n".join(lines)


def _entity_visibility(
    observation_set: ObservationSet,
    entity: str,
    response_count: int,
) -> EntityVisibility:
    mentioned_response_ids = set()
    recommended_response_ids = set()
    ranks = []

    for observation in observation_set.observations:
        for mention in observation.mentions:
            if mention.entity != entity:
                continue
            mentioned_response_ids.add(observation.id)
            if mention.role in RECOMMENDATION_ROLES:
                recommended_response_ids.add(observation.id)
            if mention.rank is not None:
                ranks.append(mention.rank)

    citation_count = sum(
        1
        for observation in observation_set.observations
        for citation in observation.citations
        if citation.entity == entity
    )
    retrieved_count = sum(
        1
        for observation in observation_set.observations
        for source in observation.retrieved_sources
        if source.entity == entity
    )

    return EntityVisibility(
        entity=entity,
        response_count=response_count,
        mention_count=len(mentioned_response_ids),
        mention_rate=len(mentioned_response_ids) / response_count,
        recommended_count=len(recommended_response_ids),
        recommended_rate=len(recommended_response_ids) / response_count,
        citation_count=citation_count,
        retrieved_count=retrieved_count,
        average_rank=sum(ranks) / len(ranks) if ranks else None,
    )


def _format_counted_items(items: tuple[tuple[str, int], ...]) -> list[str]:
    if not items:
        return ["- none"]
    return [f"- {item}: {count}" for item, count in items]
