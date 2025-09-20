"""Tests for configuration loading."""
from __future__ import annotations

from pathlib import Path

import pytest

from spotify_downloader.config import AppConfig
from spotify_downloader.exceptions import ConfigurationError


def test_config_load_from_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "client")
    monkeypatch.setenv("SPOTIFY_CLIENT_SECRET", "secret")
    monkeypatch.setenv("SPOTIFY_REDIRECT_URI", "http://localhost")
    monkeypatch.setenv("FFMPEG_PATH", str(tmp_path / "ffmpeg.exe"))
    monkeypatch.setenv("MAX_DOWNLOAD_THREADS", "2")

    config = AppConfig.load_from_env()

    assert config.spotify.client_id == "client"
    assert config.downloader.ffmpeg_path.name == "ffmpeg.exe"
    assert config.downloader.max_threads == 2


def test_config_load_missing_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SPOTIFY_CLIENT_ID", raising=False)
    monkeypatch.delenv("SPOTIFY_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("SPOTIFY_REDIRECT_URI", raising=False)
    monkeypatch.delenv("FFMPEG_PATH", raising=False)

    with pytest.raises(ConfigurationError):
        AppConfig.load_from_env()
