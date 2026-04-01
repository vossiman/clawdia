from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

SCREENSHOT_PATH = Path("/tmp/clawdia_screenshot.png")


@dataclass
class ActionResult:
    success: bool
    data: bytes | None = None
    error: str = ""


async def _run(cmd: list[str]) -> ActionResult:
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
    except Exception as e:
        return ActionResult(success=False, error=str(e))

    if process.returncode != 0:
        return ActionResult(success=False, error=stderr.decode().strip())
    return ActionResult(success=True)


async def take_screenshot() -> ActionResult:
    """Capture full screen screenshot using scrot."""
    result = await _run(["scrot", "-o", str(SCREENSHOT_PATH)])
    if not result.success:
        return result
    try:
        data = SCREENSHOT_PATH.read_bytes()
        return ActionResult(success=True, data=data)
    except Exception as e:
        return ActionResult(success=False, error=str(e))


async def click(x: int, y: int) -> ActionResult:
    """Move mouse to (x, y) and click."""
    result = await _run(["xdotool", "mousemove", str(x), str(y)])
    if not result.success:
        return result
    return await _run(["xdotool", "click", "1"])


async def type_text(text: str) -> ActionResult:
    """Type text using xdotool."""
    return await _run(["xdotool", "type", "--delay", "50", text])


async def press_key(combo: str) -> ActionResult:
    """Press a key combination using xdotool."""
    return await _run(["xdotool", "key", combo])
