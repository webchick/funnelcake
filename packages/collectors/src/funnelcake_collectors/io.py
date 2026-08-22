from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from funnelcake_shared import DessertStage, ProductFunnelStage

from .models import (
    EvidenceArtifact,
    EvidenceArtifactKind,
    Observation,
    ObservationConfidence,
    ObservationProvenance,
)


def observation_to_dict(observation: Observation) -> dict[str, Any]:
    payload = asdict(observation)
    if observation.journey_stage is not None:
        payload["journey_stage"] = observation.journey_stage.value
    if observation.dessert_stage is not None:
        payload["dessert_stage"] = observation.dessert_stage.value
    payload["confidence"] = observation.confidence.value
    for evidence in payload["evidence"]:
        evidence["kind"] = evidence["kind"].value
    return payload


def observations_to_dict(observations: tuple[Observation, ...]) -> dict[str, Any]:
    return {"observations": [observation_to_dict(observation) for observation in observations]}


def write_observations(observations: tuple[Observation, ...], path: str | Path) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(observations_to_dict(observations), indent=2) + "\n", encoding="utf-8")
    return output_path


def load_observations(path: str | Path) -> tuple[Observation, ...]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    records = raw["observations"] if isinstance(raw, dict) else raw
    return tuple(_observation(record) for record in records)


def format_observations(observations: tuple[Observation, ...]) -> str:
    lines = [f"normalized_observations={len(observations)}"]
    for observation in observations:
        stage = observation.journey_stage.value if observation.journey_stage else "none"
        dessert = observation.dessert_stage.value if observation.dessert_stage else "none"
        success = "unknown" if observation.success is None else str(observation.success).lower()
        lines.append(
            f"- {observation.id}: stage={stage} dessert={dessert} "
            f"signal={observation.signal} success={success} "
            f"collector={observation.provenance.collector}"
        )
    return "\n".join(lines)


def _observation(record: dict[str, Any]) -> Observation:
    return Observation(
        id=record["id"],
        experiment_id=record["experiment_id"],
        task_id=record.get("task_id"),
        actor=record.get("actor"),
        journey_stage=ProductFunnelStage(record["journey_stage"]) if record.get("journey_stage") else None,
        dessert_stage=DessertStage(record["dessert_stage"]) if record.get("dessert_stage") else None,
        signal=record["signal"],
        value=record.get("value"),
        success=record.get("success"),
        timestamp=record.get("timestamp"),
        evidence=tuple(_evidence(item) for item in record.get("evidence", [])),
        provenance=ObservationProvenance(**record["provenance"]),
        confidence=ObservationConfidence(record.get("confidence", ObservationConfidence.MEDIUM.value)),
        attributes=record.get("attributes", {}),
    )


def _evidence(record: dict[str, Any]) -> EvidenceArtifact:
    return EvidenceArtifact(
        id=record["id"],
        kind=EvidenceArtifactKind(record["kind"]),
        uri=record.get("uri"),
        summary=record.get("summary"),
        content=record.get("content"),
    )
