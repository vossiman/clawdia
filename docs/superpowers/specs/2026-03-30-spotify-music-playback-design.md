# Spotify Music Playback — Design Spec

**Date:** 2026-03-30
**Status:** Approved
**Scope:** Add Spotify playback to Clawdia via librespot + Spotify Web API

## Overview

Enable Clawdia to play music through a USB speaker attached to the Raspberry Pi. The first backend is Spotify (paid account required). The architecture is designed to support future backends (Emby, yt-dlp) but this spec covers Spotify only.

## Architecture

**librespot 0.8.0** runs on the Pi host as a systemd user service. It handles Spotify Connect and audio output to the USB speaker via rodio/ALSA. (Originally designed for spotifyd, but switched to librespot due to spotifyd 0.4.x OAuth bugs — see `docs/pi-audio-setup.md` for details.)

**Clawdia** (in Docker) controls playback through the **Spotify Web API** using the `spotipy` Python library. No direct communication between Clawdia and librespot — the Spotify cloud is the middleman.

```
Telegram/Voice → Brain (PydanticAI) → action="music" → MusicController
    → spotipy → Spotify Web API → Spotify cloud → librespot → USB speaker
```

Spotify Connect also works independently — the user can cast from their phone's Spotify app to the "clawdia" device at any time.

## Components

### New: `src/clawdia/music/`

#### `controller.py` — MusicController

Wraps spotipy. All methods return human-readable strings for Telegram responses. Internally, sync spotipy calls wrapped in `asyncio.to_thread()`.

```python
class MusicController:
    def __init__(self, client_id, client_secret, redirect_uri, device_name, cache_path):
        # Init spotipy with SpotifyOAuth, CacheFileHandler for token persistence

    # Transport
    async def play(self, uri: str | None = None) -> str
    async def pause(self) -> str
    async def skip(self) -> str
    async def previous(self) -> str
    async def volume(self, level: int) -> str           # 0-100

    # Discovery
    async def search(self, query: str, type: str = "track") -> list
    async def play_query(self, query: str) -> str       # Search + play first result
    async def play_playlist(self, name: str) -> str     # Find playlist by name + play
    async def queue_track(self, query: str) -> str      # Search + add to queue

    # Info
    async def now_playing(self) -> str | None
    async def list_playlists(self) -> list

    # Device
    async def ensure_device(self) -> bool
    async def transfer_playback(self) -> str
```

#### `__init__.py`

Exports `MusicController`.

### Modified: `brain/models.py`

Add `"music"` to the action literal and a new `MusicAction` model:

```python
class MusicAction(BaseModel):
    command: Literal[
        "play", "pause", "skip", "previous", "volume",
        "search", "play_query", "play_playlist", "queue",
        "now_playing", "list_playlists"
    ]
    query: str | None = None
    volume: int | None = None       # 0-100
```

Update `ClawdiaResponse`:

```python
class ClawdiaResponse(BaseModel):
    action: Literal["ir", "respond", "music"]
    ir: IRAction | None = None
    music: MusicAction | None = None
    message: str
```

### Modified: `brain/agent.py`

Update `build_system_prompt()` to include music capabilities. Rules:
- If the user wants to play music, search, or control playback → `action="music"`
- If the user wants device/TV control → `action="ir"`
- Otherwise → `action="respond"`

### Modified: `orchestrator.py`

Add music handling to the action routing:

```python
elif response.action == "music":
    result = await music_controller.handle(response.music)
    await telegram.send(result)
```

Inject `MusicController` at startup alongside existing IR and Telegram components.

### Modified: `telegram_bot/bot.py`

Add slash commands:

| Command | Action |
|---|---|
| `/play <query>` | Search + play top result |
| `/pause` | Pause playback |
| `/skip` | Next track |
| `/prev` | Previous track |
| `/np` | Show what's currently playing |
| `/vol <0-100>` | Set volume |
| `/playlist <name>` | Find and play a playlist |
| `/queue <query>` | Add a track to the queue |
| `/playlists` | List your playlists |

Slash commands call `MusicController` directly, bypassing the brain.

### Modified: `config.py`

Add Spotify settings:

```python
spotify_client_id: str = ""
spotify_client_secret: str = ""
spotify_redirect_uri: str = "http://127.0.0.1:8888/callback"
spotify_device_name: str = "clawdia"
spotify_cache_path: str = "/data/.spotify_cache"
```

All via environment variables, consistent with existing config pattern.

### Modified: `docker-compose.yml`

Add a volume mount for the Spotify token cache file so it persists across container restarts.

### Dependencies: `pyproject.toml`

Add `spotipy>=2.24` to dependencies.

## Pi Host Setup (One-Time)

These steps happen on the Pi directly, not in Docker:

1. **USB speaker:** Verify with `aplay -l`, identify ALSA device name
2. **spotifyd:** Download `spotifyd-linux-aarch64-full` from GitHub releases, place in `/usr/local/bin/`
3. **spotifyd config** at `~/.config/spotifyd/spotifyd.conf`:
   ```toml
   [global]
   backend = "alsa"
   device = "<from aplay -L>"
   mixer = "PCM"
   volume_controller = "alsa"
   device_name = "clawdia"
   bitrate = 160
   cache_path = "/tmp/spotifyd-cache"
   ```
4. **systemd user service:** Create, enable, start with `systemctl --user enable --now spotifyd`
5. **Spotify Developer App:** Register at developer.spotify.com, get client_id + client_secret
6. **OAuth token:** Run one-time auth flow (spotipy prints URL, user authorizes in browser, refresh token cached to disk)

## Spotify Web API OAuth

- **Flow:** Authorization Code (one-time browser auth, then refresh token forever)
- **Scopes:** `user-modify-playback-state`, `user-read-playback-state`, `user-read-currently-playing`, `playlist-read-private`, `playlist-read-collaborative`
- **Token storage:** JSON file at configured `spotify_cache_path`, auto-refreshed by spotipy

## Interaction with Existing Features

Music playback is independent — no coordination with IR, voice, or other features. Music plays in the background; all existing functionality continues to work as before. Smart pause (auto-pause during voice commands) is a future enhancement, not in scope.

## Future Backends (Out of Scope)

The `MusicController` interface is designed so that future backends (Emby, yt-dlp) can implement the same method signatures. A backend abstraction layer is not built now — YAGNI. When the second backend arrives, refactor `MusicController` into a base class or protocol.

## Testing

- Unit tests for `MusicController` with mocked spotipy client
- Unit tests for brain routing: music commands → `action="music"`
- Unit tests for Telegram slash command handlers
- Integration test: full flow from Telegram message through brain to music action
- Manual test on Pi: end-to-end with real Spotify playback

## Non-Goals

- No Emby or yt-dlp integration (future work)
- No smart pause during voice commands (future work)
- No TTS announcements of track changes
- No multi-room audio
- No playlist creation or modification from Clawdia
