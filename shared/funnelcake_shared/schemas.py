from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any


def to_record(value: Any) -> dict[str, Any]:
    if not is_dataclass(value):
        raise TypeError("to_record expects a dataclass instance")
    return asdict(value)
