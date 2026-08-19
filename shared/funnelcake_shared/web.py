from __future__ import annotations

from urllib.parse import urlparse


def normalize_origin(url: str) -> str:
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError(f"Expected absolute URL, got: {url}")
    return f"{parsed.scheme}://{parsed.netloc}"
