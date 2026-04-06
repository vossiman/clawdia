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
                "paplay",
                path,
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
