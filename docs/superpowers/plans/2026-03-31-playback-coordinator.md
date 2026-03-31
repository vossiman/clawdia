# Playback Coordinator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a global PlaybackCoordinator that ensures only one audio source plays at a time and injects playback state into the brain's system prompt.

**Architecture:** A `PlaybackCoordinator` sits between command handlers and service controllers. All playback-affecting commands go through it. It stops the active source before starting a new one and tracks state for the brain's system prompt.

**Tech Stack:** Python 3.11+, asyncio, pydantic, pytest-asyncio

---

### Task 1: PlaybackCoordinator core

**Files:**
- Create: `src/clawdia/playback/__init__.py`
- Create: `src/clawdia/playback/coordinator.py`
- Create: `tests/test_playback_coordinator.py`

- [ ] **Step 1: Write failing tests for PlaybackCoordinator**

```python
# tests/test_playback_coordinator.py
from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from clawdia.playback.coordinator import PlaybackCoordinator


@pytest.fixture
def coordinator():
    return PlaybackCoordinator()


async def test_play_sets_state(coordinator):
    callback = AsyncMock(return_value="Now playing: Jazz Song by Artist")
    result = await coordinator.play(
        service="spotify:123",
        source="telegram",
        user_chat_id=123,
        callback=callback,
        description="Jazz Song by Artist",
    )
    callback.assert_called_once()
    assert result == "Now playing: Jazz Song by Artist"
    assert coordinator.state is not None
    assert coordinator.state.service == "spotify:123"
    assert coordinator.state.description == "Jazz Song by Artist"
    assert coordinator.state.source == "telegram"
    assert coordinator.state.user_chat_id == 123


async def test_play_stops_previous_service(coordinator):
    stop_a = AsyncMock()
    stop_b = AsyncMock()
    coordinator.register_service("spotify:111", stop=stop_a)
    coordinator.register_service("spotify:222", stop=stop_b)

    await coordinator.play(
        service="spotify:111",
        source="telegram",
        user_chat_id=111,
        callback=AsyncMock(return_value="Playing A"),
        description="Song A",
    )
    stop_a.assert_not_called()

    await coordinator.play(
        service="spotify:222",
        source="telegram",
        user_chat_id=222,
        callback=AsyncMock(return_value="Playing B"),
        description="Song B",
    )
    stop_a.assert_called_once()
    stop_b.assert_not_called()
    assert coordinator.state.service == "spotify:222"


async def test_play_same_service_does_not_stop(coordinator):
    stop = AsyncMock()
    coordinator.register_service("spotify:123", stop=stop)

    await coordinator.play(
        service="spotify:123",
        source="telegram",
        user_chat_id=123,
        callback=AsyncMock(return_value="Playing A"),
        description="Song A",
    )
    await coordinator.play(
        service="spotify:123",
        source="telegram",
        user_chat_id=123,
        callback=AsyncMock(return_value="Playing B"),
        description="Song B",
    )
    stop.assert_not_called()
    assert coordinator.state.description == "Song B"


async def test_stop_clears_state(coordinator):
    coordinator.register_service("spotify:123", stop=AsyncMock())
    await coordinator.play(
        service="spotify:123",
        source="telegram",
        user_chat_id=123,
        callback=AsyncMock(return_value="Playing"),
        description="Song",
    )
    await coordinator.stop("spotify:123")
    assert coordinator.state is None


async def test_stop_wrong_service_keeps_state(coordinator):
    coordinator.register_service("spotify:123", stop=AsyncMock())
    coordinator.register_service("spotify:456", stop=AsyncMock())
    await coordinator.play(
        service="spotify:123",
        source="telegram",
        user_chat_id=123,
        callback=AsyncMock(return_value="Playing"),
        description="Song",
    )
    await coordinator.stop("spotify:456")
    assert coordinator.state is not None
    assert coordinator.state.service == "spotify:123"


async def test_get_state_for_prompt_nothing(coordinator):
    result = coordinator.get_state_for_prompt()
    assert result == "Nothing is currently playing."


async def test_get_state_for_prompt_playing(coordinator):
    await coordinator.play(
        service="spotify:123",
        source="telegram",
        user_chat_id=123,
        callback=AsyncMock(return_value="Playing"),
        description="No Surprises by Radiohead",
    )
    result = coordinator.get_state_for_prompt()
    assert "No Surprises by Radiohead" in result
    assert "spotify:123" in result


async def test_stop_callback_failure_does_not_block_play(coordinator):
    stop_a = AsyncMock(side_effect=Exception("API down"))
    coordinator.register_service("spotify:111", stop=stop_a)

    await coordinator.play(
        service="spotify:111",
        source="telegram",
        user_chat_id=111,
        callback=AsyncMock(return_value="Playing A"),
        description="Song A",
    )

    callback_b = AsyncMock(return_value="Playing B")
    result = await coordinator.play(
        service="spotify:222",
        source="voice",
        user_chat_id=None,
        callback=callback_b,
        description="Song B",
    )
    callback_b.assert_called_once()
    assert result == "Playing B"
    assert coordinator.state.service == "spotify:222"


async def test_play_with_voice_source(coordinator):
    await coordinator.play(
        service="spotify:123",
        source="voice",
        user_chat_id=None,
        callback=AsyncMock(return_value="Playing"),
        description="Some song",
    )
    assert coordinator.state.source == "voice"
    assert coordinator.state.user_chat_id is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_playback_coordinator.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'clawdia.playback'`

- [ ] **Step 3: Implement PlaybackCoordinator**

```python
# src/clawdia/playback/__init__.py
from clawdia.playback.coordinator import PlaybackCoordinator

__all__ = ["PlaybackCoordinator"]
```

```python
# src/clawdia/playback/coordinator.py
from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class PlaybackState:
    source: str
    user_chat_id: int | None
    service: str
    description: str
    started_at: datetime


class PlaybackCoordinator:
    """Ensures only one audio source plays at a time."""

    def __init__(self) -> None:
        self.state: PlaybackState | None = None
        self._stop_callbacks: dict[str, Callable[[], Awaitable]] = {}

    def register_service(self, name: str, stop: Callable[[], Awaitable]) -> None:
        self._stop_callbacks[name] = stop

    async def play(
        self,
        service: str,
        source: str,
        user_chat_id: int | None,
        callback: Callable[[], Awaitable[str]],
        description: str,
    ) -> str:
        if self.state and self.state.service != service:
            await self._stop_active()

        result = await callback()
        self.state = PlaybackState(
            source=source,
            user_chat_id=user_chat_id,
            service=service,
            description=description,
            started_at=datetime.now(),
        )
        return result

    async def stop(self, service: str) -> None:
        if self.state and self.state.service == service:
            self.state = None

    async def _stop_active(self) -> None:
        if not self.state:
            return
        stop_cb = self._stop_callbacks.get(self.state.service)
        if stop_cb:
            try:
                await stop_cb()
            except Exception:
                logger.exception("Failed to stop %s", self.state.service)
        self.state = None

    def get_state_for_prompt(self) -> str:
        if not self.state:
            return "Nothing is currently playing."
        elapsed = datetime.now() - self.state.started_at
        minutes = int(elapsed.total_seconds() // 60)
        if minutes < 1:
            ago = "just now"
        elif minutes == 1:
            ago = "1 min ago"
        else:
            ago = f"{minutes} min ago"
        return f"Currently playing: {self.state.description} ({self.state.service}, since {ago})"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_playback_coordinator.py -v`
Expected: All 10 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/clawdia/playback/__init__.py src/clawdia/playback/coordinator.py tests/test_playback_coordinator.py
git commit -m "feat: add PlaybackCoordinator with tests"
```

---

### Task 2: Inject playback state into brain system prompt

**Files:**
- Modify: `src/clawdia/brain/agent.py`
- Modify: `src/clawdia/brain/__init__.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_brain_prompt.py
from unittest.mock import MagicMock

from clawdia.brain.agent import build_system_prompt


def test_system_prompt_includes_playback_state():
    ir = MagicMock()
    ir.list_commands_with_descriptions.return_value = []
    music = MagicMock()
    result = build_system_prompt(ir=ir, music=music, playback_state="Currently playing: Jazz by Miles (spotify:123, since 2 min ago)")
    assert "Currently playing: Jazz by Miles" in result


def test_system_prompt_nothing_playing():
    ir = MagicMock()
    ir.list_commands_with_descriptions.return_value = []
    music = MagicMock()
    result = build_system_prompt(ir=ir, music=music, playback_state="Nothing is currently playing.")
    assert "Nothing is currently playing." in result


def test_system_prompt_no_playback_state():
    ir = MagicMock()
    ir.list_commands_with_descriptions.return_value = []
    result = build_system_prompt(ir=ir, music=None)
    assert "Nothing is currently playing." not in result
    assert "Music playback is not currently configured." in result
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_brain_prompt.py -v`
Expected: FAIL — `build_system_prompt() got an unexpected keyword argument 'playback_state'`

- [ ] **Step 3: Add playback state to system prompt**

In `src/clawdia/brain/agent.py`, add a `{playback_state}` section to `SYSTEM_PROMPT` and update `build_system_prompt`:

Replace the `SYSTEM_PROMPT` string to add after the Music Playback section:

```python
## Current Playback State

{playback_state}
```

Update `build_system_prompt` signature and body:

```python
def build_system_prompt(
    ir: IRController,
    music: MusicController | None = None,
    playback_state: str | None = None,
) -> str:
    commands = ir.list_commands_with_descriptions()
    if commands:
        lines = [f"- {name}: {desc}" if desc else f"- {name}" for name, desc in commands]
        ir_commands = "\n".join(lines)
    else:
        ir_commands = "No IR commands recorded yet."

    music_section = MUSIC_ENABLED if music else MUSIC_DISABLED
    ps = playback_state if playback_state else ""

    return SYSTEM_PROMPT.format(
        ir_commands=ir_commands,
        music_section=music_section,
        playback_state=ps,
    )
```

Update `create_agent` to accept and pass through `playback_state`:

```python
def create_agent(
    model: str = "openrouter:anthropic/claude-haiku-4.5",
    ir: IRController | None = None,
    music: MusicController | None = None,
    playback_state: str | None = None,
) -> Agent:
    if ir:
        prompt = build_system_prompt(ir=ir, music=music, playback_state=playback_state)
    else:
        prompt = SYSTEM_PROMPT.format(
            ir_commands="No IR commands recorded yet.",
            music_section=MUSIC_ENABLED if music else MUSIC_DISABLED,
            playback_state=playback_state or "",
        )
    return Agent(
        model,
        output_type=ClawdiaResponse,
        instructions=prompt,
    )
```

- [ ] **Step 4: Update Brain to accept coordinator and rebuild prompt per message**

In `src/clawdia/brain/__init__.py`:

```python
from __future__ import annotations

from typing import TYPE_CHECKING

from clawdia.brain.agent import create_agent
from clawdia.brain.models import ClawdiaResponse

if TYPE_CHECKING:
    from clawdia.ir import IRController
    from clawdia.music import MusicController
    from clawdia.playback import PlaybackCoordinator


class Brain:
    """High-level interface to the Clawdia intent engine."""

    def __init__(
        self,
        model: str = "openrouter:anthropic/claude-haiku-4.5",
        ir: IRController | None = None,
        music: MusicController | None = None,
        coordinator: PlaybackCoordinator | None = None,
    ):
        self._model = model
        self._ir = ir
        self._music = music
        self._coordinator = coordinator
        self.agent = create_agent(model=model, ir=ir, music=music)

    def reload_commands(self) -> None:
        """Rebuild the agent with current IR commands."""
        self.agent = create_agent(model=self._model, ir=self._ir, music=self._music)

    async def process(self, text: str) -> ClawdiaResponse:
        """Process a text command and return a structured response."""
        playback_state = self._coordinator.get_state_for_prompt() if self._coordinator else None
        agent = create_agent(
            model=self._model,
            ir=self._ir,
            music=self._music,
            playback_state=playback_state,
        )
        result = await agent.run(text)
        return result.output
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_brain_prompt.py tests/test_brain.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/clawdia/brain/agent.py src/clawdia/brain/__init__.py tests/test_brain_prompt.py
git commit -m "feat: inject playback state into brain system prompt"
```

---

### Task 3: Wire coordinator into main.py

**Files:**
- Modify: `src/clawdia/main.py`

- [ ] **Step 1: Update main.py to create coordinator and register services**

In `src/clawdia/main.py`, add after the music controllers block (after line 74) and before the Brain creation (line 76):

```python
    from clawdia.playback import PlaybackCoordinator
    coordinator = PlaybackCoordinator()
    for chat_id, mc in music_controllers.items():
        coordinator.register_service(f"spotify:{chat_id}", stop=mc.pause)
        logger.info("Registered playback service spotify:%d", chat_id)
    if music and not music_controllers:
        coordinator.register_service("spotify:default", stop=music.pause)
```

Update the Brain creation to pass the coordinator:

```python
    brain = Brain(model=f"openrouter:{settings.openrouter_model}", ir=ir, music=music, coordinator=coordinator)
```

Update the ClawdiaTelegramBot creation to pass the coordinator:

```python
    telegram = ClawdiaTelegramBot(
        token=settings.telegram_bot_token,
        chat_ids=chat_ids,
        brain=brain,
        ir=ir,
        music=music,
        music_controllers=music_controllers or None,
        coordinator=coordinator,
    )
```

Update the Orchestrator creation to pass the coordinator:

```python
    orchestrator = Orchestrator(
        brain=brain,
        ir=ir,
        telegram=telegram,
        stt=stt,
        music=music,
        coordinator=coordinator,
    )
```

- [ ] **Step 2: Verify imports work**

Run: `uv run python -c "from clawdia.main import main; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add src/clawdia/main.py
git commit -m "feat: wire PlaybackCoordinator into main startup"
```

---

### Task 4: Route telegram bot commands through coordinator

**Files:**
- Modify: `src/clawdia/telegram_bot/bot.py`
- Modify: `tests/test_music_telegram.py`

- [ ] **Step 1: Write failing test for coordinator routing**

Add to `tests/test_music_telegram.py`:

```python
async def test_play_routes_through_coordinator():
    music = AsyncMock()
    music.play_query.return_value = "Now playing: Song by Artist"

    from clawdia.playback import PlaybackCoordinator
    coordinator = PlaybackCoordinator()
    coordinator.register_service("spotify:12345", stop=music.pause)

    bot = ClawdiaTelegramBot(
        token="test-token",
        chat_ids={12345},
        brain=AsyncMock(),
        music=music,
        music_controllers={12345: music},
        coordinator=coordinator,
    )

    update, context = _make_update("/play jazz", chat_id=12345, args=["jazz"])
    await bot._handle_play(update, context)
    music.play_query.assert_called_once_with("jazz")
    assert coordinator.state is not None
    assert coordinator.state.service == "spotify:12345"


async def test_pause_clears_coordinator_state():
    music = AsyncMock()
    music.play_query.return_value = "Now playing: Song"
    music.pause.return_value = "Paused."

    from clawdia.playback import PlaybackCoordinator
    coordinator = PlaybackCoordinator()
    coordinator.register_service("spotify:12345", stop=music.pause)

    bot = ClawdiaTelegramBot(
        token="test-token",
        chat_ids={12345},
        brain=AsyncMock(),
        music=music,
        music_controllers={12345: music},
        coordinator=coordinator,
    )

    update_play, ctx_play = _make_update("/play jazz", chat_id=12345, args=["jazz"])
    await bot._handle_play(update_play, ctx_play)
    assert coordinator.state is not None

    update_pause, ctx_pause = _make_update("/pause", chat_id=12345)
    await bot._handle_pause(update_pause, ctx_pause)
    assert coordinator.state is None


async def test_play_stops_other_users_playback():
    music_a = AsyncMock()
    music_b = AsyncMock()
    music_a.play_query.return_value = "Playing A"
    music_b.play_query.return_value = "Playing B"

    from clawdia.playback import PlaybackCoordinator
    coordinator = PlaybackCoordinator()
    coordinator.register_service("spotify:111", stop=music_a.pause)
    coordinator.register_service("spotify:222", stop=music_b.pause)

    bot = ClawdiaTelegramBot(
        token="test-token",
        chat_ids={111, 222},
        brain=AsyncMock(),
        music_controllers={111: music_a, 222: music_b},
        coordinator=coordinator,
    )

    update_a, ctx_a = _make_update("/play jazz", chat_id=111, args=["jazz"])
    await bot._handle_play(update_a, ctx_a)
    assert coordinator.state.service == "spotify:111"

    update_b, ctx_b = _make_update("/play rock", chat_id=222, args=["rock"])
    await bot._handle_play(update_b, ctx_b)
    music_a.pause.assert_called_once()
    assert coordinator.state.service == "spotify:222"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_music_telegram.py::test_play_routes_through_coordinator -v`
Expected: FAIL — `ClawdiaTelegramBot() got an unexpected keyword argument 'coordinator'`

- [ ] **Step 3: Update bot constructor and playback handlers**

In `src/clawdia/telegram_bot/bot.py`, update `__init__` to accept `coordinator`:

Add to the TYPE_CHECKING imports:
```python
    from clawdia.playback import PlaybackCoordinator
```

Update `__init__` signature to add `coordinator: PlaybackCoordinator | None = None` and store it as `self.coordinator = coordinator`.

Update `_handle_play`:
```python
    async def _handle_play(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /play [query] - play music or search and play a track."""
        music = self._get_music(update.effective_chat.id)
        if not music:
            await update.message.reply_text("Music playback is not configured.")
            return
        chat_id = update.effective_chat.id
        if context.args:
            query = " ".join(context.args)
            if self.coordinator:
                result = await self.coordinator.play(
                    service=f"spotify:{chat_id}",
                    source="telegram",
                    user_chat_id=chat_id,
                    callback=lambda: music.play_query(query),
                    description=query,
                )
            else:
                result = await music.play_query(query)
        else:
            if self.coordinator:
                result = await self.coordinator.play(
                    service=f"spotify:{chat_id}",
                    source="telegram",
                    user_chat_id=chat_id,
                    callback=lambda: music.play(),
                    description="Resumed playback",
                )
            else:
                result = await music.play()
        await update.message.reply_text(result)
```

Update `_handle_pause`:
```python
    async def _handle_pause(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /pause - pause playback."""
        music = self._get_music(update.effective_chat.id)
        if not music:
            await update.message.reply_text("Music playback is not configured.")
            return
        result = await music.pause()
        if self.coordinator:
            await self.coordinator.stop(f"spotify:{update.effective_chat.id}")
        await update.message.reply_text(result)
```

Update `_handle_skip`:
```python
    async def _handle_skip(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /skip - skip to next track."""
        music = self._get_music(update.effective_chat.id)
        if not music:
            await update.message.reply_text("Music playback is not configured.")
            return
        result = await music.skip()
        await update.message.reply_text(result)
```

Update `_handle_prev` — same pattern as skip (no coordinator change, just pass through).

Update `_handle_playlist`:
```python
    async def _handle_playlist(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /playlist <name> - play a playlist by name."""
        music = self._get_music(update.effective_chat.id)
        if not music:
            await update.message.reply_text("Music playback is not configured.")
            return
        if not context.args:
            await update.message.reply_text("Usage: /playlist <name>\nExample: /playlist chill")
            return
        name = " ".join(context.args)
        chat_id = update.effective_chat.id
        if self.coordinator:
            result = await self.coordinator.play(
                service=f"spotify:{chat_id}",
                source="telegram",
                user_chat_id=chat_id,
                callback=lambda: music.play_playlist(name),
                description=f"playlist: {name}",
            )
        else:
            result = await music.play_playlist(name)
        await update.message.reply_text(result)
```

Update `_handle_queue`:
```python
    async def _handle_queue(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /queue <query> - add a track to the queue."""
        music = self._get_music(update.effective_chat.id)
        if not music:
            await update.message.reply_text("Music playback is not configured.")
            return
        if not context.args:
            await update.message.reply_text("Usage: /queue <query>\nExample: /queue jazz classics")
            return
        query = " ".join(context.args)
        result = await music.queue_track(query)
        await update.message.reply_text(result)
```

`_handle_np`, `_handle_vol`, `_handle_playlists` — no changes, read-only.

Update the `_handle_message` music dispatch block (around line 297) to route through coordinator:
```python
        elif response.action == "music" and response.music:
            music = self._get_music(update.effective_chat.id)
            if not music:
                await update.message.reply_text("Music playback is not configured.")
                return
            from clawdia.orchestrator import MUSIC_DISPATCH
            handler = MUSIC_DISPATCH.get(response.music.command)
            if not handler:
                await update.message.reply_text(f"Unknown music command: {response.music.command}")
                return
            chat_id = update.effective_chat.id
            is_playback_cmd = response.music.command in ("play", "play_query", "play_playlist")
            if self.coordinator and is_playback_cmd:
                result = await self.coordinator.play(
                    service=f"spotify:{chat_id}",
                    source="telegram",
                    user_chat_id=chat_id,
                    callback=lambda: handler(music, response.music),
                    description=response.music.query or "music",
                )
            elif self.coordinator and response.music.command == "pause":
                result = await handler(music, response.music)
                await self.coordinator.stop(f"spotify:{chat_id}")
            else:
                result = await handler(music, response.music)
            if isinstance(result, list):
                if not result:
                    await update.message.reply_text("No results found.")
                else:
                    lines = [
                        f"• {r['name']} — {r.get('artists', '')}" if "artists" in r else f"• {r['name']}"
                        for r in result
                    ]
                    await update.message.reply_text("\n".join(lines))
            else:
                await update.message.reply_text(result)
```

- [ ] **Step 4: Update existing bot tests to pass coordinator**

Update the `bot` fixture in `tests/test_music_telegram.py` — add `coordinator=None` to the existing fixture (it should still work without a coordinator for backward compat).

- [ ] **Step 5: Run all tests**

Run: `uv run pytest -x -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/clawdia/telegram_bot/bot.py tests/test_music_telegram.py
git commit -m "feat: route telegram music commands through PlaybackCoordinator"
```

---

### Task 5: Route orchestrator through coordinator

**Files:**
- Modify: `src/clawdia/orchestrator.py`

- [ ] **Step 1: Update Orchestrator to accept and use coordinator**

```python
# src/clawdia/orchestrator.py — updated __init__ and _handle_music

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from clawdia.brain import Brain
    from clawdia.brain.models import MusicAction
    from clawdia.ir import IRController
    from clawdia.music import MusicController
    from clawdia.playback import PlaybackCoordinator
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
    """Coordinates the full Clawdia pipeline."""

    def __init__(
        self,
        brain: Brain,
        ir: IRController,
        telegram: ClawdiaTelegramBot,
        stt: SpeechToText | None = None,
        music: MusicController | None = None,
        coordinator: PlaybackCoordinator | None = None,
    ):
        self.brain = brain
        self.ir = ir
        self.telegram = telegram
        self.stt = stt
        self.music = music
        self.coordinator = coordinator

    async def _handle_music(self, action: MusicAction) -> str:
        """Dispatch a music action to the controller."""
        if not self.music:
            return "Music playback is not configured."
        handler = MUSIC_DISPATCH.get(action.command)
        if not handler:
            return f"Unknown music command: {action.command}"
        is_playback_cmd = action.command in ("play", "play_query", "play_playlist")
        if self.coordinator and is_playback_cmd:
            result = await self.coordinator.play(
                service="spotify:default",
                source="voice",
                user_chat_id=None,
                callback=lambda: handler(self.music, action),
                description=action.query or "music",
            )
        elif self.coordinator and action.command == "pause":
            result = await handler(self.music, action)
            await self.coordinator.stop("spotify:default")
        else:
            result = await handler(self.music, action)
        if isinstance(result, list):
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

- [ ] **Step 2: Run all tests**

Run: `uv run pytest -x -v`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add src/clawdia/orchestrator.py
git commit -m "feat: route orchestrator music actions through PlaybackCoordinator"
```

---

### Task 6: Run full test suite and final commit

- [ ] **Step 1: Run full test suite**

Run: `uv run pytest -v`
Expected: All tests PASS

- [ ] **Step 2: Verify imports and startup**

Run: `uv run python -c "from clawdia.playback import PlaybackCoordinator; from clawdia.main import main; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Final commit if any remaining changes**

```bash
git status
# If clean, nothing to commit
# If changes remain, add and commit
```
