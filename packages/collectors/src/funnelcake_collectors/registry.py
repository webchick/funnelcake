from __future__ import annotations

from .mcp_inspector import MCPInspectorCollector
from .models import Collector
from .native_answer_observation import NativeAnswerObservationCollector
from .promptfoo import PromptfooCollector


COLLECTORS: dict[str, Collector] = {
    NativeAnswerObservationCollector.id: NativeAnswerObservationCollector(),
    MCPInspectorCollector.id: MCPInspectorCollector(),
    PromptfooCollector.id: PromptfooCollector(),
}


COLLECTOR_ALIASES = {
    "answer-observation": NativeAnswerObservationCollector.id,
    "native-answer-observation": NativeAnswerObservationCollector.id,
    "mcp-inspector": MCPInspectorCollector.id,
    "promptfoo": PromptfooCollector.id,
}


def get_collector(collector_id: str) -> Collector:
    normalized_id = COLLECTOR_ALIASES.get(collector_id, collector_id)
    try:
        return COLLECTORS[normalized_id]
    except KeyError as exc:
        choices = ", ".join(sorted((*COLLECTORS, *COLLECTOR_ALIASES)))
        raise ValueError(f"unknown collector {collector_id!r}; expected one of: {choices}") from exc
