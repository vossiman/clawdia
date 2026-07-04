from __future__ import annotations

import io
import wave

import openai
from loguru import logger

# Biases the decoder toward command-like phrasings and music titles over
# free-form dialogue picked up from TV background noise
CONTEXT_PROMPT = (
    "Voice command to a home assistant: usually playing music "
    "(song, artist, album or playlist names, e.g. 'Play Wonderwall by Oasis'), "
    "pausing, skipping, volume, TV or PC control, or a short question."
)


class SpeechToText:
    """Transcribe audio using OpenAI Whisper API."""

    def __init__(self, api_key: str, model: str = "gpt-4o-mini-transcribe"):
        self.model = model
        self._client = openai.AsyncOpenAI(api_key=api_key)

    def pcm_to_wav(self, pcm_data: bytes, sample_rate: int = 16000) -> bytes:
        """Wrap raw PCM int16 mono data in a WAV container."""
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(pcm_data)
        return buf.getvalue()

    async def transcribe(self, audio_bytes: bytes, language: str = "en") -> str:
        """Transcribe WAV audio bytes to text."""
        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = "audio.wav"

        try:
            response = await self._client.audio.transcriptions.create(
                model=self.model,
                file=audio_file,
                language=language,
                prompt=CONTEXT_PROMPT,
            )
            text = response.text.strip()
            logger.info("STT result: '{}'", text)
            return text
        except Exception:
            logger.exception("STT transcription failed")
            return ""
