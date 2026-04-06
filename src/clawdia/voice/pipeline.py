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
