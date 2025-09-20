"""Domain models for the downloader."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class Track:
    """Represents a Spotify track relevant for downloading."""

    track_id: str
    title: str
    artist: str
    album: str
    cover_url: str | None

    def display_name(self) -> str:
        """Return a human readable name."""

        return f"{self.artist} - {self.title}"


@dataclass(slots=True)
class DownloadJob:
    """Represents a download task for the UI progress handling."""

    track: Track
    destination: Path
