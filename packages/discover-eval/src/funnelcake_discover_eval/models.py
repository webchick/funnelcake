from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DiscoveryEvalPlan:
    platform: str
    benchmarks: tuple[str, ...]


@dataclass(frozen=True)
class DiscoveryEvalResult:
    platform: str
    benchmark: str
    passed: bool
    notes: tuple[str, ...] = ()
