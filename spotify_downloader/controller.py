"""Application controller orchestrating services and UI."""
from __future__ import annotations

from collections.abc import Callable, Iterable
from logging import Logger
from pathlib import Path

from .exceptions import DownloadError, MetadataError, SpotifyServiceError
from .models import Track
from .services.metadata_writer import MetadataWriter
from .services.spotify_client import SpotifyClient
from .services.track_downloader import TrackDownloader

ProgressCallback = Callable[[int, int, Track, str], None]
StatusCallback = Callable[[str], None]


class SpotifyDownloaderController:
    """Facade combining Spotify, download and metadata services."""

    def __init__(
        self,
        spotify_client: SpotifyClient,
        downloader: TrackDownloader,
        metadata_writer: MetadataWriter,
        logger: Logger,
    ) -> None:
        self._spotify_client = spotify_client
        self._downloader = downloader
        self._metadata_writer = metadata_writer
        self._logger = logger

    def load_tracks(self, playlist_reference: str) -> list[Track]:
        """Load and return tracks for a playlist."""

        self._logger.info("Tracks werden geladen", extra={"playlist": playlist_reference})
        return self._spotify_client.fetch_playlist_tracks(playlist_reference)

    def download_tracks(
        self,
        tracks: Iterable[Track],
        destination: Path,
        status_callback: StatusCallback | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> None:
        """Download selected tracks sequentially with progress updates."""

        destination.mkdir(parents=True, exist_ok=True)
        track_list = list(tracks)
        total = len(track_list)
        if total == 0:
            return

        for index, track in enumerate(track_list, start=1):
            self._update_status(status_callback, f"Lade {track.display_name()}")
            try:
                file_path = self._downloader.download(track, destination)
                bpm, key = self._metadata_writer.apply(file_path, track)
                self._logger.info(
                    "Track verarbeitet",
                    extra={"track": track.display_name(), "bpm": bpm, "key": key},
                )
                self._update_progress(progress_callback, index, total, track, f"BPM {bpm} | Key {key}")
            except (DownloadError, MetadataError, SpotifyServiceError) as exc:
                self._logger.error(
                    "Track konnte nicht verarbeitet werden",
                    extra={"track": track.display_name(), "error": str(exc)},
                )
                self._update_progress(progress_callback, index, total, track, "Fehler")
                continue

        self._update_status(status_callback, "Download abgeschlossen")

    @staticmethod
    def _update_status(callback: StatusCallback | None, message: str) -> None:
        if callback:
            callback(message)

    @staticmethod
    def _update_progress(
        callback: ProgressCallback | None,
        index: int,
        total: int,
        track: Track,
        detail: str,
    ) -> None:
        if callback:
            callback(index, total, track, detail)
