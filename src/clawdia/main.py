from __future__ import annotations

import asyncio
import logging
import signal
import sys

from clawdia.config import settings
from clawdia.brain import Brain
from clawdia.ir import IRController
from clawdia.orchestrator import Orchestrator
from clawdia.telegram_bot import ClawdiaTelegramBot

logger = logging.getLogger(__name__)


async def run() -> None:
    """Main async entry point for Clawdia."""
    logging.basicConfig(
        level=logging.DEBUG if settings.debug else logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    logger.info("Starting Clawdia...")

    # Initialize components
    brain = Brain(model=f"openrouter:{settings.openrouter_model}")

    ir = IRController(
        device_send=settings.ir_device_send,
        codes_dir=settings.ir_codes_dir,
    )

    telegram = ClawdiaTelegramBot(
        token=settings.telegram_bot_token,
        chat_id=settings.telegram_chat_id,
        brain=brain,
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
    )

    # Wire up Telegram message handler to orchestrator
    async def enhanced_message_handler(update, context):
        """Enhanced handler that routes brain responses through orchestrator."""
        if update.effective_chat.id != telegram.chat_id:
            await update.message.reply_text("Sorry, I only respond to my owner.")
            return

        text = update.message.text
        logger.info("Telegram command: %s", text)
        await orchestrator.handle_text_command(text)

    telegram._handle_message = enhanced_message_handler

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
