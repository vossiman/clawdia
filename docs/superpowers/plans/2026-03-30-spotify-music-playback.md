# Spotify Music Playback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Spotify music playback to Clawdia via spotifyd on the Pi host and the Spotify Web API (spotipy) in the application.

**Architecture:** spotifyd runs on the Pi host as a Spotify Connect device. Clawdia controls playback via the Spotify Web API using the spotipy Python library. A new `music` action type is added to the brain alongside the existing `ir` and `respond` actions.

**Tech Stack:** spotipy (Spotify Web API wrapper), spotifyd (Spotify Connect daemon on host), PydanticAI (brain routing), python-telegram-bot (slash commands)

---

### File Map

| Action | Path | Responsibility |
|--------|------|---------------|
| Create | `src/clawdia/music/__init__.py` | Export MusicController |
| Create | `src/clawdia/music/controller.py` | Spotify Web API wrapper |
| Create | `tests/test_music_controller.py` | MusicController unit tests |
| Create | `tests/test_music_orchestrator.py` | Orchestrator music routing tests |
| Create | `tests/test_music_telegram.py` | Telegram music command tests |
| Create | `tests/test_music_models.py` | MusicAction model tests |
| Modify | `src/clawdia/brain/models.py` | Add MusicAction, update ClawdiaResponse |
| Modify | `src/clawdia/brain/agent.py` | Update system prompt for music routing |
| Modify | `src/clawdia/brain/__init__.py` | Accept MusicController for prompt building |
| Modify | `src/clawdia/orchestrator.py` | Route music actions to MusicController |
| Modify | `src/clawdia/telegram_bot/bot.py` | Add music slash commands |
| Modify | `src/clawdia/config.py` | Add Spotify settings |
| Modify | `src/clawdia/main.py` | Wire MusicController into startup |
| Modify | `pyproject.toml` | Add spotipy dependency |
| Modify | `docker-compose.yml` | Add Spotify cache volume |

---

### Task 1: Add spotipy dependency

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add spotipy to dependencies**

In `pyproject.toml`, add `spotipy` to the dependencies list:

```toml
dependencies = [
    "pydantic>=2.0",
    "pydantic-settings>=2.0",
    "pydantic-ai-slim[openrouter]>=1.0",
    "openai>=1.0",
    "python-telegram-bot>=22.0",
    "httpx>=0.27",
    "spotipy>=2.24",
]
```

- [ ] **Step 2: Install updated dependencies**

Run: `cd /home/vossi/local_dev/clawdia && uv sync`

- [ ] **Step 3: Verify import works**

Run: `cd /home/vossi/local_dev/clawdia && uv run python -c "import spotipy; print(spotipy.__version__)"`
Expected: Prints version number without error.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "feat(music): add spotipy dependency"
```

---

### Task 2: Add Spotify config settings

**Files:**
- Modify: `src/clawdia/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**

Create test in `tests/test_config.py` (append to existing file):

```python
def test_spotify_settings():
    s = Settings(
        spotify_client_id="test-id",
        spotify_client_secret="test-secret",
        spotify_device_name="test-device",
    )
    assert s.spotify_client_id == "test-id"
    assert s.spotify_client_secret == "test-secret"
    assert s.spotify_redirect_uri == "http://localhost:8888/callback"
    assert s.spotify_device_name == "test-device"
    assert s.spotify_cache_path == ".spotify_cache"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/vossi/local_dev/clawdia && uv run pytest tests/test_config.py::test_spotify_settings -v`
Expected: FAIL — `Settings` does not accept `spotify_client_id`.

- [ ] **Step 3: Add Spotify settings to config**

In `src/clawdia/config.py`, add after the Voice section:

```python
    # Spotify
    spotify_client_id: str = ""
    spotify_client_secret: str = ""
    spotify_redirect_uri: str = "http://localhost:8888/callback"
    spotify_device_name: str = "clawdia"
    spotify_cache_path: str = ".spotify_cache"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/vossi/local_dev/clawdia && uv run pytest tests/test_config.py::test_spotify_settings -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/clawdia/config.py tests/test_config.py
git commit -m "feat(music): add Spotify settings to config"
```

---

### Task 3: Add MusicAction model and update ClawdiaResponse

**Files:**
- Modify: `src/clawdia/brain/models.py`
- Test: `tests/test_music_models.py` (create)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_music_models.py`:

```python
import pytest
from clawdia.brain.models import ClawdiaResponse, MusicAction


def test_music_action_play_query():
    action = MusicAction(command="play_query", query="chill jazz")
    assert action.command == "play_query"
    assert action.query == "chill jazz"
    assert action.volume is None


def test_music_action_volume():
    action = MusicAction(command="volume", volume=75)
    assert action.volume == 75


def test_music_action_pause():
    action = MusicAction(command="pause")
    assert action.command == "pause"
    assert action.query is None


def test_music_response():
    r = ClawdiaResponse(
        action="music",
        music=MusicAction(command="play_query", query="jazz"),
        message="Playing jazz",
    )
    assert r.action == "music"
    assert r.music.command == "play_query"
    assert r.music.query == "jazz"


def test_music_response_requires_music_field():
    with pytest.raises(Exception):
        ClawdiaResponse(action="music", message="oops")


def test_ir_response_still_works():
    from clawdia.brain.models import IRAction
    r = ClawdiaResponse(
        action="ir",
        ir=IRAction(command="power"),
        message="Turning off the TV",
    )
    assert r.action == "ir"
    assert r.ir.command == "power"
    assert r.music is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/vossi/local_dev/clawdia && uv run pytest tests/test_music_models.py -v`
Expected: FAIL — `MusicAction` not found.

- [ ] **Step 3: Add MusicAction and update ClawdiaResponse**

Replace `src/clawdia/brain/models.py` with:

```python
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class IRAction(BaseModel):
    """An IR command to send to the TV."""
    command: str = Field(description="IR command name, e.g. 'power', 'vol_up', 'channel_3'")
    repeat: int = Field(default=1, description="Number of times to send the command", ge=1, le=10)


class MusicAction(BaseModel):
    """A music playback command."""
    command: Literal[
        "play", "pause", "skip", "previous", "volume",
        "search", "play_query", "play_playlist", "queue",
        "now_playing", "list_playlists",
    ] = Field(description="Music command to execute")
    query: str | None = Field(default=None, description="Search query or playlist name")
    volume: int | None = Field(default=None, description="Volume level 0-100", ge=0, le=100)


class ClawdiaResponse(BaseModel):
    """Structured response from the Clawdia brain."""
    action: Literal["ir", "respond", "music"] = Field(
        description="'ir' to send an IR command, 'respond' to reply with text, 'music' to control music"
    )
    ir: IRAction | None = Field(
        default=None, description="IR command details, required if action='ir'"
    )
    music: MusicAction | None = Field(
        default=None, description="Music command details, required if action='music'"
    )
    message: str = Field(
        description="Human-readable message describing what was done or the answer"
    )

    @model_validator(mode="after")
    def validate_action_fields(self) -> ClawdiaResponse:
        if self.action == "ir" and self.ir is None:
            raise ValueError("'ir' field is required when action is 'ir'")
        if self.action == "music" and self.music is None:
            raise ValueError("'music' field is required when action is 'music'")
        return self
```

- [ ] **Step 4: Run new tests and existing model tests**

Run: `cd /home/vossi/local_dev/clawdia && uv run pytest tests/test_music_models.py tests/test_brain_models.py -v`
Expected: All PASS (existing tests should still pass with the updated model).

- [ ] **Step 5: Commit**

```bash
git add src/clawdia/brain/models.py tests/test_music_models.py
git commit -m "feat(music): add MusicAction model and music action type"
```

---

### Task 4: Implement MusicController

**Files:**
- Create: `src/clawdia/music/__init__.py`
- Create: `src/clawdia/music/controller.py`
- Create: `tests/test_music_controller.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_music_controller.py`:

```python
import pytest
from unittest.mock import MagicMock, patch

from clawdia.music.controller import MusicController


@pytest.fixture
def mock_spotify():
    """Mock spotipy.Spotify client."""
    return MagicMock()


@pytest.fixture
def controller(mock_spotify):
    with patch("clawdia.music.controller.spotipy.Spotify", return_value=mock_spotify):
        with patch("clawdia.music.controller.SpotifyOAuth"):
            c = MusicController(
                client_id="test-id",
                client_secret="test-secret",
                redirect_uri="http://localhost:8888/callback",
                device_name="clawdia",
                cache_path="/tmp/test-cache",
            )
            c._sp = mock_spotify
            return c


def _device_list(name="clawdia"):
    return {"devices": [{"id": "dev123", "name": name, "is_active": True}]}


def _current_playback(track="Chill Vibes", artist="DJ Test"):
    return {
        "is_playing": True,
        "item": {
            "name": track,
            "artists": [{"name": artist}],
            "album": {"name": "Test Album"},
        },
    }


async def test_play_query(controller, mock_spotify):
    mock_spotify.devices.return_value = _device_list()
    mock_spotify.search.return_value = {
        "tracks": {"items": [{"uri": "spotify:track:123", "name": "Jazz Song", "artists": [{"name": "Artist"}]}]}
    }
    result = await controller.play_query("jazz")
    mock_spotify.start_playback.assert_called_once_with(device_id="dev123", uris=["spotify:track:123"])
    assert "Jazz Song" in result


async def test_pause(controller, mock_spotify):
    mock_spotify.devices.return_value = _device_list()
    result = await controller.pause()
    mock_spotify.pause_playback.assert_called_once_with(device_id="dev123")
    assert "pause" in result.lower()


async def test_skip(controller, mock_spotify):
    mock_spotify.devices.return_value = _device_list()
    result = await controller.skip()
    mock_spotify.next_track.assert_called_once_with(device_id="dev123")
    assert "skip" in result.lower()


async def test_previous(controller, mock_spotify):
    mock_spotify.devices.return_value = _device_list()
    result = await controller.previous()
    mock_spotify.previous_track.assert_called_once_with(device_id="dev123")
    assert "previous" in result.lower()


async def test_volume(controller, mock_spotify):
    mock_spotify.devices.return_value = _device_list()
    result = await controller.volume(75)
    mock_spotify.volume.assert_called_once_with(75, device_id="dev123")
    assert "75" in result


async def test_now_playing(controller, mock_spotify):
    mock_spotify.current_playback.return_value = _current_playback()
    result = await controller.now_playing()
    assert "Chill Vibes" in result
    assert "DJ Test" in result


async def test_now_playing_nothing(controller, mock_spotify):
    mock_spotify.current_playback.return_value = None
    result = await controller.now_playing()
    assert "nothing" in result.lower()


async def test_play_playlist(controller, mock_spotify):
    mock_spotify.devices.return_value = _device_list()
    mock_spotify.current_user_playlists.return_value = {
        "items": [{"name": "Chill Mix", "uri": "spotify:playlist:abc"}],
    }
    result = await controller.play_playlist("chill")
    mock_spotify.start_playback.assert_called_once_with(device_id="dev123", context_uri="spotify:playlist:abc")
    assert "Chill Mix" in result


async def test_play_playlist_not_found(controller, mock_spotify):
    mock_spotify.current_user_playlists.return_value = {"items": []}
    result = await controller.play_playlist("nonexistent")
    assert "not find" in result.lower() or "no playlist" in result.lower()


async def test_queue_track(controller, mock_spotify):
    mock_spotify.devices.return_value = _device_list()
    mock_spotify.search.return_value = {
        "tracks": {"items": [{"uri": "spotify:track:456", "name": "Queue Song", "artists": [{"name": "Artist"}]}]}
    }
    result = await controller.queue_track("queue song")
    mock_spotify.add_to_queue.assert_called_once_with("spotify:track:456", device_id="dev123")
    assert "Queue Song" in result


async def test_search(controller, mock_spotify):
    mock_spotify.search.return_value = {
        "tracks": {"items": [
            {"name": "Track 1", "artists": [{"name": "A1"}], "uri": "spotify:track:1"},
            {"name": "Track 2", "artists": [{"name": "A2"}], "uri": "spotify:track:2"},
        ]}
    }
    results = await controller.search("test")
    assert len(results) == 2
    assert results[0]["name"] == "Track 1"


async def test_list_playlists(controller, mock_spotify):
    mock_spotify.current_user_playlists.return_value = {
        "items": [
            {"name": "Playlist A", "uri": "spotify:playlist:a"},
            {"name": "Playlist B", "uri": "spotify:playlist:b"},
        ]
    }
    results = await controller.list_playlists()
    assert len(results) == 2
    assert results[0]["name"] == "Playlist A"


async def test_device_not_found(controller, mock_spotify):
    mock_spotify.devices.return_value = {"devices": []}
    result = await controller.play_query("test")
    assert "not found" in result.lower() or "offline" in result.lower()
    mock_spotify.start_playback.assert_not_called()


async def test_play_resume(controller, mock_spotify):
    mock_spotify.devices.return_value = _device_list()
    result = await controller.play()
    mock_spotify.start_playback.assert_called_once_with(device_id="dev123")
    assert "resum" in result.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/vossi/local_dev/clawdia && uv run pytest tests/test_music_controller.py -v`
Expected: FAIL — `clawdia.music.controller` not found.

- [ ] **Step 3: Create the music package**

Create `src/clawdia/music/__init__.py`:

```python
from clawdia.music.controller import MusicController

__all__ = ["MusicController"]
```

- [ ] **Step 4: Implement MusicController**

Create `src/clawdia/music/controller.py`:

```python
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
    ):
        self._device_name = device_name
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

    async def _get_device_id(self) -> str | None:
        """Find the device ID for our spotifyd instance."""
        devices = await self._run(self._sp.devices)
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
            await self._run(self._sp.start_playback, device_id=device_id, uris=[uri])
            return f"Playing on {self._device_name}."
        else:
            await self._run(self._sp.start_playback, device_id=device_id)
            return "Resuming playback."

    async def pause(self) -> str:
        """Pause playback."""
        device_id = await self._get_device_id()
        if not device_id:
            return f"Spotify device '{self._device_name}' not found or offline."
        await self._run(self._sp.pause_playback, device_id=device_id)
        return "Playback paused."

    async def skip(self) -> str:
        """Skip to next track."""
        device_id = await self._get_device_id()
        if not device_id:
            return f"Spotify device '{self._device_name}' not found or offline."
        await self._run(self._sp.next_track, device_id=device_id)
        return "Skipped to next track."

    async def previous(self) -> str:
        """Go to previous track."""
        device_id = await self._get_device_id()
        if not device_id:
            return f"Spotify device '{self._device_name}' not found or offline."
        await self._run(self._sp.previous_track, device_id=device_id)
        return "Back to previous track."

    async def volume(self, level: int) -> str:
        """Set volume (0-100)."""
        device_id = await self._get_device_id()
        if not device_id:
            return f"Spotify device '{self._device_name}' not found or offline."
        await self._run(self._sp.volume, level, device_id=device_id)
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
        results = await self._run(self._sp.search, q=query, type="track", limit=1)
        tracks = results.get("tracks", {}).get("items", [])
        if not tracks:
            return f"No results found for '{query}'."
        track = tracks[0]
        name = track["name"]
        artist = track["artists"][0]["name"]
        await self._run(self._sp.start_playback, device_id=device_id, uris=[track["uri"]])
        return f"Now playing: {name} by {artist}"

    async def play_playlist(self, name: str) -> str:
        """Find a playlist by name and play it."""
        device_id = await self._get_device_id()
        if not device_id:
            return f"Spotify device '{self._device_name}' not found or offline."
        playlists = await self._run(self._sp.current_user_playlists, limit=50)
        for pl in playlists.get("items", []):
            if name.lower() in pl["name"].lower():
                await self._run(
                    self._sp.start_playback,
                    device_id=device_id,
                    context_uri=pl["uri"],
                )
                return f"Now playing playlist: {pl['name']}"
        return f"Could not find a playlist matching '{name}'."

    async def queue_track(self, query: str) -> str:
        """Search for a track and add it to the queue."""
        device_id = await self._get_device_id()
        if not device_id:
            return f"Spotify device '{self._device_name}' not found or offline."
        results = await self._run(self._sp.search, q=query, type="track", limit=1)
        tracks = results.get("tracks", {}).get("items", [])
        if not tracks:
            return f"No results found for '{query}'."
        track = tracks[0]
        name = track["name"]
        artist = track["artists"][0]["name"]
        await self._run(self._sp.add_to_queue, track["uri"], device_id=device_id)
        return f"Added to queue: {name} by {artist}"

    async def now_playing(self) -> str:
        """Get info about the currently playing track."""
        playback = await self._run(self._sp.current_playback)
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
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /home/vossi/local_dev/clawdia && uv run pytest tests/test_music_controller.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add src/clawdia/music/__init__.py src/clawdia/music/controller.py tests/test_music_controller.py
git commit -m "feat(music): implement MusicController with Spotify Web API"
```

---

### Task 5: Update brain system prompt for music routing

**Files:**
- Modify: `src/clawdia/brain/agent.py`
- Modify: `src/clawdia/brain/__init__.py`
- Test: `tests/test_brain_agent.py` (existing, extend)

- [ ] **Step 1: Read existing brain agent tests**

Read `tests/test_brain_agent.py` to understand the current test patterns.

- [ ] **Step 2: Write the failing test**

Append to `tests/test_brain_agent.py`:

```python
from clawdia.brain.agent import build_system_prompt


def test_system_prompt_includes_music_section():
    """System prompt should include music capabilities when no music controller given."""
    from unittest.mock import MagicMock
    ir = MagicMock()
    ir.list_commands_with_descriptions.return_value = []
    prompt = build_system_prompt(ir=ir, music=None)
    # Should mention music but say it's not configured
    assert "music" in prompt.lower() or "Music" in prompt


def test_system_prompt_with_music_enabled():
    """System prompt should describe music commands when music controller is provided."""
    from unittest.mock import MagicMock
    ir = MagicMock()
    ir.list_commands_with_descriptions.return_value = []
    music = MagicMock()
    prompt = build_system_prompt(ir=ir, music=music)
    assert "action=\"music\"" in prompt or 'action="music"' in prompt
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd /home/vossi/local_dev/clawdia && uv run pytest tests/test_brain_agent.py::test_system_prompt_includes_music_section -v`
Expected: FAIL — `build_system_prompt` does not accept `music` parameter.

- [ ] **Step 4: Update the system prompt and build function**

Replace `src/clawdia/brain/agent.py`:

```python
from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic_ai import Agent

from clawdia.brain.models import ClawdiaResponse

if TYPE_CHECKING:
    from clawdia.ir import IRController
    from clawdia.music import MusicController

SYSTEM_PROMPT = """\
You are Clawdia, a voice-controlled home assistant running on a Raspberry Pi.

You can control devices via infrared commands, control music playback, and answer general questions.

## Available IR Commands

{ir_commands}

## Music Playback

{music_section}

## Rules

1. If the user wants to control a device (TV, etc.), respond with action="ir" and the exact command name.
2. If the user wants to play music, search for songs, control playback (pause, skip, volume, etc.), or manage playlists, respond with action="music" with the appropriate command.
3. If the user asks a question or wants information, respond with action="respond" and your answer.
4. Always include a brief, friendly message describing what you did or your answer.
5. If no IR command matches what the user wants, respond with action="respond" and tell them.
6. If you're unsure what the user wants, respond with action="respond" and ask for clarification.

### Music Commands Reference

- play: Resume playback
- pause: Pause playback
- skip: Skip to next track
- previous: Go to previous track
- volume: Set volume (include volume field, 0-100)
- play_query: Search and play a track (include query field)
- play_playlist: Find and play a playlist by name (include query field)
- queue: Add a track to the queue (include query field)
- search: Search for tracks (include query field)
- now_playing: Show what's currently playing
- list_playlists: List available playlists
"""

MUSIC_ENABLED = "Music playback is available via Spotify. Use action=\"music\" for any music-related requests."
MUSIC_DISABLED = "Music playback is not currently configured."


def build_system_prompt(ir: IRController, music: MusicController | None = None) -> str:
    commands = ir.list_commands_with_descriptions()
    if commands:
        lines = [f"- {name}: {desc}" if desc else f"- {name}" for name, desc in commands]
        ir_commands = "\n".join(lines)
    else:
        ir_commands = "No IR commands recorded yet."

    music_section = MUSIC_ENABLED if music else MUSIC_DISABLED

    return SYSTEM_PROMPT.format(ir_commands=ir_commands, music_section=music_section)


def create_agent(
    model: str = "openrouter:anthropic/claude-haiku-4.5",
    ir: IRController | None = None,
    music: MusicController | None = None,
) -> Agent:
    """Create the Clawdia PydanticAI agent."""
    if ir:
        prompt = build_system_prompt(ir=ir, music=music)
    else:
        prompt = SYSTEM_PROMPT.format(
            ir_commands="No IR commands recorded yet.",
            music_section=MUSIC_ENABLED if music else MUSIC_DISABLED,
        )
    return Agent(
        model,
        output_type=ClawdiaResponse,
        instructions=prompt,
    )
```

- [ ] **Step 5: Update Brain class to accept music controller**

In `src/clawdia/brain/__init__.py`, replace the file:

```python
from __future__ import annotations

from typing import TYPE_CHECKING

from clawdia.brain.agent import create_agent
from clawdia.brain.models import ClawdiaResponse

if TYPE_CHECKING:
    from clawdia.ir import IRController
    from clawdia.music import MusicController


class Brain:
    """High-level interface to the Clawdia intent engine."""

    def __init__(
        self,
        model: str = "openrouter:anthropic/claude-haiku-4.5",
        ir: IRController | None = None,
        music: MusicController | None = None,
    ):
        self._model = model
        self._ir = ir
        self._music = music
        self.agent = create_agent(model=model, ir=ir, music=music)

    def reload_commands(self) -> None:
        """Rebuild the agent with current IR commands."""
        self.agent = create_agent(model=self._model, ir=self._ir, music=self._music)

    async def process(self, text: str) -> ClawdiaResponse:
        """Process a text command and return a structured response."""
        result = await self.agent.run(text)
        return result.output
```

- [ ] **Step 6: Run all brain-related tests**

Run: `cd /home/vossi/local_dev/clawdia && uv run pytest tests/test_brain_agent.py tests/test_brain_models.py tests/test_music_models.py -v`
Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add src/clawdia/brain/agent.py src/clawdia/brain/__init__.py tests/test_brain_agent.py
git commit -m "feat(music): update brain system prompt for music action routing"
```

---

### Task 6: Update orchestrator for music routing

**Files:**
- Modify: `src/clawdia/orchestrator.py`
- Create: `tests/test_music_orchestrator.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_music_orchestrator.py`:

```python
from unittest.mock import AsyncMock, MagicMock

from clawdia.brain.models import ClawdiaResponse, MusicAction
from clawdia.orchestrator import Orchestrator


async def test_handle_music_play_query():
    mock_brain = AsyncMock()
    mock_ir = MagicMock()
    mock_telegram = AsyncMock()
    mock_music = AsyncMock()
    mock_music.play_query.return_value = "Now playing: Jazz Song by Artist"

    response = ClawdiaResponse(
        action="music",
        music=MusicAction(command="play_query", query="jazz"),
        message="Playing jazz for you",
    )
    mock_brain.process.return_value = response

    orch = Orchestrator(brain=mock_brain, ir=mock_ir, telegram=mock_telegram, music=mock_music)
    await orch.handle_text_command("play some jazz")

    mock_music.play_query.assert_called_once_with("jazz")
    mock_telegram.notify.assert_called_once_with("Now playing: Jazz Song by Artist")


async def test_handle_music_pause():
    mock_brain = AsyncMock()
    mock_ir = MagicMock()
    mock_telegram = AsyncMock()
    mock_music = AsyncMock()
    mock_music.pause.return_value = "Playback paused."

    response = ClawdiaResponse(
        action="music",
        music=MusicAction(command="pause"),
        message="Pausing music",
    )
    mock_brain.process.return_value = response

    orch = Orchestrator(brain=mock_brain, ir=mock_ir, telegram=mock_telegram, music=mock_music)
    await orch.handle_text_command("pause the music")

    mock_music.pause.assert_called_once()
    mock_telegram.notify.assert_called_once_with("Playback paused.")


async def test_handle_music_volume():
    mock_brain = AsyncMock()
    mock_ir = MagicMock()
    mock_telegram = AsyncMock()
    mock_music = AsyncMock()
    mock_music.volume.return_value = "Volume set to 50%."

    response = ClawdiaResponse(
        action="music",
        music=MusicAction(command="volume", volume=50),
        message="Setting volume",
    )
    mock_brain.process.return_value = response

    orch = Orchestrator(brain=mock_brain, ir=mock_ir, telegram=mock_telegram, music=mock_music)
    await orch.handle_text_command("set volume to 50")

    mock_music.volume.assert_called_once_with(50)


async def test_handle_music_no_controller():
    mock_brain = AsyncMock()
    mock_ir = MagicMock()
    mock_telegram = AsyncMock()

    response = ClawdiaResponse(
        action="music",
        music=MusicAction(command="pause"),
        message="Pausing",
    )
    mock_brain.process.return_value = response

    orch = Orchestrator(brain=mock_brain, ir=mock_ir, telegram=mock_telegram)
    await orch.handle_text_command("pause")

    mock_telegram.notify.assert_called_once()
    assert "not configured" in mock_telegram.notify.call_args[0][0].lower()


async def test_ir_still_works_with_music():
    """Ensure existing IR routing is unchanged."""
    mock_brain = AsyncMock()
    mock_ir = MagicMock()
    mock_ir.has_command.return_value = True
    mock_ir.send = AsyncMock(return_value=True)
    mock_telegram = AsyncMock()
    mock_music = AsyncMock()

    from clawdia.brain.models import IRAction
    response = ClawdiaResponse(
        action="ir",
        ir=IRAction(command="power"),
        message="Turning off TV",
    )
    mock_brain.process.return_value = response

    orch = Orchestrator(brain=mock_brain, ir=mock_ir, telegram=mock_telegram, music=mock_music)
    await orch.handle_text_command("turn off the TV")

    mock_ir.send.assert_called_once()
    mock_music.play_query.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/vossi/local_dev/clawdia && uv run pytest tests/test_music_orchestrator.py -v`
Expected: FAIL — `Orchestrator` does not accept `music` parameter.

- [ ] **Step 3: Update the orchestrator**

Replace `src/clawdia/orchestrator.py`:

```python
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from clawdia.brain import Brain
    from clawdia.brain.models import MusicAction
    from clawdia.ir import IRController
    from clawdia.music import MusicController
    from clawdia.telegram_bot import ClawdiaTelegramBot
    from clawdia.voice.stt import SpeechToText

logger = logging.getLogger(__name__)

MUSIC_DISPATCH = {
    "play": lambda m, a: m.play(a.query),
    "pause": lambda m, a: m.pause(),
    "skip": lambda m, a: m.skip(),
    "previous": lambda m, a: m.previous(),
    "volume": lambda m, a: m.volume(a.volume),
    "play_query": lambda m, a: m.play_query(a.query),
    "play_playlist": lambda m, a: m.play_playlist(a.query),
    "queue": lambda m, a: m.queue_track(a.query),
    "search": lambda m, a: m.search(a.query),
    "now_playing": lambda m, a: m.now_playing(),
    "list_playlists": lambda m, a: m.list_playlists(),
}


class Orchestrator:
    """Coordinates the full Clawdia pipeline.

    Connects: voice -> STT -> brain -> action routing (IR / Music / Telegram).
    """

    def __init__(
        self,
        brain: Brain,
        ir: IRController,
        telegram: ClawdiaTelegramBot,
        stt: SpeechToText | None = None,
        music: MusicController | None = None,
    ):
        self.brain = brain
        self.ir = ir
        self.telegram = telegram
        self.stt = stt
        self.music = music

    async def _handle_music(self, action: MusicAction) -> str:
        """Dispatch a music action to the controller."""
        if not self.music:
            return "Music playback is not configured."
        handler = MUSIC_DISPATCH.get(action.command)
        if not handler:
            return f"Unknown music command: {action.command}"
        result = await handler(self.music, action)
        if isinstance(result, list):
            # search / list_playlists return lists
            if not result:
                return "No results found."
            lines = [f"• {r['name']} — {r.get('artists', '')}" if 'artists' in r else f"• {r['name']}" for r in result]
            return "\n".join(lines)
        return result

    async def handle_text_command(self, text: str) -> None:
        """Process a text command through the full pipeline."""
        logger.info("Processing command: '%s'", text)

        try:
            response = await self.brain.process(text)
        except Exception:
            logger.exception("Brain processing failed")
            await self.telegram.notify("Sorry, I had trouble understanding that.")
            return

        if response.action == "ir" and response.ir:
            if not self.ir.has_command(response.ir.command):
                msg = f"IR command '{response.ir.command}' not available. Record it first."
                logger.warning(msg)
                await self.telegram.notify(msg)
                return

            success = await self.ir.send(
                command=response.ir.command,
                repeat=response.ir.repeat,
            )
            if success:
                await self.telegram.notify(response.message)
            else:
                await self.telegram.notify(f"Failed to send IR command: {response.ir.command}")

        elif response.action == "music" and response.music:
            result = await self._handle_music(response.music)
            await self.telegram.notify(result)

        elif response.action == "respond":
            await self.telegram.notify(response.message)

    async def handle_audio(self, pcm_data: bytes) -> None:
        """Process captured audio through STT -> brain -> action."""
        if self.stt is None:
            logger.error("STT not configured")
            return

        wav_data = self.stt.pcm_to_wav(pcm_data)
        text = await self.stt.transcribe(wav_data)

        if not text:
            logger.info("STT returned empty transcript, ignoring")
            return

        await self.handle_text_command(text)
```

- [ ] **Step 4: Run new and existing orchestrator tests**

Run: `cd /home/vossi/local_dev/clawdia && uv run pytest tests/test_music_orchestrator.py tests/test_orchestrator.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/clawdia/orchestrator.py tests/test_music_orchestrator.py
git commit -m "feat(music): add music action routing to orchestrator"
```

---

### Task 7: Add Telegram music slash commands

**Files:**
- Modify: `src/clawdia/telegram_bot/bot.py`
- Create: `tests/test_music_telegram.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_music_telegram.py`:

```python
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from clawdia.telegram_bot.bot import ClawdiaTelegramBot


@pytest.fixture
def bot():
    b = ClawdiaTelegramBot(
        token="test-token",
        chat_id=12345,
        brain=AsyncMock(),
        ir=MagicMock(),
        music=AsyncMock(),
    )
    return b


def _make_update(text, chat_id=12345, args=None):
    update = MagicMock()
    update.message.text = text
    update.effective_chat.id = chat_id
    update.message.reply_text = AsyncMock()
    context = MagicMock()
    context.args = args or []
    return update, context


async def test_play_command(bot):
    bot.music.play_query.return_value = "Now playing: Song by Artist"
    update, context = _make_update("/play jazz", args=["jazz"])
    await bot._handle_play(update, context)
    bot.music.play_query.assert_called_once_with("jazz")
    update.message.reply_text.assert_called_once_with("Now playing: Song by Artist")


async def test_play_no_query(bot):
    bot.music.play.return_value = "Resuming playback."
    update, context = _make_update("/play", args=[])
    await bot._handle_play(update, context)
    bot.music.play.assert_called_once()


async def test_pause_command(bot):
    bot.music.pause.return_value = "Playback paused."
    update, context = _make_update("/pause")
    await bot._handle_pause(update, context)
    bot.music.pause.assert_called_once()


async def test_skip_command(bot):
    bot.music.skip.return_value = "Skipped to next track."
    update, context = _make_update("/skip")
    await bot._handle_skip(update, context)
    bot.music.skip.assert_called_once()


async def test_prev_command(bot):
    bot.music.previous.return_value = "Back to previous track."
    update, context = _make_update("/prev")
    await bot._handle_prev(update, context)
    bot.music.previous.assert_called_once()


async def test_np_command(bot):
    bot.music.now_playing.return_value = "Playing: Song by Artist (Album)"
    update, context = _make_update("/np")
    await bot._handle_np(update, context)
    bot.music.now_playing.assert_called_once()


async def test_vol_command(bot):
    bot.music.volume.return_value = "Volume set to 75%."
    update, context = _make_update("/vol 75", args=["75"])
    await bot._handle_vol(update, context)
    bot.music.volume.assert_called_once_with(75)


async def test_vol_no_arg(bot):
    update, context = _make_update("/vol", args=[])
    await bot._handle_vol(update, context)
    bot.music.volume.assert_not_called()
    update.message.reply_text.assert_called_once()
    assert "usage" in update.message.reply_text.call_args[0][0].lower()


async def test_playlist_command(bot):
    bot.music.play_playlist.return_value = "Now playing playlist: Chill Mix"
    update, context = _make_update("/playlist chill", args=["chill"])
    await bot._handle_playlist(update, context)
    bot.music.play_playlist.assert_called_once_with("chill")


async def test_queue_command(bot):
    bot.music.queue_track.return_value = "Added to queue: Song by Artist"
    update, context = _make_update("/queue jazz song", args=["jazz", "song"])
    await bot._handle_queue(update, context)
    bot.music.queue_track.assert_called_once_with("jazz song")


async def test_playlists_command(bot):
    bot.music.list_playlists.return_value = [
        {"name": "Playlist A", "uri": "spotify:playlist:a"},
        {"name": "Playlist B", "uri": "spotify:playlist:b"},
    ]
    update, context = _make_update("/playlists")
    await bot._handle_playlists(update, context)
    update.message.reply_text.assert_called_once()
    text = update.message.reply_text.call_args[0][0]
    assert "Playlist A" in text
    assert "Playlist B" in text


async def test_music_command_no_controller():
    bot = ClawdiaTelegramBot(
        token="test-token",
        chat_id=12345,
        brain=AsyncMock(),
    )
    update, context = _make_update("/play jazz", args=["jazz"])
    await bot._handle_play(update, context)
    assert "not configured" in update.message.reply_text.call_args[0][0].lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/vossi/local_dev/clawdia && uv run pytest tests/test_music_telegram.py -v`
Expected: FAIL — `_handle_play` does not exist, `music` not accepted.

- [ ] **Step 3: Update the Telegram bot**

Replace `src/clawdia/telegram_bot/bot.py`:

```python
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import telegram
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

if TYPE_CHECKING:
    from clawdia.brain import Brain
    from clawdia.ir import IRController
    from clawdia.music import MusicController

logger = logging.getLogger(__name__)


class ClawdiaTelegramBot:
    """Telegram bot for Clawdia - receives commands, sends notifications."""

    def __init__(
        self,
        token: str,
        chat_id: int,
        brain: Brain,
        ir: IRController | None = None,
        music: MusicController | None = None,
    ):
        self.token = token
        self.chat_id = chat_id
        self.brain = brain
        self.ir = ir
        self.music = music
        self._bot = telegram.Bot(token=token)
        self._app: Application | None = None

    async def notify(self, text: str) -> None:
        """Send a notification message to the configured chat."""
        try:
            await self._bot.send_message(chat_id=self.chat_id, text=text)
        except Exception:
            logger.exception("Failed to send Telegram notification")

    def _build_app(self) -> Application:
        """Build the Telegram application with handlers."""
        app = Application.builder().token(self.token).build()
        app.add_handler(CommandHandler("start", self._handle_start))
        app.add_handler(CommandHandler("ir", self._handle_ir_list))
        app.add_handler(CommandHandler("record", self._handle_record))
        # Music commands
        app.add_handler(CommandHandler("play", self._handle_play))
        app.add_handler(CommandHandler("pause", self._handle_pause))
        app.add_handler(CommandHandler("skip", self._handle_skip))
        app.add_handler(CommandHandler("prev", self._handle_prev))
        app.add_handler(CommandHandler("np", self._handle_np))
        app.add_handler(CommandHandler("vol", self._handle_vol))
        app.add_handler(CommandHandler("playlist", self._handle_playlist))
        app.add_handler(CommandHandler("queue", self._handle_queue))
        app.add_handler(CommandHandler("playlists", self._handle_playlists))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message))
        return app

    async def _handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command."""
        await update.message.reply_text(
            "Hi! I'm Clawdia, your home assistant.\n\n"
            "Send me a message and I'll process it.\n"
            "Use /ir to see available IR commands.\n"
            "Use /play <query> to play music."
        )

    async def _handle_ir_list(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /ir command - list available IR commands."""
        if not self.ir:
            await update.message.reply_text("IR controller not configured.")
            return
        commands = self.ir.list_commands()
        if commands:
            await update.message.reply_text("Available IR commands:\n" + "\n".join(f"• {c}" for c in commands))
        else:
            await update.message.reply_text("No IR commands recorded yet. Use /record <name> to record one.")

    async def _handle_record(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /record <name> <description> - record an IR code from the receiver."""
        if update.effective_chat.id != self.chat_id:
            await update.message.reply_text("Sorry, I only respond to my owner.")
            return

        if not self.ir:
            await update.message.reply_text("IR controller not configured.")
            return

        if not context.args:
            await update.message.reply_text(
                "Usage: /record <name> <description>\n"
                "Example: /record power Toggle TV power on/off"
            )
            return

        command = context.args[0].lower().strip()
        description = " ".join(context.args[1:]).strip() if len(context.args) > 1 else ""

        if self.ir.has_command(command):
            await update.message.reply_text(
                f"'{command}' already exists. Recording will overwrite it.\n"
                "Point your remote at the IR receiver and press the button within 10 seconds..."
            )
        else:
            await update.message.reply_text(
                f"Recording '{command}'...\n"
                "Point your remote at the IR receiver and press the button within 10 seconds..."
            )

        success = await self.ir.record(command)
        if success:
            if description:
                self.ir.set_description(command, description)
            self.brain.reload_commands()
            await update.message.reply_text(f"Recorded '{command}': {description}" if description else f"Recorded '{command}'")
        else:
            await update.message.reply_text(f"Failed to record '{command}'. Timed out or no signal received.")

    # --- Music commands ---

    async def _handle_play(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /play [query] - play a track or resume."""
        if not self.music:
            await update.message.reply_text("Music playback is not configured.")
            return
        if context.args:
            query = " ".join(context.args)
            result = await self.music.play_query(query)
        else:
            result = await self.music.play()
        await update.message.reply_text(result)

    async def _handle_pause(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /pause - pause playback."""
        if not self.music:
            await update.message.reply_text("Music playback is not configured.")
            return
        result = await self.music.pause()
        await update.message.reply_text(result)

    async def _handle_skip(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /skip - skip to next track."""
        if not self.music:
            await update.message.reply_text("Music playback is not configured.")
            return
        result = await self.music.skip()
        await update.message.reply_text(result)

    async def _handle_prev(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /prev - go to previous track."""
        if not self.music:
            await update.message.reply_text("Music playback is not configured.")
            return
        result = await self.music.previous()
        await update.message.reply_text(result)

    async def _handle_np(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /np - show now playing."""
        if not self.music:
            await update.message.reply_text("Music playback is not configured.")
            return
        result = await self.music.now_playing()
        await update.message.reply_text(result)

    async def _handle_vol(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /vol <0-100> - set volume."""
        if not self.music:
            await update.message.reply_text("Music playback is not configured.")
            return
        if not context.args:
            await update.message.reply_text("Usage: /vol <0-100>")
            return
        try:
            level = int(context.args[0])
        except ValueError:
            await update.message.reply_text("Usage: /vol <0-100>")
            return
        result = await self.music.volume(level)
        await update.message.reply_text(result)

    async def _handle_playlist(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /playlist <name> - play a playlist."""
        if not self.music:
            await update.message.reply_text("Music playback is not configured.")
            return
        if not context.args:
            await update.message.reply_text("Usage: /playlist <name>")
            return
        name = " ".join(context.args)
        result = await self.music.play_playlist(name)
        await update.message.reply_text(result)

    async def _handle_queue(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /queue <query> - add a track to the queue."""
        if not self.music:
            await update.message.reply_text("Music playback is not configured.")
            return
        if not context.args:
            await update.message.reply_text("Usage: /queue <query>")
            return
        query = " ".join(context.args)
        result = await self.music.queue_track(query)
        await update.message.reply_text(result)

    async def _handle_playlists(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /playlists - list playlists."""
        if not self.music:
            await update.message.reply_text("Music playback is not configured.")
            return
        playlists = await self.music.list_playlists()
        if playlists:
            lines = [f"• {pl['name']}" for pl in playlists]
            await update.message.reply_text("Your playlists:\n" + "\n".join(lines))
        else:
            await update.message.reply_text("No playlists found.")

    async def _handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle text messages - send to brain for processing."""
        if update.effective_chat.id != self.chat_id:
            await update.message.reply_text("Sorry, I only respond to my owner.")
            return

        text = update.message.text
        logger.info("Telegram message received: %s", text)

        try:
            response = await self.brain.process(text)
        except Exception:
            logger.exception("Error processing message")
            await update.message.reply_text("Sorry, something went wrong.")
            return

        if response.action == "ir" and response.ir and self.ir:
            if not self.ir.has_command(response.ir.command):
                await update.message.reply_text(
                    f"[IR: {response.ir.command}] not available. Record it with /record {response.ir.command}"
                )
                return

            success = await self.ir.send(
                command=response.ir.command,
                repeat=response.ir.repeat,
            )
            if success:
                await update.message.reply_text(f"[IR: {response.ir.command} x{response.ir.repeat}] {response.message}")
            else:
                await update.message.reply_text(f"[IR: {response.ir.command}] Failed to send.")

        elif response.action == "music" and response.music and self.music:
            # For brain-routed music commands, dispatch similarly to orchestrator
            from clawdia.orchestrator import MUSIC_DISPATCH
            handler = MUSIC_DISPATCH.get(response.music.command)
            if handler:
                result = await handler(self.music, response.music)
                if isinstance(result, list):
                    if not result:
                        await update.message.reply_text("No results found.")
                    else:
                        lines = [f"• {r['name']} — {r.get('artists', '')}" if 'artists' in r else f"• {r['name']}" for r in result]
                        await update.message.reply_text("\n".join(lines))
                else:
                    await update.message.reply_text(result)
            else:
                await update.message.reply_text(response.message)

        else:
            await update.message.reply_text(response.message)

    async def start(self) -> None:
        """Start the Telegram bot (non-blocking, uses polling)."""
        self._app = self._build_app()
        await self._app.initialize()
        await self._app.start()
        await self._app.updater.start_polling(allowed_updates=Update.ALL_TYPES)
        logger.info("Telegram bot started")

    async def stop(self) -> None:
        """Stop the Telegram bot."""
        if self._app:
            await self._app.updater.stop()
            await self._app.stop()
            await self._app.shutdown()
            logger.info("Telegram bot stopped")
```

- [ ] **Step 4: Run new and existing telegram tests**

Run: `cd /home/vossi/local_dev/clawdia && uv run pytest tests/test_music_telegram.py tests/test_telegram.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/clawdia/telegram_bot/bot.py tests/test_music_telegram.py
git commit -m "feat(music): add Telegram slash commands for music playback"
```

---

### Task 8: Wire MusicController into main.py and docker-compose

**Files:**
- Modify: `src/clawdia/main.py`
- Modify: `docker-compose.yml`

- [ ] **Step 1: Update main.py to initialize MusicController**

In `src/clawdia/main.py`, add the music controller initialization. After the brain initialization and before the telegram bot:

Add import at top (after other imports):

```python
from clawdia.music import MusicController
```

After the brain initialization (`brain = Brain(...)`) and before the telegram bot, add:

```python
    # Optional: Spotify music (needs client credentials)
    music = None
    if settings.spotify_client_id and settings.spotify_client_secret:
        music = MusicController(
            client_id=settings.spotify_client_id,
            client_secret=settings.spotify_client_secret,
            redirect_uri=settings.spotify_redirect_uri,
            device_name=settings.spotify_device_name,
            cache_path=settings.spotify_cache_path,
        )
        logger.info("Spotify music controller initialized (device: %s)", settings.spotify_device_name)
    else:
        logger.info("Spotify not configured (missing client credentials)")
```

Update Brain constructor to pass music:

```python
    brain = Brain(model=f"openrouter:{settings.openrouter_model}", ir=ir, music=music)
```

Update telegram bot to pass music:

```python
    telegram = ClawdiaTelegramBot(
        token=settings.telegram_bot_token,
        chat_id=settings.telegram_chat_id,
        brain=brain,
        ir=ir,
        music=music,
    )
```

Update orchestrator to pass music:

```python
    orchestrator = Orchestrator(
        brain=brain,
        ir=ir,
        telegram=telegram,
        stt=stt,
        music=music,
    )
```

The full updated `run()` function should be:

```python
async def run() -> None:
    """Main async entry point for Clawdia."""
    logging.basicConfig(
        level=logging.DEBUG if settings.debug else logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    # Prevent bot token from leaking in debug logs
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.WARNING)
    logger.info("Starting Clawdia...")

    # Initialize components
    ir = IRController(
        device_send=settings.ir_device_send,
        codes_dir=settings.ir_codes_dir,
    )

    # Optional: Spotify music (needs client credentials)
    music = None
    if settings.spotify_client_id and settings.spotify_client_secret:
        music = MusicController(
            client_id=settings.spotify_client_id,
            client_secret=settings.spotify_client_secret,
            redirect_uri=settings.spotify_redirect_uri,
            device_name=settings.spotify_device_name,
            cache_path=settings.spotify_cache_path,
        )
        logger.info("Spotify music controller initialized (device: %s)", settings.spotify_device_name)
    else:
        logger.info("Spotify not configured (missing client credentials)")

    brain = Brain(model=f"openrouter:{settings.openrouter_model}", ir=ir, music=music)

    telegram = ClawdiaTelegramBot(
        token=settings.telegram_bot_token,
        chat_id=settings.telegram_chat_id,
        brain=brain,
        ir=ir,
        music=music,
    )

    # Optional: STT (needs OpenAI API key)
    stt = None
    if settings.openai_api_key:
        from clawdia.voice.stt import SpeechToText
        stt = SpeechToText(
            api_key=settings.openai_api_key,
            model=settings.stt_model,
        )

    orchestrator = Orchestrator(
        brain=brain,
        ir=ir,
        telegram=telegram,
        stt=stt,
        music=music,
    )

    # Start services
    await telegram.start()
    await telegram.notify("Clawdia is online!")
    logger.info("Clawdia is running. Telegram bot active. Ctrl+C to stop.")

    # Optional: Start wake word listener (needs hardware)
    listener_task = None
    try:
        from clawdia.voice.listener import WakeWordListener

        async def on_wake_word():
            logger.info("Wake word detected! Capturing audio...")
            audio_data = await listener.capture_audio(duration=5.0)
            await orchestrator.handle_audio(audio_data)

        listener = WakeWordListener(
            model_path=settings.wake_word_model,
            threshold=settings.wake_word_threshold,
            sample_rate=settings.audio_sample_rate,
            chunk_size=settings.audio_chunk_size,
            on_wake_word=on_wake_word,
        )
        listener_task = asyncio.create_task(listener.start_listening())
        logger.info("Wake word listener started")
    except Exception:
        logger.info("Wake word listener not available (missing hardware/packages)")

    # Keep running until interrupted
    stop_event = asyncio.Event()

    def _signal_handler():
        stop_event.set()

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _signal_handler)

    await stop_event.wait()

    # Cleanup
    logger.info("Shutting down...")
    if listener_task:
        listener_task.cancel()
    await telegram.stop()
    logger.info("Clawdia stopped.")
```

- [ ] **Step 2: Update docker-compose.yml**

Add a volume for the Spotify cache:

```yaml
services:
  clawdia:
    build: .
    restart: unless-stopped
    env_file: .env
    devices:
      - /dev/lirc0:/dev/lirc0
      - /dev/lirc1:/dev/lirc1
      - /dev/snd:/dev/snd
    volumes:
      - ./ir-codes:/app/ir-codes
      - ./models:/app/models
      - spotify-cache:/app/.spotify_cache
      - /run/user/1000/pulse:/run/user/1000/pulse
    environment:
      - PULSE_SERVER=unix:/run/user/1000/pulse/native

volumes:
  spotify-cache:
```

- [ ] **Step 3: Run the full test suite**

Run: `cd /home/vossi/local_dev/clawdia && uv run pytest tests/ -v`
Expected: All tests PASS (new and existing).

- [ ] **Step 4: Commit**

```bash
git add src/clawdia/main.py docker-compose.yml
git commit -m "feat(music): wire MusicController into startup and docker-compose"
```

---

### Task 9: Run full test suite and final verification

- [ ] **Step 1: Run the complete test suite**

Run: `cd /home/vossi/local_dev/clawdia && uv run pytest tests/ -v --tb=short`
Expected: All tests PASS.

- [ ] **Step 2: Run ruff linter**

Run: `cd /home/vossi/local_dev/clawdia && uv run ruff check src/clawdia/music/ src/clawdia/brain/ src/clawdia/orchestrator.py src/clawdia/telegram_bot/ src/clawdia/config.py src/clawdia/main.py`
Expected: No errors.

- [ ] **Step 3: Verify import chain works**

Run: `cd /home/vossi/local_dev/clawdia && uv run python -c "from clawdia.music import MusicController; from clawdia.brain.models import MusicAction, ClawdiaResponse; print('All imports OK')"`
Expected: `All imports OK`

- [ ] **Step 4: Fix any issues found and commit**

If ruff or tests found issues, fix them and commit:

```bash
git add -u
git commit -m "fix: address linting and test issues"
```
