"""Tests for filesystem helper functions."""
from __future__ import annotations

from spotify_downloader.utils.filesystem import safe_filename, safe_stem


def test_safe_stem_removes_invalid_characters() -> None:
    assert safe_stem("Artist: Title???") == "Artist_Title"


def test_safe_filename_with_extension() -> None:
    filename = safe_filename("   ", "mp3")
    assert filename.name == "track.mp3"
