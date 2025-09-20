"""Spotify API integration layer."""
from __future__ import annotations

import re
from typing import Iterable

try:  # pragma: no cover - optional dependency
    import spotipy  # type: ignore
    from spotipy.oauth2 import SpotifyOAuth  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    spotipy = None  # type: ignore
    SpotifyOAuth = None  # type: ignore

from ..config import SpotifyApiConfig
from ..exceptions import SpotifyServiceError
from ..models import Track


_PLAYLIST_REGEX = re.compile(r"playlist/([a-zA-Z0-9]+)")


class SpotifyClient:
    """Thin wrapper around the Spotipy client."""

    def __init__(self, config: SpotifyApiConfig):
        self._config = config
        self._client: object | None = None

    @property
    def client(self):  # type: ignore[override]
        """Lazily construct the Spotipy client."""

        if spotipy is None or SpotifyOAuth is None:
            raise SpotifyServiceError("Spotipy ist nicht installiert")

        if self._client is None:
            try:
                self._client = spotipy.Spotify(
                    auth_manager=SpotifyOAuth(
                        client_id=self._config.client_id,
                        client_secret=self._config.client_secret,
                        redirect_uri=self._config.redirect_uri,
                        scope=self._config.scope,
                        open_browser=False,
                    )
                )
            except Exception as exc:  # pragma: no cover - network/auth errors
                raise SpotifyServiceError("Spotify-Authentifizierung fehlgeschlagen") from exc
        return self._client

    def extract_playlist_id(self, playlist_reference: str) -> str:
        """Extract the playlist id from a url or id string."""

        if not playlist_reference:
            raise SpotifyServiceError("Leere Playlist Referenz")

        if len(playlist_reference) == 22 and playlist_reference.isalnum():
            return playlist_reference

        match = _PLAYLIST_REGEX.search(playlist_reference)
        if match:
            return match.group(1)

        raise SpotifyServiceError("Ungültige Playlist-URL")

    def fetch_playlist_tracks(self, playlist_reference: str) -> list[Track]:
        """Load all tracks for a playlist."""

        playlist_id = self.extract_playlist_id(playlist_reference)
        results = self.client.playlist_items(playlist_id, additional_types=("track",))
        tracks = self._parse_tracks(results.get("items", []))

        while results.get("next"):
            results = self.client.next(results)
            tracks.extend(self._parse_tracks(results.get("items", [])))

        if not tracks:
            raise SpotifyServiceError("Playlist enthält keine verfügbaren Tracks")

        return tracks

    def fetch_track(self, track_id: str) -> Track:
        """Fetch full details for a single track."""

        try:
            track_data = self.client.track(track_id)
        except SpotifyServiceError:
            raise
        except Exception as exc:  # pragma: no cover - network/auth errors
            raise SpotifyServiceError("Track konnte nicht geladen werden") from exc

        return Track(
            track_id=track_data["id"],
            title=track_data["name"],
            artist=track_data["artists"][0]["name"],
            album=track_data["album"]["name"],
            cover_url=(track_data["album"]["images"][0]["url"] if track_data["album"].get("images") else None),
        )

    @staticmethod
    def _parse_tracks(items: Iterable[dict]) -> list[Track]:
        """Transform raw API response data into Track objects."""

        parsed: list[Track] = []
        for item in items:
            track = item.get("track")
            if not track:
                continue
            if track.get("is_local"):
                continue
            if track.get("artists") is None:
                continue
            images = track.get("album", {}).get("images") or []
            cover_url = images[0]["url"] if images else None
            parsed.append(
                Track(
                    track_id=track["id"],
                    title=track["name"],
                    artist=track["artists"][0]["name"],
                    album=track.get("album", {}).get("name", ""),
                    cover_url=cover_url,
                )
            )
        return parsed
