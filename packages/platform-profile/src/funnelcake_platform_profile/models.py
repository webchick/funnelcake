from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PlatformProfile:
    name: str
    homepage: str
    docs_url: str | None = None
    notes: tuple[str, ...] = ()
