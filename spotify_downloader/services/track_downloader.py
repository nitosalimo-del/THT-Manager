"""Downloading tracks from YouTube Music using yt-dlp."""
from __future__ import annotations

from logging import Logger
from pathlib import Path

try:  # pragma: no cover - optional dependency
    import yt_dlp  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    yt_dlp = None  # type: ignore

from ..exceptions import DownloadError
from ..models import Track
from ..utils.filesystem import safe_filename, safe_stem


class TrackDownloader:
    """Handles the actual download and conversion to mp3."""

    def __init__(self, ffmpeg_path: Path, logger: Logger):
        self._ffmpeg_path = ffmpeg_path
        self._logger = logger

    def download(self, track: Track, target_dir: Path) -> Path:
        """Download a single track and return the resulting path."""

        if yt_dlp is None:
            raise DownloadError("yt-dlp nicht installiert")

        target_dir.mkdir(parents=True, exist_ok=True)
        safe_name = safe_stem(track.display_name())
        output_template = target_dir / f"{safe_name}.%(ext)s"

        options = {
            "format": "bestaudio/best",
            "outtmpl": str(output_template),
            "ffmpeg_location": str(self._ffmpeg_path),
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "320",
                }
            ],
            "noplaylist": True,
            "quiet": True,
            "nocheckcertificate": True,
        }

        query = f"ytsearch1:{track.display_name()}"
        try:
            with yt_dlp.YoutubeDL(options) as downloader:
                downloader.extract_info(query, download=True)
        except Exception as exc:  # pragma: no cover - requires network
            self._logger.error("Download fehlgeschlagen", extra={"track": track.display_name()})
            raise DownloadError(f"Download fehlgeschlagen für {track.display_name()}") from exc

        result_path = target_dir / safe_filename(track.display_name(), "mp3")
        if not result_path.exists():
            raise DownloadError(f"Ergebnisdatei fehlt für {track.display_name()}")

        self._logger.info("Download abgeschlossen", extra={"track": track.display_name(), "path": str(result_path)})
        return result_path
