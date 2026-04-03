from __future__ import annotations

import base64
import json
from dataclasses import dataclass

import anthropic
from loguru import logger

from clawdia.pc_agent.actions import click, press_key, take_screenshot, type_text

MAX_ITERATIONS = 30


@dataclass
class AgentResult:
    success: bool
    summary: str

    def to_json(self) -> str:
        return json.dumps({"success": self.success, "summary": self.summary})


class ComputerUseAgent:
    """Runs the computer use loop: screenshot -> Claude -> action -> repeat."""

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-6-20250514",
        max_iterations: int = MAX_ITERATIONS,
    ):
        self.client = anthropic.AsyncAnthropic(api_key=api_key)
        self.model = model
        self.max_iterations = max_iterations

    async def _take_screenshot(self) -> bytes:
        result = await take_screenshot()
        if not result.success or result.data is None:
            raise RuntimeError(f"Screenshot failed: {result.error}")
        return result.data

    async def _call_api(self, messages: list, system: str) -> anthropic.types.Message:
        return await self.client.messages.create(  # pyright: ignore[reportCallIssue]
            model=self.model,
            max_tokens=4096,
            system=system,
            messages=messages,
            tools=[
                {
                    "type": "computer_20250124",
                    "name": "computer",
                    "display_width_px": 1920,
                    "display_height_px": 1080,
                    "display_number": 0,
                },
            ],
            betas=["computer-use-2025-01-24"],
        )

    async def _execute_tool(self, tool_input: dict) -> bytes | str:
        action = tool_input.get("action")
        if action == "screenshot":
            return await self._take_screenshot()
        elif action == "left_click":
            coords = tool_input.get("coordinate", [0, 0])
            await click(coords[0], coords[1])
            return await self._take_screenshot()
        elif action == "type":
            await type_text(tool_input.get("text", ""))
            return await self._take_screenshot()
        elif action == "key":
            await press_key(tool_input.get("text", ""))
            return await self._take_screenshot()
        else:
            logger.warning("Unknown action: {}", action)
            return await self._take_screenshot()

    async def run(self, goal: str, knowledge_context: str) -> AgentResult:
        """Execute the computer use loop until the goal is achieved or max iterations reached."""
        system = f"You are controlling a Linux desktop to accomplish a goal.\n\nGoal: {goal}"
        if knowledge_context:
            system += f"\n\nKnown facts about this PC:\n{knowledge_context}"

        screenshot_data = await self._take_screenshot()
        screenshot_b64 = base64.standard_b64encode(screenshot_data).decode()

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": f"Please accomplish this goal: {goal}"},
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": screenshot_b64,
                        },
                    },
                ],
            },
        ]

        for iteration in range(self.max_iterations):
            logger.info("Computer use iteration {}/{}", iteration + 1, self.max_iterations)

            response = await self._call_api(messages, system)

            tool_uses = [b for b in response.content if b.type == "tool_use"]
            text_blocks = [b for b in response.content if b.type == "text"]

            if not tool_uses:
                summary = text_blocks[0].text if text_blocks else "Goal completed."
                return AgentResult(success=True, summary=summary)

            messages.append({"role": "assistant", "content": response.content})

            tool_results = []
            for tool_use in tool_uses:
                result_data = await self._execute_tool(tool_use.input)

                if isinstance(result_data, bytes):
                    result_b64 = base64.standard_b64encode(result_data).decode()
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": tool_use.id,
                            "content": [
                                {
                                    "type": "image",
                                    "source": {
                                        "type": "base64",
                                        "media_type": "image/png",
                                        "data": result_b64,
                                    },
                                },
                            ],
                        }
                    )
                else:
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": tool_use.id,
                            "content": str(result_data),
                        }
                    )

            messages.append({"role": "user", "content": tool_results})

        return AgentResult(
            success=False, summary="Reached max iterations without completing the goal."
        )
