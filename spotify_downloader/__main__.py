"""CLI entry point for the Spotify downloader application."""
from __future__ import annotations

import sys
from tkinter import messagebox

from .app import SpotifyDownloaderApp
from .config import AppConfig
from .exceptions import ConfigurationError
from .logging_utils import configure_logging
from .services.metadata_writer import MetadataWriter
from .services.spotify_client import SpotifyClient
from .services.track_downloader import TrackDownloader
from .controller import SpotifyDownloaderController


def main() -> None:
    logger = configure_logging()
    try:
        config = AppConfig.load_from_env()
    except ConfigurationError as exc:
        messagebox.showerror("Konfiguration", str(exc))
        sys.exit(1)

    spotify_client = SpotifyClient(config.spotify)
    downloader = TrackDownloader(config.downloader.ffmpeg_path, logger)
    metadata_writer = MetadataWriter(spotify_client, config.downloader.request_timeout, logger)
    controller = SpotifyDownloaderController(spotify_client, downloader, metadata_writer, logger)

    app = SpotifyDownloaderApp(controller)
    app.mainloop()


if __name__ == "__main__":
    main()
