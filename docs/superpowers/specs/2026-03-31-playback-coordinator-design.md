# Playback Coordinator

## Problem

Clawdia controls a single speaker in a shared living room. Multiple audio sources exist (per-user Spotify, future: web radio, Emby). When someone starts playing something, any other active playback should stop automatically. The brain (LLM) should also be aware of what's currently playing so it can reason about it in conversation.

## Design

### PlaybackState

```python
@dataclass
class PlaybackState:
    source: str              # "telegram", "voice", "web"
    user_chat_id: int | None # set for telegram, None for voice
    service: str             # "spotify:4380413", "webradio", "emby"
    description: str         # "No Surprises by Radiohead"
    started_at: datetime
```

`None` means nothing is playing.

### PlaybackCoordinator

```python
class PlaybackCoordinator:
    state: PlaybackState | None

    def register_service(name: str, stop: Callable) -> None
    async def play(service: str, source: str, user_chat_id: int | None, callback: Callable, description: str) -> str
    async def stop(service: str) -> None
    def get_state_for_prompt() -> str
```

**`register_service(name, stop)`** — register a stoppable audio source. `stop` is an async callable that pauses/stops that service.

**`play(service, source, user_chat_id, callback, description)`** — the main entry point for any playback action:
1. If another service is currently active, call its registered `stop` callback
2. Call `callback()` — the actual play action (e.g. `music.play_query("jazz")`)
3. Update `self.state` with the new playback info. `description` is provided by the caller — for slash commands this is the query string, for brain-routed commands it can be extracted from the result.
4. Return the callback's result

**`stop(service)`** — stop a specific service and clear state if it was the active one.

**`get_state_for_prompt()`** — returns a human-readable string for the brain's system prompt:
- `"Currently playing: No Surprises by Radiohead (Gernot's Spotify, since 2 min ago)"`
- `"Nothing is currently playing."`

### Service registration

At startup in `main.py`, after creating music controllers:

```python
coordinator = PlaybackCoordinator()
for chat_id, mc in music_controllers.items():
    coordinator.register_service(f"spotify:{chat_id}", stop=mc.pause)
```

Future services register the same way with their own stop callbacks.

### Integration: Telegram bot

Slash commands that affect playback go through the coordinator instead of calling the controller directly. Read-only commands (`/np`, `/playlists`) do not.

Commands routed through coordinator: `/play`, `/pause`, `/skip`, `/prev`, `/playlist`, `/queue`
Commands that bypass coordinator: `/np`, `/vol`, `/playlists`

Example for `/play`:
```python
music = self._get_music(chat_id)
result = await self.coordinator.play(
    service=f"spotify:{chat_id}",
    source="telegram",
    user_chat_id=chat_id,
    callback=lambda: music.play_query(query),
    description=query,  # updated after callback with actual track name
)
```

### Integration: Brain system prompt

In `brain/agent.py`, the system prompt includes the coordinator's state:

```
Current playback: No Surprises by Radiohead (Gernot's Spotify, since 2 min ago)
```

This lets the brain reason naturally: "pausing Oxana's music to play your request", or answer "what's playing?" without calling the Spotify API.

The brain's system prompt is built at process-time (each message), so it always reflects current state.

### Integration: Orchestrator

The orchestrator's `_handle_music` method routes through the coordinator for the voice/wake-word path, same as the telegram bot does for slash commands.

### What the coordinator does NOT do

- No queue management — that's the service's job
- No volume control — separate concern
- No playback history beyond current state
- No persistence — state is in-memory, resets on restart
- No user confirmation before interrupting — last command wins

## Files

| File | Change |
|------|--------|
| `src/clawdia/playback/__init__.py` | New — exports PlaybackCoordinator |
| `src/clawdia/playback/coordinator.py` | New — PlaybackCoordinator + PlaybackState |
| `src/clawdia/brain/agent.py` | Inject playback state into system prompt |
| `src/clawdia/main.py` | Create coordinator, register services, pass to components |
| `src/clawdia/telegram_bot/bot.py` | Route playback commands through coordinator |
| `src/clawdia/orchestrator.py` | Route music actions through coordinator |
| `tests/test_playback_coordinator.py` | New — unit tests for coordinator |

## Edge cases

- **Rapid successive commands**: Second play arrives while first is still starting. The coordinator is single-threaded (asyncio), so commands are serialized naturally.
- **Service crashes**: If a stop callback fails (e.g. Spotify API down), log the error and proceed with the new playback anyway. Don't let a broken service block the new one.
- **Pause vs stop**: `/pause` goes through the coordinator to clear the active state. Resuming with `/play` (no query) sets it again.
- **Skip/prev**: These don't change the active service, but the description should update. The coordinator can update the description after the callback returns.
