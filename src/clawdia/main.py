from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys

from dotenv import load_dotenv
load_dotenv()

from clawdia.config import settings
from clawdia.brain import Brain
from clawdia.ir import IRController
from clawdia.music import MusicController
from clawdia.orchestrator import Orchestrator
from clawdia.telegram_bot import ClawdiaTelegramBot

logger = logging.getLogger(__name__)


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


def main():
    """Sync entry point."""
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
