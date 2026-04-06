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
