from __future__ import annotations

import re
from dataclasses import replace

from .models import AnswerObservation, EntityMention, ObservationSet, Product

RECOMMENDATION_PATTERNS = (
    re.compile(r"\b(recommend|recommended|consider|shortlist|strong fit|best fit|good fit)\b", re.IGNORECASE),
    re.compile(r"\b(should be|is a strong|are usually easier choices)\b", re.IGNORECASE),
)


def extract_product_mentions(observation_set: ObservationSet) -> ObservationSet:
    products = observation_set.products
    observations = tuple(
        replace(
            observation,
            mentions=_merge_mentions(observation, products),
        )
        for observation in observation_set.observations
    )
    return replace(observation_set, observations=observations)


def _merge_mentions(
    observation: AnswerObservation,
    products: tuple[Product, ...],
) -> tuple[EntityMention, ...]:
    existing_by_product = {
        mention.product_id or _slug(mention.display_name or mention.entity): mention
        for mention in observation.mentions
    }
    extracted = []
    for product in products:
        match = _find_product(observation.raw_answer, product)
        if match is None:
            continue
        existing = existing_by_product.get(product.id)
        extracted.append(
            EntityMention(
                entity=product.name,
                product_id=product.id,
                display_name=product.name,
                role=_role(observation.raw_answer, match.start(), existing),
                rank=existing.rank if existing is not None else None,
                stance=existing.stance if existing is not None else "neutral",
                claims=existing.claims if existing is not None else (),
                attributes={
                    **(existing.attributes if existing is not None else {}),
                    "extracted_by": "deterministic_product_alias",
                },
            )
        )

    extracted_ids = {mention.product_id for mention in extracted if mention.product_id}
    preserved = tuple(
        mention
        for mention in observation.mentions
        if mention.product_id not in extracted_ids
    )
    return tuple(extracted) + preserved


def _find_product(answer: str, product: Product) -> re.Match[str] | None:
    for name in (product.name, *product.aliases):
        match = re.search(rf"\b{re.escape(name)}\b", answer, re.IGNORECASE)
        if match is not None:
            return match
    return None


def _role(
    answer: str,
    position: int,
    existing: EntityMention | None,
) -> str:
    if existing is not None and existing.role != "mentioned":
        return existing.role
    sentence = _sentence_at(answer, position)
    if any(pattern.search(sentence) for pattern in RECOMMENDATION_PATTERNS):
        return "recommended"
    return "mentioned"


def _sentence_at(answer: str, position: int) -> str:
    start = max(answer.rfind(".", 0, position), answer.rfind("!", 0, position), answer.rfind("?", 0, position))
    end_candidates = [
        index
        for index in (
            answer.find(".", position),
            answer.find("!", position),
            answer.find("?", position),
        )
        if index != -1
    ]
    end = min(end_candidates) if end_candidates else len(answer)
    return answer[start + 1:end]


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "unknown"
