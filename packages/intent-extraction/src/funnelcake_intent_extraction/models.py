from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Intent:
    name: str
    evidence: tuple[str, ...] = ()


@dataclass(frozen=True)
class IntentProfile:
    platform: str
    intents: tuple[Intent, ...]
