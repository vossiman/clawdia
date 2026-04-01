from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime

from loguru import logger


@dataclass
class PlaybackState:
    source: str
    user_chat_id: int | None
    service: str
    description: str
    started_at: datetime


class PlaybackCoordinator:
    """Ensures only one audio source plays at a time."""

    def __init__(self) -> None:
        self.state: PlaybackState | None = None
        self._stop_callbacks: dict[str, Callable[[], Awaitable]] = {}

    def register_service(self, name: str, stop: Callable[[], Awaitable]) -> None:
        self._stop_callbacks[name] = stop

    async def play(
        self,
        service: str,
        source: str,
        user_chat_id: int | None,
        callback: Callable[[], Awaitable[str]],
        description: str,
    ) -> str:
        if self.state and self.state.service != service:
            await self._stop_active()

        result = await callback()
        self.state = PlaybackState(
            source=source,
            user_chat_id=user_chat_id,
            service=service,
            description=description,
            started_at=datetime.now(),
        )
        return result

    async def stop(self, service: str) -> None:
        if self.state and self.state.service == service:
            self.state = None

    async def _stop_active(self) -> None:
        if not self.state:
            return
        stop_cb = self._stop_callbacks.get(self.state.service)
        if stop_cb:
            try:
                await stop_cb()
            except Exception:
                logger.exception("Failed to stop {}", self.state.service)
        self.state = None

    def get_state_for_prompt(self) -> str:
        if not self.state:
            return "Nothing is currently playing."
        elapsed = datetime.now() - self.state.started_at
        minutes = int(elapsed.total_seconds() // 60)
        if minutes < 1:
            ago = "just now"
        elif minutes == 1:
            ago = "1 min ago"
        else:
            ago = f"{minutes} min ago"
        return f"Currently playing: {self.state.description} ({self.state.service}, since {ago})"
