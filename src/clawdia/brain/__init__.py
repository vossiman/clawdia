from __future__ import annotations

from clawdia.brain.agent import create_agent
from clawdia.brain.models import ClawdiaResponse


class Brain:
    """High-level interface to the Clawdia intent engine."""

    def __init__(self, model: str = "openrouter:anthropic/claude-haiku-4-5-20251001"):
        self.agent = create_agent(model=model)

    async def process(self, text: str) -> ClawdiaResponse:
        """Process a text command and return a structured response."""
        result = await self.agent.run(text)
        return result.output
