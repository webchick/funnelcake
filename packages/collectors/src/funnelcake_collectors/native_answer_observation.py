from __future__ import annotations

from funnelcake_answer_observation import load_observation_set
from funnelcake_answer_observation.metrics import RECOMMENDATION_ROLES
from funnelcake_shared import DessertStage, ProductFunnelStage

from .models import (
    CollectorCapability,
    EvidenceArtifact,
    EvidenceArtifactKind,
    Experiment,
    Observation,
    ObservationConfidence,
    ObservationProvenance,
    require_input_path,
)


class NativeAnswerObservationCollector:
    id = "native.answer_observation"
    version = "0.1"

    def supports(self, capability: CollectorCapability) -> bool:
        return capability == CollectorCapability.ANSWER_OBSERVATION

    def collect(self, experiment: Experiment) -> tuple[Observation, ...]:
        if not self.supports(experiment.capability):
            raise ValueError(f"{self.id} does not support {experiment.capability.value}")

        input_path = require_input_path(experiment)
        observation_set = load_observation_set(input_path)
        raw_artifact = EvidenceArtifact(
            id=f"{experiment.id}:raw",
            kind=EvidenceArtifactKind.JSON,
            uri=str(input_path),
            summary=f"Answer observation set {observation_set.id}",
        )
        provenance = ObservationProvenance(
            collector=self.id,
            collector_version=self.version,
            source=str(input_path),
            raw_artifact_id=raw_artifact.id,
        )

        normalized = []
        for source_observation in observation_set.observations:
            subject_mentions = tuple(
                mention
                for mention in source_observation.mentions
                if mention.entity == observation_set.subject_entity
                or mention.product_id == observation_set.subject_product_id
            )
            mentioned = bool(subject_mentions)
            recommended = any(mention.role in RECOMMENDATION_ROLES for mention in subject_mentions)
            first_rank = min(
                (mention.rank for mention in subject_mentions if mention.rank is not None),
                default=None,
            )
            raw_evidence = EvidenceArtifact(
                id=f"{experiment.id}:{source_observation.id}",
                kind=EvidenceArtifactKind.JSON,
                uri=f"{input_path}#observations/{source_observation.id}",
                summary=f"Answer observation {source_observation.id}",
                content={
                    "observation_id": source_observation.id,
                    "prompt_id": source_observation.prompt_id,
                    "provider": source_observation.provider,
                    "engine": source_observation.engine,
                    "model": source_observation.model,
                    "mentions": [
                        {
                            "entity": mention.entity,
                            "product_id": mention.product_id,
                            "role": mention.role,
                            "rank": mention.rank,
                        }
                        for mention in subject_mentions
                    ],
                },
            )
            normalized.append(
                Observation(
                    id=f"{experiment.id}:{source_observation.id}:visibility",
                    experiment_id=experiment.id,
                    task_id=experiment.task_id or source_observation.prompt_id,
                    actor=experiment.actor or source_observation.provider or source_observation.engine,
                    journey_stage=ProductFunnelStage.INVESTIGATE,
                    dessert_stage=DessertStage.DISCOVER,
                    signal="agent_visibility",
                    value={
                        "mentioned": mentioned,
                        "recommended": recommended,
                        "first_rank": first_rank,
                    },
                    success=mentioned,
                    timestamp=source_observation.timestamp,
                    evidence=(raw_artifact, raw_evidence),
                    provenance=provenance,
                    confidence=ObservationConfidence.HIGH if source_observation.success else ObservationConfidence.LOW,
                    attributes={
                        "observation_set_id": observation_set.id,
                        "source_observation_id": source_observation.id,
                    },
                )
            )
            if recommended:
                normalized.append(
                    Observation(
                        id=f"{experiment.id}:{source_observation.id}:selection",
                        experiment_id=experiment.id,
                        task_id=experiment.task_id or source_observation.prompt_id,
                        actor=experiment.actor or source_observation.provider or source_observation.engine,
                        journey_stage=ProductFunnelStage.LAND,
                        dessert_stage=DessertStage.SELECT,
                        signal="agent_selection",
                        value={"selected": True, "first_choice": first_rank == 1},
                        success=True,
                        timestamp=source_observation.timestamp,
                        evidence=(raw_artifact, raw_evidence),
                        provenance=provenance,
                        confidence=ObservationConfidence.HIGH,
                        attributes={
                            "observation_set_id": observation_set.id,
                            "source_observation_id": source_observation.id,
                        },
                    )
                )

        return tuple(normalized)
