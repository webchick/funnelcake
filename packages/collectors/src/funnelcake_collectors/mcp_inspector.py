from __future__ import annotations

import json
import subprocess
from pathlib import Path

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


class MCPInspectorCollector:
    id = "external.mcp_inspector"
    version = "0.1"

    def supports(self, capability: CollectorCapability) -> bool:
        return capability == CollectorCapability.MCP_INSPECTION

    def collect(self, experiment: Experiment) -> tuple[Observation, ...]:
        if not self.supports(experiment.capability):
            raise ValueError(f"{self.id} does not support {experiment.capability.value}")

        input_path = require_input_path(experiment)
        return self.collect_payload(experiment, json.loads(input_path.read_text(encoding="utf-8")), str(input_path))

    def collect_from_server(
        self,
        experiment: Experiment,
        server: str,
        *,
        method: str = "tools/list",
        command: str = "mcp-inspector",
        tool_name: str | None = None,
        raw_output_path: str | Path | None = None,
        extra_args: tuple[str, ...] = (),
    ) -> tuple[Observation, ...]:
        args = [command, "--cli", server, "--method", method, "--format", "json"]
        if tool_name is not None:
            args.extend(["--tool-name", tool_name])
        args.extend(extra_args)
        try:
            completed = subprocess.run(
                args,
                check=False,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError as exc:
            raise RuntimeError(
                f"{command!r} was not found. Install MCP Inspector or pass --command."
            ) from exc

        raw_text = completed.stdout.strip()
        if raw_output_path is not None:
            output_path = Path(raw_output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(raw_text + "\n", encoding="utf-8")
            source = str(output_path)
        else:
            source = f"{command} {' '.join(args[1:])}"

        if not raw_text:
            raise RuntimeError(
                f"MCP Inspector produced no JSON output; exit_code={completed.returncode} stderr={completed.stderr.strip()}"
            )

        try:
            raw = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"MCP Inspector output was not JSON; exit_code={completed.returncode} stderr={completed.stderr.strip()}"
            ) from exc

        if isinstance(raw, dict):
            raw.setdefault("server", server)
            raw.setdefault("method", method)
            raw.setdefault("exit_code", completed.returncode)
            if completed.stderr.strip():
                raw.setdefault("stderr", completed.stderr.strip())
        return self.collect_payload(experiment, raw, source)

    def collect_payload(
        self,
        experiment: Experiment,
        raw: dict[str, object],
        source: str,
    ) -> tuple[Observation, ...]:
        auth_succeeded = _bool_field(raw, "auth_succeeded", "authenticationSucceeded")
        if auth_succeeded is None and _exit_code(raw) is not None:
            auth_succeeded = _exit_code(raw) == 0
        tools_discovered = _tool_count(raw)
        error = _error_message(raw)
        raw_artifact = EvidenceArtifact(
            id=f"{experiment.id}:raw",
            kind=EvidenceArtifactKind.JSON,
            uri=source,
            summary="MCP Inspector result",
            content=raw,
        )
        provenance = ObservationProvenance(
            collector=self.id,
            collector_version=self.version,
            source=source,
            raw_artifact_id=raw_artifact.id,
        )

        observations = [
            Observation(
                id=f"{experiment.id}:mcp-auth",
                experiment_id=experiment.id,
                task_id=experiment.task_id,
                actor=experiment.actor or _as_string(_field(raw, "client", "agent", "actor")),
                journey_stage=ProductFunnelStage.LAUNCH,
                dessert_stage=DessertStage.SETUP,
                signal="mcp_authentication",
                value={
                    "auth_succeeded": auth_succeeded,
                    "tools_discovered": tools_discovered,
                    "error": error,
                },
                success=auth_succeeded,
                timestamp=_as_string(_field(raw, "timestamp")),
                evidence=(raw_artifact,),
                provenance=provenance,
                confidence=ObservationConfidence.HIGH if auth_succeeded is not None else ObservationConfidence.MEDIUM,
                attributes={"server": _field(raw, "server", "server_url", "serverUrl")},
            )
        ]
        if isinstance(tools_discovered, int | float):
            observations.append(
                Observation(
                    id=f"{experiment.id}:mcp-tools",
                    experiment_id=experiment.id,
                    task_id=experiment.task_id,
                    actor=experiment.actor or _as_string(_field(raw, "client", "agent", "actor")),
                    journey_stage=ProductFunnelStage.INITIAL_VALUE,
                    dessert_stage=DessertStage.EXECUTE,
                    signal="mcp_tool_discovery",
                    value={"tools_discovered": tools_discovered},
                    success=tools_discovered > 0,
                    timestamp=_as_string(_field(raw, "timestamp")),
                    evidence=(raw_artifact,),
                    provenance=provenance,
                    confidence=ObservationConfidence.HIGH,
                    attributes={"server": _field(raw, "server", "server_url", "serverUrl")},
                )
            )
        return tuple(observations)


def _field(raw: dict[str, object], *names: str) -> object:
    for name in names:
        value = raw.get(name)
        if value is not None:
            return value
    return None


def _nested(raw: dict[str, object], *path: str) -> object:
    value: object = raw
    for key in path:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
        if value is None:
            return None
    return value


def _tool_count(raw: dict[str, object]) -> object:
    explicit = _field(raw, "tools_discovered", "toolsDiscovered")
    if explicit is not None:
        return explicit
    tools = _nested(raw, "result", "tools")
    if isinstance(tools, list):
        return len(tools)
    return None


def _error_message(raw: dict[str, object]) -> object:
    error = _field(raw, "error", "message")
    if isinstance(error, dict):
        nested = error.get("message")
        return nested if nested is not None else error
    nested_error = _nested(raw, "error", "message")
    return nested_error if nested_error is not None else error


def _exit_code(raw: dict[str, object]) -> int | None:
    value = _field(raw, "exit_code", "exitCode")
    return value if isinstance(value, int) else None


def _bool_field(raw: dict[str, object], *names: str) -> bool | None:
    value = _field(raw, *names)
    return value if isinstance(value, bool) else None


def _as_string(value: object) -> str | None:
    if value is None:
        return None
    return str(value)
