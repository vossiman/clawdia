from __future__ import annotations

import asyncio
import logging
from functools import partial

import spotipy
from spotipy.oauth2 import SpotifyOAuth

logger = logging.getLogger(__name__)


class MusicController:
    """Controls Spotify playback via the Web API."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        device_name: str,
        cache_path: str,
        device_controller: MusicController | None = None,
    ):
        self._device_name = device_name
        self._device_controller = device_controller
        auth_manager = SpotifyOAuth(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            scope=(
                "user-modify-playback-state "
                "user-read-playback-state "
                "user-read-currently-playing "
                "playlist-read-private "
                "playlist-read-collaborative"
            ),
            cache_handler=spotipy.CacheFileHandler(cache_path=cache_path),
        )
        self._sp = spotipy.Spotify(auth_manager=auth_manager)

    async def _run(self, func, *args, **kwargs):
        """Run a sync spotipy call in a thread."""
        return await asyncio.to_thread(partial(func, *args, **kwargs))

    @property
    def _playback_sp(self) -> spotipy.Spotify:
        """Spotipy client for device-bound operations.

        Spotify Connect devices are only visible to the account that librespot
        authenticated as. All playback commands must use that account's client.
        """
        if self._device_controller is not None:
            return self._device_controller._sp
        return self._sp

    async def _get_device_id(self) -> str | None:
        """Find the device ID for the librespot instance."""
        devices = await self._run(self._playback_sp.devices)
        for device in devices.get("devices", []):
            if device["name"] == self._device_name:
                return device["id"]
        return None

    async def play(self, uri: str | None = None) -> str:
        """Resume playback or play a specific URI."""
        device_id = await self._get_device_id()
        if not device_id:
            return f"Spotify device '{self._device_name}' not found or offline."
        if uri:
            await self._run(self._playback_sp.start_playback, device_id=device_id, uris=[uri])
            return f"Playing on {self._device_name}."
        else:
            await self._run(self._playback_sp.start_playback, device_id=device_id)
            return "Resuming playback."

    async def pause(self) -> str:
        """Pause playback."""
        device_id = await self._get_device_id()
        if not device_id:
            return f"Spotify device '{self._device_name}' not found or offline."
        await self._run(self._playback_sp.pause_playback, device_id=device_id)
        return "Playback paused."

    async def skip(self) -> str:
        """Skip to next track."""
        device_id = await self._get_device_id()
        if not device_id:
            return f"Spotify device '{self._device_name}' not found or offline."
        await self._run(self._playback_sp.next_track, device_id=device_id)
        return "Skipped to next track."

    async def previous(self) -> str:
        """Go to previous track."""
        device_id = await self._get_device_id()
        if not device_id:
            return f"Spotify device '{self._device_name}' not found or offline."
        await self._run(self._playback_sp.previous_track, device_id=device_id)
        return "Back to previous track."

    async def volume(self, level: int) -> str:
        """Set volume (0-100)."""
        device_id = await self._get_device_id()
        if not device_id:
            return f"Spotify device '{self._device_name}' not found or offline."
        await self._run(self._playback_sp.volume, level, device_id=device_id)
        return f"Volume set to {level}%."

    async def search(self, query: str, search_type: str = "track") -> list[dict]:
        """Search Spotify. Returns list of {name, artists, uri}."""
        results = await self._run(self._sp.search, q=query, type=search_type, limit=5)
        tracks = results.get("tracks", {}).get("items", [])
        return [
            {
                "name": t["name"],
                "artists": ", ".join(a["name"] for a in t["artists"]),
                "uri": t["uri"],
            }
            for t in tracks
        ]

    async def play_query(self, query: str) -> str:
        """Search for a track and play the top result."""
        device_id = await self._get_device_id()
        if not device_id:
            return f"Spotify device '{self._device_name}' not found or offline."
        results = await self._run(self._sp.search, q=query, type="track", limit=5)
        tracks = results.get("tracks", {}).get("items", [])
        if not tracks:
            return f"No results found for '{query}'."
        track = tracks[0]
        name = track["name"]
        artist = track["artists"][0]["name"]
        await self._run(self._playback_sp.start_playback, device_id=device_id, uris=[track["uri"]])
        return f"Now playing: {name} by {artist}"

    async def play_playlist(self, name: str) -> str:
        """Find a playlist by name and play it."""
        playlists = await self._run(self._sp.current_user_playlists, limit=50)
        matched = None
        for pl in playlists.get("items", []):
            if name.lower() in pl["name"].lower():
                matched = pl
                break
        if not matched:
            return f"Could not find a playlist matching '{name}'."
        device_id = await self._get_device_id()
        if not device_id:
            return f"Spotify device '{self._device_name}' not found or offline."
        await self._run(
            self._playback_sp.start_playback,
            device_id=device_id,
            context_uri=matched["uri"],
        )
        return f"Now playing playlist: {matched['name']}"

    async def queue_track(self, query: str) -> str:
        """Search for a track and add it to the queue."""
        device_id = await self._get_device_id()
        if not device_id:
            return f"Spotify device '{self._device_name}' not found or offline."
        results = await self._run(self._sp.search, q=query, type="track", limit=5)
        tracks = results.get("tracks", {}).get("items", [])
        if not tracks:
            return f"No results found for '{query}'."
        track = tracks[0]
        name = track["name"]
        artist = track["artists"][0]["name"]
        await self._run(self._playback_sp.add_to_queue, track["uri"], device_id=device_id)
        return f"Added to queue: {name} by {artist}"

    async def now_playing(self) -> str:
        """Get info about the currently playing track."""
        playback = await self._run(self._playback_sp.current_playback)
        if not playback or not playback.get("item"):
            return "Nothing is currently playing."
        item = playback["item"]
        name = item["name"]
        artist = item["artists"][0]["name"]
        album = item.get("album", {}).get("name", "")
        is_playing = playback.get("is_playing", False)
        status = "Playing" if is_playing else "Paused"
        return f"{status}: {name} by {artist} ({album})"

    async def list_playlists(self) -> list[dict]:
        """List user's playlists. Returns list of {name, uri}."""
        playlists = await self._run(self._sp.current_user_playlists, limit=50)
        return [
            {"name": pl["name"], "uri": pl["uri"]}
            for pl in playlists.get("items", [])
        ]
