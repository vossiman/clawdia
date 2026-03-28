from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from clawdia.brain import Brain
    from clawdia.ir import IRController
    from clawdia.telegram_bot import ClawdiaTelegramBot
    from clawdia.voice.stt import SpeechToText

logger = logging.getLogger(__name__)


class Orchestrator:
    """Coordinates the full Clawdia pipeline.

    Connects: voice -> STT -> brain -> action routing (IR / Telegram).
    """

    def __init__(
        self,
        brain: Brain,
        ir: IRController,
        telegram: ClawdiaTelegramBot,
        stt: SpeechToText | None = None,
    ):
        self.brain = brain
        self.ir = ir
        self.telegram = telegram
        self.stt = stt

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
