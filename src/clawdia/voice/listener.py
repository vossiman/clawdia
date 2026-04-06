from __future__ import annotations

import asyncio
import importlib
import time
from collections.abc import Awaitable, Callable
from typing import Any

from loguru import logger


class WakeWordListener:
    """Listens for wake word using openWakeWord.

    Designed to work without hardware for testing - actual mic capture
    is only started when start_listening() is called on a Pi with a mic.
    """

    def __init__(
        self,
        model_path: str = "hey_jarvis",
        threshold: float = 0.7,
        sample_rate: int = 16000,
        chunk_size: int = 1280,
        cooldown: float = 5.0,
        on_wake_word: Callable[[], Awaitable[None]] | None = None,
    ):
        self.model_path = model_path
        self.threshold = threshold
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.cooldown = cooldown
        self.on_wake_word = on_wake_word
        self._running = False
        self._oww_model = None
        self._last_detection: float = 0.0
        self._suppressed = False

    async def _on_detected(self) -> None:
        """Called when wake word is detected."""
        logger.info("Wake word detected!")
        if self.on_wake_word:
            await self.on_wake_word()

    def _init_model(self):
        """Initialize the openWakeWord model. Requires openwakeword package."""
        try:
            model_module = importlib.import_module("openwakeword.model")
            model_cls = model_module.Model

            self._oww_model = model_cls(
                wakeword_models=[self.model_path],
                inference_framework="onnx",
            )
            logger.info("Wake word model loaded: {}", self.model_path)
        except ImportError:
            logger.warning("openwakeword not installed. Wake word detection disabled.")
        except Exception:
            logger.exception("Failed to load wake word model")

    async def start_listening(self) -> None:
        """Start listening for the wake word on the microphone.

        Requires: openwakeword, pyaudio, and a working microphone.
        """
        try:
            np: Any = importlib.import_module("numpy")
            pyaudio: Any = importlib.import_module("pyaudio")
        except ImportError:
            logger.error("pyaudio/numpy not installed. Install with: pip install clawdia[voice]")
            return

        self._init_model()
        if self._oww_model is None:
            logger.error("No wake word model available. Cannot listen.")
            return

        audio = pyaudio.PyAudio()
        stream = audio.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=self.sample_rate,
            input=True,
            frames_per_buffer=self.chunk_size,
        )

        self._running = True
        logger.info("Listening for wake word '{}'...", self.model_path)

        try:
            while self._running:
                audio_frame = np.frombuffer(
                    stream.read(self.chunk_size, exception_on_overflow=False),
                    dtype=np.int16,
                )
                predictions = self._oww_model.predict(audio_frame)

                for _model_name, score in predictions.items():
                    if score > 0.1:
                        logger.debug(
                            "Wake word score: {:.3f} (threshold: {})", score, self.threshold
                        )
                    if self._suppressed:
                        continue
                    now = time.monotonic()
                    if score > self.threshold and (now - self._last_detection) > self.cooldown:
                        self._last_detection = now
                        await self._on_detected()

                await asyncio.sleep(0)
        finally:
            stream.stop_stream()
            stream.close()
            audio.terminate()

    async def capture_audio(self, duration: float = 5.0) -> bytes:
        """Capture audio from mic for a given duration. Returns raw PCM bytes."""
        try:
            pyaudio: Any = importlib.import_module("pyaudio")
        except ImportError:
            logger.error("pyaudio not installed")
            return b""

        audio = pyaudio.PyAudio()
        stream = audio.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=self.sample_rate,
            input=True,
            frames_per_buffer=self.chunk_size,
        )

        frames = []
        num_chunks = int(self.sample_rate / self.chunk_size * duration)

        logger.info("Capturing audio for {:.1f}s...", duration)
        for _ in range(num_chunks):
            data = stream.read(self.chunk_size, exception_on_overflow=False)
            frames.append(data)
            await asyncio.sleep(0)

        stream.stop_stream()
        stream.close()
        audio.terminate()

        return b"".join(frames)

    def stop(self) -> None:
        """Stop listening."""
        self._running = False
