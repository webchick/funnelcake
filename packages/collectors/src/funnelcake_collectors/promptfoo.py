from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

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


class PromptfooCollector:
    id = "external.promptfoo"
    version = "0.1"

    def supports(self, capability: CollectorCapability) -> bool:
        return capability == CollectorCapability.AGENT_EVALUATION

    def collect(self, experiment: Experiment) -> tuple[Observation, ...]:
        if not self.supports(experiment.capability):
            raise ValueError(f"{self.id} does not support {experiment.capability.value}")

        input_path = require_input_path(experiment)
        raw = load_promptfoo_results(input_path)
        return self.collect_payload(experiment, raw, str(input_path))

    def collect_from_config(
        self,
        experiment: Experiment,
        config_path: str | Path,
        *,
        command: str = "promptfoo",
        raw_output_path: str | Path,
        extra_args: tuple[str, ...] = (),
    ) -> tuple[Observation, ...]:
        output_path = Path(raw_output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        args = [command, "eval", "--config", str(config_path), "--output", str(output_path), *extra_args]
        try:
            completed = subprocess.run(
                args,
                check=False,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError as exc:
            raise RuntimeError(
                f"{command!r} was not found. Install Promptfoo or pass --command."
            ) from exc

        if completed.returncode != 0:
            raise RuntimeError(
                f"Promptfoo eval failed; exit_code={completed.returncode} stderr={completed.stderr.strip()}"
            )
        if not output_path.exists():
            raise RuntimeError(f"Promptfoo did not write expected output file: {output_path}")

        raw = load_promptfoo_results(output_path)
        if isinstance(raw, dict):
            raw.setdefault("config_path", str(config_path))
            raw.setdefault("exit_code", completed.returncode)
        return self.collect_payload(experiment, raw, str(output_path))

    def collect_payload(
        self,
        experiment: Experiment,
        raw: dict[str, Any],
        source: str,
    ) -> tuple[Observation, ...]:
        outputs = _outputs(raw)
        raw_artifact = EvidenceArtifact(
            id=f"{experiment.id}:raw",
            kind=EvidenceArtifactKind.JSON,
            uri=source,
            summary="Promptfoo eval results",
            content=raw,
        )
        provenance = ObservationProvenance(
            collector=self.id,
            collector_version=self.version,
            source=source,
            raw_artifact_id=raw_artifact.id,
        )
        stage = _stage(experiment)
        observations = []
        for index, row in enumerate(outputs, start=1):
            success = _success(row)
            score = _score(row)
            grading_result = row.get("gradingResult") if isinstance(row.get("gradingResult"), dict) else {}
            observations.append(
                Observation(
                    id=f"{experiment.id}:promptfoo-{index:04d}",
                    experiment_id=experiment.id,
                    task_id=experiment.task_id or _task_id(row, index),
                    actor=experiment.actor or _provider(row),
                    journey_stage=stage,
                    dessert_stage=DessertStage.EXECUTE,
                    signal="agent_eval_result",
                    value={
                        "success": success,
                        "score": score,
                        "reason": row.get("reason") or grading_result.get("reason"),
                    },
                    success=success,
                    timestamp=_timestamp(raw, row),
                    evidence=(raw_artifact,),
                    provenance=provenance,
                    confidence=ObservationConfidence.HIGH if success is not None else ObservationConfidence.MEDIUM,
                    attributes={
                        "promptfoo_output_index": index - 1,
                        "test_idx": row.get("testIdx"),
                        "prompt_idx": row.get("promptIdx"),
                    },
                )
            )
        return tuple(observations)


def load_promptfoo_results(path: str | Path) -> dict[str, Any]:
    result_path = Path(path)
    text = result_path.read_text(encoding="utf-8").strip()
    if not text:
        return {"results": {"outputs": []}}
    if result_path.suffix == ".jsonl":
        return {"results": {"outputs": [json.loads(line) for line in text.splitlines() if line.strip()]}}
    loaded = json.loads(text)
    if isinstance(loaded, list):
        return {"results": {"outputs": loaded}}
    if isinstance(loaded, dict):
        return loaded
    raise ValueError(f"unsupported Promptfoo result payload in {result_path}")


def _outputs(raw: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    candidates = raw.get("outputs")
    if candidates is None and isinstance(raw.get("results"), dict):
        candidates = raw["results"].get("outputs")
        if candidates is None:
            candidates = raw["results"].get("results")
    if candidates is None and isinstance(raw.get("results"), list):
        candidates = raw.get("results")
    if not isinstance(candidates, list):
        return ()
    return tuple(item for item in candidates if isinstance(item, dict))


def _success(row: dict[str, Any]) -> bool | None:
    for key in ("success", "pass", "passed"):
        value = row.get(key)
        if isinstance(value, bool):
            return value
    grading = row.get("gradingResult")
    if isinstance(grading, dict):
        value = grading.get("pass")
        if isinstance(value, bool):
            return value
    return None


def _score(row: dict[str, Any]) -> float | int | None:
    value = row.get("score")
    if isinstance(value, int | float):
        return value
    grading = row.get("gradingResult")
    if isinstance(grading, dict):
        grading_score = grading.get("score")
        if isinstance(grading_score, int | float):
            return grading_score
    return None


def _provider(row: dict[str, Any]) -> str | None:
    provider = row.get("provider")
    if isinstance(provider, dict):
        provider_id = provider.get("id") or provider.get("label")
        return str(provider_id) if provider_id is not None else None
    if provider is not None:
        return str(provider)
    return None


def _task_id(row: dict[str, Any], index: int) -> str:
    for key in ("testCaseId", "test_id", "testIdx"):
        value = row.get(key)
        if value is not None:
            return str(value)
    return f"promptfoo-row-{index:04d}"


def _timestamp(raw: dict[str, Any], row: dict[str, Any]) -> str | None:
    value = row.get("timestamp") or raw.get("timestamp")
    return str(value) if value is not None else None


def _stage(experiment: Experiment) -> ProductFunnelStage:
    value = experiment.attributes.get("journey_stage")
    if isinstance(value, str):
        return ProductFunnelStage(value)
    return ProductFunnelStage.INITIAL_VALUE
