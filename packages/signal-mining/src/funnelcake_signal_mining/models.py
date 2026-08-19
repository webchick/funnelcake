from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Signal:
    source: str
    kind: str
    value: str
    confidence: float = 1.0


@dataclass(frozen=True)
class SignalSet:
    platform: str
    signals: tuple[Signal, ...]
