from __future__ import annotations

import asyncio

from loguru import logger


class AudioOutput:
    """System audio levels via PulseAudio (pactl).

    Owns the master output (sink) volume and mic (source) gain. Music and
    TTS both play through the default sink, so set_volume is the master
    volume for everything Clawdia outputs.
    """

    def __init__(self, max_volume: int = 80, startup_volume: int = 60, mic_volume: int = 250):
        self.max_volume = max_volume
        self.startup_volume = startup_volume
        self.mic_volume = mic_volume

    async def _pactl(self, *args: str) -> int:
        """Run a pactl command. Returns the exit code, -1 if pactl is unavailable."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "pactl",
                *args,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.wait()
            return proc.returncode if proc.returncode is not None else -1
        except Exception:
            logger.exception("pactl call failed: {}", args)
            return -1

    async def set_volume(self, level: int) -> str:
        """Set the master output volume (0-100), clamped to max_volume."""
        clamped = max(0, min(level, self.max_volume))
        code = await self._pactl("set-sink-volume", "@DEFAULT_SINK@", f"{clamped}%")
        if code != 0:
            return f"Failed to set volume (pactl exit code {code})."
        if clamped < level:
            return f"Volume set to {clamped}% (max)."
        return f"Volume set to {clamped}%."

    async def initialize(self) -> None:
        """Set startup audio levels: mic gain and master output volume."""
        await self._pactl("set-source-volume", "@DEFAULT_SOURCE@", f"{self.mic_volume}%")
        await self._pactl("set-sink-volume", "@DEFAULT_SINK@", f"{self.startup_volume}%")
        logger.info(
            "Audio levels initialized (mic: {}%, output: {}%)",
            self.mic_volume,
            self.startup_volume,
        )
