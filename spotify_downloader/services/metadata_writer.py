"""Metadata enrichment utilities."""
from __future__ import annotations

from logging import Logger
from pathlib import Path

try:  # pragma: no cover - optional dependency
    import librosa  # type: ignore
    import numpy as np  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    librosa = None  # type: ignore
    np = None  # type: ignore

try:  # pragma: no cover - optional dependency
    import requests  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    requests = None  # type: ignore

try:  # pragma: no cover - optional dependency
    from mutagen.easyid3 import EasyID3  # type: ignore
    from mutagen.id3 import APIC, ID3, TBPM, TKEY  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    EasyID3 = None  # type: ignore
    APIC = None  # type: ignore
    ID3 = None  # type: ignore
    TBPM = None  # type: ignore
    TKEY = None  # type: ignore

from ..exceptions import MetadataError, SpotifyServiceError
from ..models import Track
from .spotify_client import SpotifyClient


class MetadataWriter:
    """Derives and writes ID3 metadata including BPM and musical key."""

    def __init__(self, spotify_client: SpotifyClient, request_timeout: float, logger: Logger):
        self._spotify_client = spotify_client
        self._request_timeout = request_timeout
        self._logger = logger

    def apply(self, file_path: Path, track: Track) -> tuple[int, str]:
        """Apply metadata to a given mp3 file."""

        if EasyID3 is None or ID3 is None:
            raise MetadataError("Mutagen nicht installiert")
        if not file_path.exists():
            raise MetadataError(f"Datei nicht gefunden: {file_path}")

        try:
            easy_id3 = EasyID3(file_path)
        except Exception as exc:  # pragma: no cover - IO heavy
            raise MetadataError("ID3-Tags konnten nicht gelesen werden") from exc

        easy_id3["title"] = track.title
        easy_id3["artist"] = track.artist

        track_details = track
        if not track.album or track.cover_url is None:
            try:
                track_details = self._spotify_client.fetch_track(track.track_id)
            except SpotifyServiceError:
                self._logger.warning("Albumdaten konnten nicht nachgeladen werden", extra={"track": track.display_name()})

        if track_details.album:
            easy_id3["album"] = track_details.album

        easy_id3.save()

        self._write_cover_art(file_path, track_details)
        bpm, key = self._analyse_audio(file_path)
        self._write_id3_additional_tags(file_path, bpm, key)
        self._logger.info(
            "Metadaten gesetzt",
            extra={"track": track.display_name(), "bpm": bpm, "key": key},
        )
        return bpm, key

    def _write_cover_art(self, file_path: Path, track: Track) -> None:
        if track.cover_url is None or requests is None or ID3 is None or APIC is None:
            if requests is None:
                self._logger.warning("Requests nicht verfügbar – Cover wird übersprungen")
            return
        try:
            response = requests.get(track.cover_url, timeout=self._request_timeout)
            response.raise_for_status()
        except Exception:  # pragma: no cover - network heavy
            self._logger.warning("Cover konnte nicht geladen werden", extra={"url": track.cover_url})
            return

        try:
            id3 = ID3(file_path)
            id3.delall("APIC")
            id3.add(
                APIC(
                    encoding=3,
                    mime="image/jpeg",
                    type=3,
                    desc="Cover",
                    data=response.content,
                )
            )
            id3.save()
        except Exception as exc:  # pragma: no cover - IO heavy
            raise MetadataError("Cover konnte nicht gespeichert werden") from exc

    def _analyse_audio(self, file_path: Path) -> tuple[int, str]:
        if librosa is None or np is None:
            raise MetadataError("Librosa/Numpy nicht installiert")
        try:
            audio, sample_rate = librosa.load(file_path, sr=None)
            tempo, _ = librosa.beat.beat_track(y=audio, sr=sample_rate)
            chroma = librosa.feature.chroma_stft(y=audio, sr=sample_rate)
        except Exception as exc:  # pragma: no cover - DSP heavy
            raise MetadataError("Analyse der Audiodaten fehlgeschlagen") from exc

        bpm_value = int(round(float(tempo))) if not np.isnan(tempo) else 0
        key_idx = int(np.argmax(chroma.mean(axis=1))) if chroma.size else 0
        key_list = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
        key = key_list[key_idx % len(key_list)]
        return bpm_value, key

    def _write_id3_additional_tags(self, file_path: Path, bpm: int, key: str) -> None:
        if ID3 is None or TBPM is None or TKEY is None:
            raise MetadataError("Mutagen nicht vollständig installiert")
        try:
            id3 = ID3(file_path)
            id3.delall("TBPM")
            id3.delall("TKEY")
            id3.add(TBPM(encoding=3, text=str(bpm)))
            id3.add(TKEY(encoding=3, text=key))
            id3.save()
        except Exception as exc:  # pragma: no cover - IO heavy
            raise MetadataError("Zusätzliche ID3-Tags konnten nicht gespeichert werden") from exc
