"""Custom Exceptions for the Spotify downloader application."""
from __future__ import annotations

from dataclasses import dataclass


class DownloaderError(Exception):
    """Base class for domain specific exceptions."""


class ConfigurationError(DownloaderError):
    """Raised when mandatory configuration values are missing."""


class SpotifyServiceError(DownloaderError):
    """Raised for Spotify API related failures."""


class DownloadError(DownloaderError):
    """Raised when downloading a track fails."""


class MetadataError(DownloaderError):
    """Raised when writing metadata is not possible."""


@dataclass(frozen=True)
class ValidationIssue:
    """Data container used to expose validation issues to the UI."""

    message: str
    hint: str | None = None
