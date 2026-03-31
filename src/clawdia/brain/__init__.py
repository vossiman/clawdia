from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic_ai.messages import ModelMessage

from clawdia.brain.agent import create_agent
from clawdia.brain.models import ClawdiaResponse

if TYPE_CHECKING:
    from clawdia.ir import IRController
    from clawdia.music import MusicController
    from clawdia.playback import PlaybackCoordinator


class Brain:
    """High-level interface to the Clawdia intent engine."""

    def __init__(
        self,
        model: str = "openrouter:anthropic/claude-haiku-4.5",
        ir: IRController | None = None,
        music: MusicController | None = None,
        pc_enabled: bool = False,
        pc_knowledge: str = "",
        coordinator: PlaybackCoordinator | None = None,
    ):
        self._model = model
        self._ir = ir
        self._music = music
        self._pc_enabled = pc_enabled
        self._pc_knowledge = pc_knowledge
        self._coordinator = coordinator
        self._history: dict[str, list[ModelMessage]] = {}
        self.agent = create_agent(model=model, ir=ir, music=music, pc_enabled=pc_enabled, pc_knowledge=pc_knowledge)

    def reload_commands(self, pc_knowledge: str | None = None) -> None:
        """Rebuild the agent with current IR commands and knowledge."""
        if pc_knowledge is not None:
            self._pc_knowledge = pc_knowledge
        self.agent = create_agent(
            model=self._model, ir=self._ir, music=self._music,
            pc_enabled=self._pc_enabled, pc_knowledge=self._pc_knowledge,
        )

    def _trimmed_history(self, context_id: str, max_exchanges: int = 3) -> list[ModelMessage]:
        """Return the last N exchanges for a context."""
        messages = self._history.get(context_id, [])
        # Each exchange produces 3 messages with structured output:
        # request, response (tool call), request (tool return)
        limit = max_exchanges * 3
        return messages[-limit:] if len(messages) > limit else list(messages)

    async def process(self, text: str, context_id: str = "default") -> ClawdiaResponse:
        """Process a text command and return a structured response."""
        playback_state = self._coordinator.get_state_for_prompt() if self._coordinator else None
        agent = create_agent(
            model=self._model,
            ir=self._ir,
            music=self._music,
            pc_enabled=self._pc_enabled,
            pc_knowledge=self._pc_knowledge,
            playback_state=playback_state,
        )
        history = self._trimmed_history(context_id)
        result = await agent.run(text, message_history=history)
        if context_id not in self._history:
            self._history[context_id] = []
        self._history[context_id].extend(result.new_messages())
        return result.output
