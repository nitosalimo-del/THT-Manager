"""Filesystem helper functions."""
from __future__ import annotations

import re
from pathlib import Path

_INVALID_CHARS = re.compile(r"[^a-zA-Z0-9äöüÄÖÜß\s\-_.]")
_MULTISPACE = re.compile(r"\s+")


def safe_stem(name: str) -> str:
    """Return a sanitized filename stem without extension."""

    cleaned = _INVALID_CHARS.sub("", name)
    cleaned = _MULTISPACE.sub(" ", cleaned).strip()
    cleaned = cleaned.replace(" ", "_")
    return cleaned or "track"


def safe_filename(name: str, extension: str) -> Path:
    """Create a safe filename for the given name and extension."""

    stem = safe_stem(name)
    extension = extension.lstrip(".")
    return Path(f"{stem}.{extension}")
