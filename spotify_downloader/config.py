"""Application configuration helpers."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os

from .exceptions import ConfigurationError


@dataclass(frozen=True)
class SpotifyApiConfig:
    """Holds credentials and scopes for the Spotify API."""

    client_id: str
    client_secret: str
    redirect_uri: str
    scope: str = "playlist-read-private"


@dataclass(frozen=True)
class DownloaderRuntimeConfig:
    """Runtime configuration for download behaviour."""

    ffmpeg_path: Path
    request_timeout: float = 15.0
    max_threads: int = 4


@dataclass(frozen=True)
class AppConfig:
    """Aggregate configuration object."""

    spotify: SpotifyApiConfig
    downloader: DownloaderRuntimeConfig

    @staticmethod
    def load_from_env(env: dict[str, str] | None = None) -> "AppConfig":
        """Create a config instance from environment variables.

        Raises:
            ConfigurationError: If required values are missing.
        """

        source = env or os.environ
        client_id = source.get("SPOTIFY_CLIENT_ID")
        client_secret = source.get("SPOTIFY_CLIENT_SECRET")
        redirect_uri = source.get("SPOTIFY_REDIRECT_URI")
        ffmpeg_path_value = source.get("FFMPEG_PATH")

        missing = [
            ("SPOTIFY_CLIENT_ID", client_id),
            ("SPOTIFY_CLIENT_SECRET", client_secret),
            ("SPOTIFY_REDIRECT_URI", redirect_uri),
            ("FFMPEG_PATH", ffmpeg_path_value),
        ]

        missing_keys = [name for name, value in missing if not value]
        if missing_keys:
            raise ConfigurationError(
                f"Fehlende Konfiguration: {', '.join(missing_keys)}"
            )

        scope = source.get("SPOTIFY_SCOPE", "playlist-read-private")
        request_timeout = float(source.get("REQUEST_TIMEOUT", "15"))
        max_threads = int(source.get("MAX_DOWNLOAD_THREADS", "4"))

        spotify_cfg = SpotifyApiConfig(
            client_id=client_id,  # type: ignore[arg-type]
            client_secret=client_secret,  # type: ignore[arg-type]
            redirect_uri=redirect_uri,  # type: ignore[arg-type]
            scope=scope,
        )

        downloader_cfg = DownloaderRuntimeConfig(
            ffmpeg_path=Path(ffmpeg_path_value).expanduser().resolve(),  # type: ignore[arg-type]
            request_timeout=request_timeout,
            max_threads=max(1, max_threads),
        )

        return AppConfig(spotify=spotify_cfg, downloader=downloader_cfg)
