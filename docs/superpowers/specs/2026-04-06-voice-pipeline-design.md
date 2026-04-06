# Voice Pipeline Design: Wake Word + STT + TTS

**Date:** 2026-04-06
**Status:** Approved

## Overview

Bring the existing (untested) wake word detection and speech-to-text code to life on the Raspberry Pi, and add text-to-speech response output. The voice pipeline should feel like a natural extension of the existing Telegram interaction — same brain, same conversation context, same action routing.

## Hardware

- **Microphone:** USB mic `ZX-5061-675` (ALSA card 3), PulseAudio source `alsa_input.usb-Solid_State_System_Co._Ltd._ZX-5061-675_000000000000-00.mono-fallback`
- **Speaker:** Jieli `UACDemoV1.0` (ALSA card 4), already used for Spotify/librespot output
- **PulseAudio** is the audio server, already running as a systemd user service

## Components

### TextToSpeech (`src/clawdia/voice/tts.py`)

- Uses `openai.AsyncOpenAI` (same pattern as `SpeechToText`)
- Method `synthesize(text: str) -> bytes` — returns audio bytes
- Configurable voice and model via settings

### AudioPlayer (`src/clawdia/voice/player.py`)

- Plays audio through PulseAudio via `paplay` subprocess
- `play_file(path: str)` — plays a static WAV file (chime, error sound)
- `play_bytes(data: bytes, suffix: str)` — writes to temp file, plays via `paplay`
- Pure audio playback only — does not manage Spotify. Ducking is handled by the voice reply callback in `main.py`

### Static Audio Assets (`src/clawdia/voice/sounds/`)

- `chime.wav` — wake word acknowledgment beep
- `error.wav` — "didn't catch that" notification sound

## Configuration

New settings in `config.py`:

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `tts_model` | `str` | `"tts-1"` | OpenAI TTS model |
| `tts_voice` | `str` | `"alloy"` | OpenAI TTS voice |
| `voice_response_telegram` | `bool` | `True` | Send voice responses to Telegram |
| `voice_response_tts` | `bool` | `True` | Speak responses via speaker |
| `voice_context_id` | `str` | `"voice"` | Context ID for voice conversation history |

Existing voice settings remain unchanged: `wake_word_model`, `wake_word_threshold`, `audio_sample_rate`, `audio_chunk_size`.

## Voice Pipeline Flow

### Happy Path

1. `WakeWordListener` detects "hey jarvis"
2. Play `chime.wav` through speaker
3. Capture 5 seconds of audio (existing `capture_audio()`)
4. Send to OpenAI Whisper STT, get text back
5. Call `orchestrator.handle_text_command(text, reply=voice_reply, source="voice", context_id=voice_context_id)`
6. Brain processes command, action executes, response text generated
7. `voice_reply(response_text)` fires:
   - If `voice_response_tts` enabled: pause Spotify, synthesize TTS, play audio, resume Spotify
   - If `voice_response_telegram` enabled: send text to all Telegram chat IDs

### Empty STT Path

1. Wake word detected, chime plays, audio captured
2. STT returns empty string
3. Play `error.wav` through speaker
4. Send "Voice command not understood (empty transcription)" to Telegram

### Error Handling

- **STT API failure:** Log error, play error sound, notify Telegram
- **TTS API failure:** Log error, fall back to Telegram-only response
- **Playback failure:** Log error, continue (non-fatal)

## Architecture Decisions

### Orchestrator stays source-agnostic

The orchestrator does not know about TTS. The `reply` callback passed from `main.py` handles voice output routing (TTS + Telegram). This mirrors how Telegram passes its own `reply=message.reply_text` callback. The orchestrator just calls `reply(text)` and doesn't care how it's delivered.

### Voice commands use the same pipeline as Telegram

Voice input goes through `handle_text_command()` with `source="voice"` and a dedicated `context_id`. This means voice gets the same brain processing, conversation history, and action routing as Telegram messages.

### Spotify ducking via full pause/resume

When playing TTS audio, Spotify is fully paused (not volume-ducked). The existing `SpotifyController.pause()` and `play()` methods handle this. Simpler than volume manipulation and avoids audio overlap.

### Audio playback via `paplay`

Uses PulseAudio CLI (`paplay`) as a subprocess for audio playback. No new Python audio dependencies needed. Works with the existing PulseAudio setup that librespot already uses.

### Concurrency

While capturing audio or playing TTS, the wake word listener is effectively paused (same async loop, mic stream is occupied). After the response plays, the listener resumes. No concurrent listening during playback.

## Testing

### Unit Tests

- `TextToSpeech.synthesize()` — mock OpenAI client, verify API call and returned bytes
- `AudioPlayer.play_bytes()` — mock subprocess, verify `paplay` invocation
- `AudioPlayer` Spotify ducking — mock music controller, verify pause/resume around playback
- Voice reply callback — verify routing based on config flags

### Manual Integration Tests on Pi

1. Test mic capture: record a few seconds, play back to verify audio quality
2. Test wake word: say "hey jarvis", verify detection in logs
3. Test chime playback: verify sound comes through speaker
4. Test full pipeline: wake word, speak command, hear TTS response
5. Test Spotify ducking: music playing, voice command, music pauses, response plays, music resumes

## Out of Scope

- Custom "hey clawdia" wake word (future — needs model training)
- Barge-in / interrupt detection
- Continuous conversation without re-triggering wake word
- Volume ducking (using full pause/resume instead)
- Local TTS fallback
- Multi-room / multi-mic support
