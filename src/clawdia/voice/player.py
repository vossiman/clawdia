from __future__ import annotations

import asyncio
import tempfile

from loguru import logger


class AudioPlayer:
    """Play audio through PulseAudio using paplay."""

    def __init__(self, tts_volume_percent: int = 100):
        # per-stream volume relative to the master sink; 65536 = 100%
        self.tts_volume_percent = tts_volume_percent

    async def play_file(self, path: str) -> None:
        """Play a WAV file through the default PulseAudio sink."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "paplay",
                f"--volume={int(65536 * self.tts_volume_percent / 100)}",
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
