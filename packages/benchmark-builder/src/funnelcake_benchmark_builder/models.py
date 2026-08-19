from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BenchmarkTask:
    name: str
    prompt: str
    expected_signals: tuple[str, ...] = ()


@dataclass(frozen=True)
class BenchmarkSpec:
    platform: str
    tasks: tuple[BenchmarkTask, ...]
