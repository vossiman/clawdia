from __future__ import annotations

from typing import TYPE_CHECKING

from clawdia.brain.agent import create_agent
from clawdia.brain.models import ClawdiaResponse

if TYPE_CHECKING:
    from clawdia.ir import IRController
    from clawdia.music import MusicController


class Brain:
    """High-level interface to the Clawdia intent engine."""

    def __init__(
        self,
        model: str = "openrouter:anthropic/claude-haiku-4.5",
        ir: IRController | None = None,
        music: MusicController | None = None,
    ):
        self._model = model
        self._ir = ir
        self._music = music
        self.agent = create_agent(model=model, ir=ir, music=music)

    def reload_commands(self) -> None:
        """Rebuild the agent with current IR commands."""
        self.agent = create_agent(model=self._model, ir=self._ir, music=self._music)

    async def process(self, text: str) -> ClawdiaResponse:
        """Process a text command and return a structured response."""
        result = await self.agent.run(text)
        return result.output
