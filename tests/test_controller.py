"""Tests for the controller orchestration logic."""
from __future__ import annotations

from pathlib import Path

from spotify_downloader.controller import SpotifyDownloaderController
from spotify_downloader.models import Track


class DummyDownloader:
    def __init__(self, tmp_dir: Path) -> None:
        self.tmp_dir = tmp_dir
        self.downloaded: list[str] = []

    def download(self, track: Track, destination: Path) -> Path:
        self.downloaded.append(track.track_id)
        destination.mkdir(parents=True, exist_ok=True)
        path = destination / f"{track.track_id}.mp3"
        path.write_bytes(b"data")
        return path


class DummyMetadataWriter:
    def apply(self, file_path: Path, track: Track) -> tuple[int, str]:
        return 120, "C"


class DummySpotifyClient:
    def fetch_playlist_tracks(self, playlist: str) -> list[Track]:  # pragma: no cover - not used here
        raise NotImplementedError


class DummyLogger:
    def info(self, *args, **kwargs) -> None:  # pragma: no cover - no-op logging
        pass

    def error(self, *args, **kwargs) -> None:  # pragma: no cover - no-op logging
        pass


def test_controller_download_tracks(tmp_path: Path) -> None:
    track = Track(track_id="1", title="Song", artist="Artist", album="Album", cover_url=None)
    downloader = DummyDownloader(tmp_path)
    metadata_writer = DummyMetadataWriter()
    controller = SpotifyDownloaderController(
        spotify_client=DummySpotifyClient(),
        downloader=downloader,
        metadata_writer=metadata_writer,
        logger=DummyLogger(),
    )

    progress_events: list[tuple[int, int, Track, str]] = []
    status_updates: list[str] = []

    controller.download_tracks(
        tracks=[track],
        destination=tmp_path,
        status_callback=status_updates.append,
        progress_callback=lambda *args: progress_events.append(args),
    )

    assert downloader.downloaded == ["1"]
    assert status_updates[-1] == "Download abgeschlossen"
    assert progress_events[0][0:2] == (1, 1)
    assert progress_events[0][3] == "BPM 120 | Key C"
