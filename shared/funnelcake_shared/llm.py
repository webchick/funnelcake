from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LlmRequest:
    prompt: str
    system: str | None = None
