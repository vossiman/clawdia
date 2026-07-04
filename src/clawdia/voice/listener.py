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
        patience: int = 1,
        vad_threshold: float = 0.0,
        verifier_model: str = "",
        verifier_threshold: float = 0.3,
        on_wake_word: Callable[[], Awaitable[None]] | None = None,
    ):
        self.model_path = model_path
        self.threshold = threshold
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.cooldown = cooldown
        self.patience = patience
        self.vad_threshold = vad_threshold
        self.verifier_model = verifier_model
        self.verifier_threshold = verifier_threshold
        self.on_wake_word = on_wake_word
        self._running = False
        self._oww_model = None
        self._last_detection: float | None = None
        self._suppressed = False
        self._streak = 0

    def _should_trigger(self, score: float, now: float | None = None) -> bool:
        """Decide whether a frame's score triggers the wake word.

        Requires `patience` consecutive frames above threshold to filter out
        single-frame spikes from TV audio or music.
        """
        if now is None:
            now = time.monotonic()
        if self._suppressed:
            self._streak = 0
            return False
        if score > self.threshold:
            self._streak += 1
        else:
            self._streak = 0
            return False
        if self._streak < self.patience:
            return False
        if self._last_detection is not None and (now - self._last_detection) <= self.cooldown:
            return False
        self._streak = 0
        self._last_detection = now
        return True

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

            kwargs: dict[str, Any] = {}
            if self.verifier_model:
                kwargs["custom_verifier_models"] = {self.model_path: self.verifier_model}
                kwargs["custom_verifier_threshold"] = self.verifier_threshold

            self._oww_model = model_cls(
                wakeword_models=[self.model_path],
                inference_framework="onnx",
                vad_threshold=self.vad_threshold,
                **kwargs,
            )
            logger.info(
                "Wake word model loaded: {}{}",
                self.model_path,
                f" (verifier: {self.verifier_model})" if self.verifier_model else "",
            )
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
                    if self._should_trigger(score):
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

    def reset_state(self) -> None:
        """Reset the wake word model's prediction state."""
        if self._oww_model is not None:
            self._oww_model.reset()
            logger.debug("Wake word model state reset")

    def stop(self) -> None:
        """Stop listening."""
        self._running = False
