from __future__ import annotations

from .metrics import summarize_observations
from .models import (
    EntityVisibility,
    EntityVisibilityChange,
    ObservationComparison,
    ObservationSet,
)


def compare_observation_sets(
    baseline: ObservationSet,
    followup: ObservationSet,
) -> ObservationComparison:
    baseline_summary = summarize_observations(baseline)
    followup_summary = summarize_observations(followup)
    baseline_index = {
        visibility.entity: visibility
        for visibility in baseline_summary.entity_visibility
    }
    followup_index = {
        visibility.entity: visibility
        for visibility in followup_summary.entity_visibility
    }
    entities = sorted(set(baseline_index) | set(followup_index))

    return ObservationComparison(
        baseline_id=baseline.id,
        followup_id=followup.id,
        subject_entity=followup.subject_entity,
        baseline_response_count=baseline_summary.response_count,
        followup_response_count=followup_summary.response_count,
        entity_changes=tuple(
            _entity_change(entity, baseline_index.get(entity), followup_index.get(entity))
            for entity in entities
        ),
    )


def format_observation_comparison(comparison: ObservationComparison) -> str:
    lines = [
        "Observation comparison",
        f"baseline={comparison.baseline_id} responses={comparison.baseline_response_count}",
        f"followup={comparison.followup_id} responses={comparison.followup_response_count}",
        "",
        "Changes",
        "Entity | Seen | Recommended | First choice | Recommendation share",
    ]
    for change in sorted(
        comparison.entity_changes,
        key=lambda item: (
            -abs(item.recommended_rate_change),
            item.display_name or item.entity,
        ),
    ):
        label = change.display_name or change.entity
        lines.append(
            f"{label} | "
            f"{_format_rate_change(change.before_mention_rate, change.after_mention_rate)} | "
            f"{_format_rate_change(change.before_recommended_rate, change.after_recommended_rate)} | "
            f"{_format_rate_change(change.before_first_choice_rate, change.after_first_choice_rate)} | "
            f"{_format_rate_change(change.before_recommendation_share, change.after_recommendation_share)}"
        )

    lines.extend(
        [
            "",
            "Interpretation",
            "These are observational deltas, not causal claims. Use controlled follow-up runs or manually authored hypotheses before attributing cause.",
        ]
    )
    return "\n".join(lines)


def _entity_change(
    entity: str,
    before: EntityVisibility | None,
    after: EntityVisibility | None,
) -> EntityVisibilityChange:
    before = before or _empty_visibility(entity)
    after = after or _empty_visibility(entity)
    return EntityVisibilityChange(
        entity=entity,
        display_name=after.display_name or before.display_name,
        before_mention_rate=before.mention_rate,
        after_mention_rate=after.mention_rate,
        mention_rate_change=after.mention_rate - before.mention_rate,
        before_recommended_rate=before.recommended_rate,
        after_recommended_rate=after.recommended_rate,
        recommended_rate_change=after.recommended_rate - before.recommended_rate,
        before_first_choice_rate=before.first_choice_rate,
        after_first_choice_rate=after.first_choice_rate,
        first_choice_rate_change=after.first_choice_rate - before.first_choice_rate,
        before_recommendation_share=before.recommendation_share,
        after_recommendation_share=after.recommendation_share,
        recommendation_share_change=after.recommendation_share - before.recommendation_share,
    )


def _empty_visibility(entity: str) -> EntityVisibility:
    return EntityVisibility(
        entity=entity,
        display_name=None,
        response_count=0,
        mention_count=0,
        mention_rate=0.0,
        recommended_count=0,
        recommended_rate=0.0,
        first_choice_count=0,
        first_choice_rate=0.0,
        citation_count=0,
        retrieved_count=0,
        recommendation_share=0.0,
    )


def _format_rate_change(before: float, after: float) -> str:
    return f"{before:.0%} -> {after:.0%} ({_format_percentage_points(after - before)})"


def _format_percentage_points(change: float) -> str:
    percentage_points = change * 100
    sign = "+" if percentage_points > 0 else ""
    return f"{sign}{percentage_points:.0f}pp"
