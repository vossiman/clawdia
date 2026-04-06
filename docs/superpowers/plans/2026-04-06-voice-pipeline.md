# Voice Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring the existing wake word + STT code to life on the Pi, add TTS output, and wire voice responses to both Telegram and speaker.

**Architecture:** Voice input flows through the existing `WakeWordListener` → `SpeechToText` → `Orchestrator.handle_text_command()` pipeline. New `TextToSpeech` and `AudioPlayer` classes handle output. The orchestrator stays source-agnostic — a `reply` callback from `main.py` routes responses to TTS and/or Telegram based on config flags. Spotify is paused during TTS playback.

**Tech Stack:** OpenAI TTS API (`tts-1`), OpenAI Whisper API (existing), openWakeWord (existing), PulseAudio (`paplay`), pyaudio (existing)

**Spec:** `docs/superpowers/specs/2026-04-06-voice-pipeline-design.md`

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `src/clawdia/voice/tts.py` | OpenAI TTS synthesis |
| Create | `src/clawdia/voice/player.py` | Audio playback via `paplay` |
| Create | `src/clawdia/voice/sounds/chime.wav` | Wake word acknowledgment sound |
| Create | `src/clawdia/voice/sounds/error.wav` | Error notification sound |
| Create | `tests/test_tts.py` | TTS unit tests |
| Create | `tests/test_player.py` | AudioPlayer unit tests |
| Create | `tests/test_voice_pipeline.py` | Voice reply callback + pipeline tests |
| Modify | `src/clawdia/config.py:24-28` | Add TTS and voice response settings |
| Modify | `src/clawdia/orchestrator.py:261-274` | Improve `handle_audio()` error handling |
| Modify | `src/clawdia/main.py:184-204` | Rewire `on_wake_word` with chime, TTS reply, ducking |
| Modify | `tests/test_config.py` | Add tests for new settings |

---

### Task 1: Add TTS and Voice Response Config Settings

**Files:**
- Modify: `src/clawdia/config.py:24-28`
- Modify: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_config.py`:

```python
def test_voice_response_settings():
    s = Settings(
        openrouter_api_key="k",
        telegram_bot_token="t",
        telegram_chat_ids="1",
    )
    assert s.tts_model == "tts-1"
    assert s.tts_voice == "alloy"
    assert s.voice_response_telegram is True
    assert s.voice_response_tts is True
    assert s.voice_context_id == "voice"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_config.py::test_voice_response_settings -v`
Expected: FAIL — `Settings` has no field `tts_model`

- [ ] **Step 3: Add new settings to config.py**

Add after the existing voice settings block (line 28) in `src/clawdia/config.py`:

```python
    # TTS
    tts_model: str = "tts-1"
    tts_voice: str = "alloy"

    # Voice response routing
    voice_response_telegram: bool = True
    voice_response_tts: bool = True
    voice_context_id: str = "voice"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_config.py::test_voice_response_settings -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/clawdia/config.py tests/test_config.py
git commit -m "feat: add TTS and voice response config settings"
```

---

### Task 2: Create TextToSpeech Class

**Files:**
- Create: `src/clawdia/voice/tts.py`
- Create: `tests/test_tts.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_tts.py`:

```python
from unittest.mock import AsyncMock, MagicMock, patch

from clawdia.voice.tts import TextToSpeech


async def test_synthesize():
    mock_audio_data = b"fake-mp3-data"

    with patch("clawdia.voice.tts.openai.AsyncOpenAI") as MockClient:
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_response.read = AsyncMock(return_value=mock_audio_data)
        mock_client.audio.speech.create = AsyncMock(return_value=mock_response)
        MockClient.return_value = mock_client

        tts = TextToSpeech(api_key="test-key")
        result = await tts.synthesize("Hello world")

        assert result == mock_audio_data
        mock_client.audio.speech.create.assert_called_once_with(
            model="tts-1",
            voice="alloy",
            input="Hello world",
            response_format="wav",
        )


async def test_synthesize_custom_voice():
    with patch("clawdia.voice.tts.openai.AsyncOpenAI") as MockClient:
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_response.read = AsyncMock(return_value=b"data")
        mock_client.audio.speech.create = AsyncMock(return_value=mock_response)
        MockClient.return_value = mock_client

        tts = TextToSpeech(api_key="test-key", model="tts-1-hd", voice="nova")
        await tts.synthesize("Hi")

        call_kwargs = mock_client.audio.speech.create.call_args[1]
        assert call_kwargs["model"] == "tts-1-hd"
        assert call_kwargs["voice"] == "nova"


async def test_synthesize_failure_returns_empty():
    with patch("clawdia.voice.tts.openai.AsyncOpenAI") as MockClient:
        mock_client = AsyncMock()
        mock_client.audio.speech.create = AsyncMock(side_effect=Exception("API error"))
        MockClient.return_value = mock_client

        tts = TextToSpeech(api_key="test-key")
        result = await tts.synthesize("Hello")
        assert result == b""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_tts.py -v`
Expected: FAIL — `clawdia.voice.tts` has no `TextToSpeech`

- [ ] **Step 3: Create the TextToSpeech class**

Create `src/clawdia/voice/tts.py`:

```python
from __future__ import annotations

import openai
from loguru import logger


class TextToSpeech:
    """Synthesize speech using OpenAI TTS API."""

    def __init__(self, api_key: str, model: str = "tts-1", voice: str = "alloy"):
        self.model = model
        self.voice = voice
        self._client = openai.AsyncOpenAI(api_key=api_key)

    async def synthesize(self, text: str) -> bytes:
        """Convert text to audio bytes (WAV format)."""
        try:
            response = await self._client.audio.speech.create(
                model=self.model,
                voice=self.voice,
                input=text,
                response_format="wav",
            )
            audio_data = await response.read()
            logger.info("TTS synthesized {} bytes for: '{}'", len(audio_data), text[:50])
            return audio_data
        except Exception:
            logger.exception("TTS synthesis failed")
            return b""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_tts.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add src/clawdia/voice/tts.py tests/test_tts.py
git commit -m "feat: add TextToSpeech class using OpenAI TTS API"
```

---

### Task 3: Create AudioPlayer Class

**Files:**
- Create: `src/clawdia/voice/player.py`
- Create: `tests/test_player.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_player.py`:

```python
import asyncio
from unittest.mock import AsyncMock, patch, call

import pytest

from clawdia.voice.player import AudioPlayer


@pytest.fixture
def player():
    return AudioPlayer()


async def test_play_file(player):
    with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
        mock_proc = AsyncMock()
        mock_proc.wait = AsyncMock(return_value=0)
        mock_proc.returncode = 0
        mock_exec.return_value = mock_proc

        await player.play_file("/path/to/chime.wav")

        mock_exec.assert_called_once_with(
            "paplay", "/path/to/chime.wav",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )


async def test_play_bytes_writes_temp_and_plays(player):
    with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec, \
         patch("tempfile.NamedTemporaryFile") as mock_tmp:
        mock_proc = AsyncMock()
        mock_proc.wait = AsyncMock(return_value=0)
        mock_proc.returncode = 0
        mock_exec.return_value = mock_proc

        mock_file = mock_tmp.return_value.__enter__.return_value
        mock_file.name = "/tmp/clawdia_tts.wav"

        await player.play_bytes(b"fake-wav-data", suffix=".wav")

        mock_file.write.assert_called_once_with(b"fake-wav-data")
        mock_file.flush.assert_called_once()
        mock_exec.assert_called_once_with(
            "paplay", "/tmp/clawdia_tts.wav",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )


async def test_play_file_logs_on_failure(player):
    with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
        mock_proc = AsyncMock()
        mock_proc.wait = AsyncMock(return_value=1)
        mock_proc.returncode = 1
        mock_exec.return_value = mock_proc

        # Should not raise, just log
        await player.play_file("/path/to/missing.wav")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_player.py -v`
Expected: FAIL — `clawdia.voice.player` does not exist

- [ ] **Step 3: Create the AudioPlayer class**

Create `src/clawdia/voice/player.py`:

```python
from __future__ import annotations

import asyncio
import tempfile

from loguru import logger


class AudioPlayer:
    """Play audio through PulseAudio using paplay."""

    async def play_file(self, path: str) -> None:
        """Play a WAV file through the default PulseAudio sink."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "paplay", path,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.wait()
            if proc.returncode != 0:
                logger.warning("paplay exited with code {} for {}", proc.returncode, path)
        except Exception:
            logger.exception("Failed to play audio file: {}", path)

    async def play_bytes(self, data: bytes, suffix: str = ".wav") -> None:
        """Write audio bytes to a temp file and play it."""
        try:
            with tempfile.NamedTemporaryFile(suffix=suffix, prefix="clawdia_tts") as f:
                f.write(data)
                f.flush()
                await self.play_file(f.name)
        except Exception:
            logger.exception("Failed to play audio bytes")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_player.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add src/clawdia/voice/player.py tests/test_player.py
git commit -m "feat: add AudioPlayer class for PulseAudio playback"
```

---

### Task 4: Generate Chime and Error Sound Assets

**Files:**
- Create: `src/clawdia/voice/sounds/chime.wav`
- Create: `src/clawdia/voice/sounds/error.wav`

- [ ] **Step 1: Generate chime.wav**

Use Python to generate a short pleasant chime tone (440Hz sine wave, 0.3s, with fade):

```bash
uv run python -c "
import wave, struct, math
sr = 16000
dur = 0.3
samples = []
for i in range(int(sr * dur)):
    t = i / sr
    fade = min(t / 0.01, 1.0) * max(0, 1.0 - (t - dur + 0.05) / 0.05)
    sample = int(fade * 16000 * math.sin(2 * math.pi * 880 * t))
    samples.append(struct.pack('<h', max(-32768, min(32767, sample))))
with wave.open('src/clawdia/voice/sounds/chime.wav', 'wb') as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
    w.writeframes(b''.join(samples))
print('chime.wav created')
"
```

- [ ] **Step 2: Generate error.wav**

Use Python to generate a short descending error tone (two-tone, 0.4s):

```bash
uv run python -c "
import wave, struct, math
sr = 16000
dur = 0.4
samples = []
for i in range(int(sr * dur)):
    t = i / sr
    freq = 440 if t < dur / 2 else 330
    fade = min(t / 0.01, 1.0) * max(0, 1.0 - (t - dur + 0.05) / 0.05)
    sample = int(fade * 12000 * math.sin(2 * math.pi * freq * t))
    samples.append(struct.pack('<h', max(-32768, min(32767, sample))))
with wave.open('src/clawdia/voice/sounds/error.wav', 'wb') as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
    w.writeframes(b''.join(samples))
print('error.wav created')
"
```

- [ ] **Step 3: Verify files exist and are valid WAV**

```bash
uv run python -c "
import wave
for f in ['src/clawdia/voice/sounds/chime.wav', 'src/clawdia/voice/sounds/error.wav']:
    with wave.open(f) as w:
        print(f'{f}: {w.getnchannels()}ch, {w.getframerate()}Hz, {w.getnframes()} frames')
"
```

Expected: Both files exist, mono, 16000Hz.

- [ ] **Step 4: Commit**

```bash
git add src/clawdia/voice/sounds/chime.wav src/clawdia/voice/sounds/error.wav
git commit -m "feat: add chime and error sound assets for voice pipeline"
```

---

### Task 5: Improve handle_audio() Error Handling

**Files:**
- Modify: `src/clawdia/orchestrator.py:261-274`
- Modify: `tests/test_orchestrator.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_orchestrator.py`:

```python
async def test_handle_audio_calls_stt_and_routes(orchestrator, mock_brain, mock_telegram):
    """Test that handle_audio transcribes and routes to handle_text_command."""
    mock_stt = AsyncMock()
    mock_stt.pcm_to_wav.return_value = b"wav-data"
    mock_stt.transcribe = AsyncMock(return_value="play some jazz")
    orchestrator.stt = mock_stt

    response = ClawdiaResponse(action="respond", message="Playing jazz")
    mock_brain.process.return_value = response

    await orchestrator.handle_audio(b"pcm-data")

    mock_stt.pcm_to_wav.assert_called_once_with(b"pcm-data")
    mock_stt.transcribe.assert_called_once_with(b"wav-data")
    mock_brain.process.assert_called_once()


async def test_handle_audio_empty_transcript_calls_on_error(orchestrator):
    """Test that empty STT triggers on_error callback."""
    mock_stt = AsyncMock()
    mock_stt.pcm_to_wav.return_value = b"wav-data"
    mock_stt.transcribe = AsyncMock(return_value="")
    orchestrator.stt = mock_stt

    on_error = AsyncMock()
    await orchestrator.handle_audio(b"pcm-data", on_error=on_error)

    on_error.assert_called_once()


async def test_handle_audio_stt_exception_calls_on_error(orchestrator):
    """Test that STT failure triggers on_error callback."""
    mock_stt = AsyncMock()
    mock_stt.pcm_to_wav.return_value = b"wav-data"
    mock_stt.transcribe = AsyncMock(side_effect=Exception("API timeout"))
    orchestrator.stt = mock_stt

    on_error = AsyncMock()
    await orchestrator.handle_audio(b"pcm-data", on_error=on_error)

    on_error.assert_called_once()


async def test_handle_audio_no_stt(orchestrator):
    """Test that handle_audio is a no-op without STT configured."""
    orchestrator.stt = None
    await orchestrator.handle_audio(b"pcm-data")
    # Should not raise
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_orchestrator.py::test_handle_audio_calls_stt_and_routes tests/test_orchestrator.py::test_handle_audio_empty_transcript_calls_on_error tests/test_orchestrator.py::test_handle_audio_stt_exception_calls_on_error tests/test_orchestrator.py::test_handle_audio_no_stt -v`
Expected: FAIL — `handle_audio()` doesn't accept `on_error` parameter

- [ ] **Step 3: Update handle_audio in orchestrator.py**

Replace the `handle_audio` method (lines 261-274) in `src/clawdia/orchestrator.py`:

```python
    async def handle_audio(
        self,
        pcm_data: bytes,
        *,
        reply: Callable[[str], Awaitable[None]] | None = None,
        context_id: str = "default",
        source: str = "voice",
        on_error: Callable[[], Awaitable[None]] | None = None,
    ) -> None:
        """Process captured audio through STT -> brain -> action."""
        if self.stt is None:
            logger.error("STT not configured")
            return

        wav_data = self.stt.pcm_to_wav(pcm_data)

        try:
            text = await self.stt.transcribe(wav_data)
        except Exception:
            logger.exception("STT transcription failed")
            if on_error:
                await on_error()
            return

        if not text:
            logger.info("STT returned empty transcript, ignoring")
            if on_error:
                await on_error()
            return

        await self.handle_text_command(
            text, reply=reply, context_id=context_id, source=source,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_orchestrator.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/clawdia/orchestrator.py tests/test_orchestrator.py
git commit -m "feat: add on_error callback and reply passthrough to handle_audio"
```

---

### Task 6: Wire Voice Pipeline in main.py

**Files:**
- Modify: `src/clawdia/main.py:184-204`
- Create: `tests/test_voice_pipeline.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_voice_pipeline.py`:

```python
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


async def test_voice_reply_sends_to_telegram_when_enabled():
    """Test that voice_reply sends to Telegram when voice_response_telegram is True."""
    from clawdia.voice.tts import TextToSpeech
    from clawdia.voice.player import AudioPlayer

    telegram = AsyncMock()
    tts = AsyncMock(spec=TextToSpeech)
    player = AsyncMock(spec=AudioPlayer)
    music = AsyncMock()

    tts.synthesize = AsyncMock(return_value=b"audio-data")

    # Import the helper we'll create
    from clawdia.voice.pipeline import make_voice_reply

    reply = make_voice_reply(
        telegram=telegram,
        tts=tts,
        player=player,
        music=music,
        response_telegram=True,
        response_tts=False,
    )
    await reply("Hello there")

    telegram.notify.assert_called_once_with("🎙 Hello there")
    tts.synthesize.assert_not_called()


async def test_voice_reply_speaks_when_enabled():
    """Test that voice_reply synthesizes and plays TTS when voice_response_tts is True."""
    from clawdia.voice.tts import TextToSpeech
    from clawdia.voice.player import AudioPlayer

    telegram = AsyncMock()
    tts = AsyncMock(spec=TextToSpeech)
    player = AsyncMock(spec=AudioPlayer)
    music = AsyncMock()

    tts.synthesize = AsyncMock(return_value=b"audio-data")

    from clawdia.voice.pipeline import make_voice_reply

    reply = make_voice_reply(
        telegram=telegram,
        tts=tts,
        player=player,
        music=music,
        response_telegram=False,
        response_tts=True,
    )
    await reply("Hello there")

    tts.synthesize.assert_called_once_with("Hello there")
    player.play_bytes.assert_called_once_with(b"audio-data", suffix=".wav")
    telegram.notify.assert_not_called()


async def test_voice_reply_ducks_spotify():
    """Test that Spotify is paused before TTS and resumed after."""
    from clawdia.voice.tts import TextToSpeech
    from clawdia.voice.player import AudioPlayer

    telegram = AsyncMock()
    tts = AsyncMock(spec=TextToSpeech)
    player = AsyncMock(spec=AudioPlayer)
    music = AsyncMock()

    tts.synthesize = AsyncMock(return_value=b"audio-data")

    call_order = []
    music.pause = AsyncMock(side_effect=lambda: call_order.append("pause"))
    music.play = AsyncMock(side_effect=lambda: call_order.append("resume"))
    player.play_bytes = AsyncMock(side_effect=lambda *a, **kw: call_order.append("play"))

    from clawdia.voice.pipeline import make_voice_reply

    reply = make_voice_reply(
        telegram=telegram,
        tts=tts,
        player=player,
        music=music,
        response_telegram=False,
        response_tts=True,
    )
    await reply("Playing jazz")

    assert call_order == ["pause", "play", "resume"]


async def test_voice_reply_no_duck_without_music():
    """Test that TTS works without a music controller (no ducking)."""
    from clawdia.voice.tts import TextToSpeech
    from clawdia.voice.player import AudioPlayer

    telegram = AsyncMock()
    tts = AsyncMock(spec=TextToSpeech)
    player = AsyncMock(spec=AudioPlayer)

    tts.synthesize = AsyncMock(return_value=b"audio-data")

    from clawdia.voice.pipeline import make_voice_reply

    reply = make_voice_reply(
        telegram=telegram,
        tts=tts,
        player=player,
        music=None,
        response_telegram=False,
        response_tts=True,
    )
    await reply("Hello")

    tts.synthesize.assert_called_once()
    player.play_bytes.assert_called_once()


async def test_voice_reply_tts_failure_falls_back_to_telegram():
    """Test that TTS failure sends the message to Telegram instead."""
    from clawdia.voice.tts import TextToSpeech
    from clawdia.voice.player import AudioPlayer

    telegram = AsyncMock()
    tts = AsyncMock(spec=TextToSpeech)
    player = AsyncMock(spec=AudioPlayer)

    tts.synthesize = AsyncMock(return_value=b"")  # failure returns empty

    from clawdia.voice.pipeline import make_voice_reply

    reply = make_voice_reply(
        telegram=telegram,
        tts=tts,
        player=player,
        music=None,
        response_telegram=True,
        response_tts=True,
    )
    await reply("Hello")

    # TTS failed, should not play
    player.play_bytes.assert_not_called()
    # Should still send to telegram
    telegram.notify.assert_called_once()


async def test_on_error_plays_error_sound_and_notifies():
    """Test that the error callback plays error.wav and notifies Telegram."""
    from clawdia.voice.pipeline import make_on_error

    telegram = AsyncMock()
    player = AsyncMock()

    on_error = make_on_error(telegram=telegram, player=player, error_sound="/path/error.wav")
    await on_error()

    player.play_file.assert_called_once_with("/path/error.wav")
    telegram.notify.assert_called_once()
    assert "not understood" in telegram.notify.call_args[0][0].lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_voice_pipeline.py -v`
Expected: FAIL — `clawdia.voice.pipeline` does not exist

- [ ] **Step 3: Create the voice pipeline module**

Create `src/clawdia/voice/pipeline.py`:

```python
from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from clawdia.telegram_bot import ClawdiaTelegramBot
    from clawdia.voice.player import AudioPlayer
    from clawdia.voice.tts import TextToSpeech


def make_voice_reply(
    *,
    telegram: ClawdiaTelegramBot,
    tts: TextToSpeech | None,
    player: AudioPlayer,
    music: object | None,
    response_telegram: bool,
    response_tts: bool,
) -> Callable[[str], Awaitable[None]]:
    """Create a reply callback for voice commands.

    Routes responses to TTS speaker and/or Telegram based on config flags.
    Ducks Spotify during TTS playback.
    """

    async def reply(text: str) -> None:
        tts_played = False

        if response_tts and tts:
            audio_data = await tts.synthesize(text)
            if audio_data:
                try:
                    if music:
                        await music.pause()  # type: ignore[union-attr]
                    await player.play_bytes(audio_data, suffix=".wav")
                    tts_played = True
                except Exception:
                    logger.exception("TTS playback failed")
                finally:
                    if music:
                        try:
                            await music.play()  # type: ignore[union-attr]
                        except Exception:
                            logger.warning("Failed to resume Spotify after TTS")

        if response_telegram:
            await telegram.notify(f"\U0001f399 {text}")
        elif not tts_played:
            # TTS was requested but failed — fall back to Telegram
            await telegram.notify(f"\U0001f399 {text}")

    return reply


def make_on_error(
    *,
    telegram: ClawdiaTelegramBot,
    player: AudioPlayer,
    error_sound: str,
) -> Callable[[], Awaitable[None]]:
    """Create an error callback for voice pipeline failures."""

    async def on_error() -> None:
        try:
            await player.play_file(error_sound)
        except Exception:
            logger.exception("Failed to play error sound")
        await telegram.notify("Voice command not understood (empty transcription)")

    return on_error
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_voice_pipeline.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add src/clawdia/voice/pipeline.py tests/test_voice_pipeline.py
git commit -m "feat: add voice pipeline reply and error callbacks"
```

---

### Task 7: Rewire main.py to Use Voice Pipeline

**Files:**
- Modify: `src/clawdia/main.py:133-204`

- [ ] **Step 1: Update main.py — initialize TTS and AudioPlayer**

After the STT initialization block (line 141) in `src/clawdia/main.py`, add TTS and player setup:

```python
    # Optional: TTS (needs OpenAI API key)
    tts = None
    if settings.openai_api_key and settings.voice_response_tts:
        from clawdia.voice.tts import TextToSpeech

        tts = TextToSpeech(
            api_key=settings.openai_api_key,
            model=settings.tts_model,
            voice=settings.tts_voice,
        )
```

- [ ] **Step 2: Rewrite the wake word listener block**

Replace lines 184-204 in `src/clawdia/main.py`:

```python
    # Optional: Start wake word listener (needs hardware)
    listener_task = None
    try:
        from pathlib import Path

        from clawdia.voice.listener import WakeWordListener
        from clawdia.voice.pipeline import make_on_error, make_voice_reply
        from clawdia.voice.player import AudioPlayer

        player = AudioPlayer()
        sounds_dir = str(Path(__file__).parent / "voice" / "sounds")

        voice_reply = make_voice_reply(
            telegram=telegram,
            tts=tts,
            player=player,
            music=music,
            response_telegram=settings.voice_response_telegram,
            response_tts=settings.voice_response_tts,
        )

        on_error = make_on_error(
            telegram=telegram,
            player=player,
            error_sound=f"{sounds_dir}/error.wav",
        )

        async def on_wake_word():
            logger.info("Wake word detected! Playing chime...")
            await player.play_file(f"{sounds_dir}/chime.wav")
            logger.info("Capturing audio...")
            audio_data = await listener.capture_audio(duration=5.0)
            await orchestrator.handle_audio(
                audio_data,
                reply=voice_reply,
                context_id=settings.voice_context_id,
                source="voice",
                on_error=on_error,
            )

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
```

- [ ] **Step 3: Run full test suite**

Run: `uv run pytest -v`
Expected: ALL PASS

- [ ] **Step 4: Run linting and type checks**

Run: `uv run ruff check . && uv run ruff format --check . && uv run pyright`
Expected: Clean

- [ ] **Step 5: Commit**

```bash
git add src/clawdia/main.py
git commit -m "feat: wire voice pipeline with chime, TTS, and Spotify ducking"
```

---

### Task 8: Deploy and Test on Pi

**Files:** None (manual validation)

- [ ] **Step 1: Deploy to Pi**

```bash
ssh clawdia "cd ~/clawdia && git pull && source ~/.local/bin/env && uv sync --frozen --extra voice && systemctl --user restart clawdia"
```

- [ ] **Step 2: Check service started**

```bash
ssh clawdia "systemctl --user status clawdia --no-pager"
```

Verify: active (running), no errors in recent log lines.

- [ ] **Step 3: Check wake word listener started**

```bash
ssh clawdia "journalctl --user -u clawdia --no-pager -n 30 | grep -i 'wake\|listen\|voice'"
```

Expected: "Wake word listener started" or "Listening for wake word 'hey_jarvis'..."

- [ ] **Step 4: Test mic capture**

SSH into Pi and run a quick recording test:

```bash
ssh clawdia "arecord -D pulse -f S16_LE -r 16000 -c 1 -d 3 /tmp/test_mic.wav && aplay -D pulse /tmp/test_mic.wav"
```

Speak into the mic during recording, then listen for playback through the speaker.

- [ ] **Step 5: Test chime playback**

```bash
ssh clawdia "paplay ~/clawdia/src/clawdia/voice/sounds/chime.wav"
```

Expected: Hear the chime through the speaker.

- [ ] **Step 6: Test full voice pipeline**

Say "Hey Jarvis" near the mic. Expected sequence:
1. Chime plays through speaker
2. 5 seconds of capture
3. TTS response plays through speaker
4. Response appears in Telegram

Check logs for the full flow:
```bash
ssh clawdia "journalctl --user -u clawdia --no-pager -n 50"
```

- [ ] **Step 7: Test Spotify ducking**

Start music via Telegram, then say "Hey Jarvis, what time is it?" Expected:
1. Chime plays
2. Audio captured
3. Spotify pauses
4. TTS response plays
5. Spotify resumes
