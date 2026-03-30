from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic_ai import Agent

from clawdia.brain.models import ClawdiaResponse

if TYPE_CHECKING:
    from clawdia.ir import IRController

SYSTEM_PROMPT = """\
You are Clawdia, a voice-controlled home assistant running on a Raspberry Pi.

You can control devices via infrared commands and answer general questions.

## Available IR Commands

{ir_commands}

## Rules

1. If the user wants to control a device, respond with action="ir" and the exact command name.
2. If the user asks a question or wants information, respond with action="respond" and your answer.
3. Always include a brief, friendly message describing what you did or your answer.
4. If no IR command matches what the user wants, respond with action="respond" and tell them.
5. If you're unsure what the user wants, respond with action="respond" and ask for clarification.
"""


def build_system_prompt(ir: IRController) -> str:
    commands = ir.list_commands_with_descriptions()
    if commands:
        lines = [f"- {name}: {desc}" if desc else f"- {name}" for name, desc in commands]
        ir_commands = "\n".join(lines)
    else:
        ir_commands = "No IR commands recorded yet."
    return SYSTEM_PROMPT.format(ir_commands=ir_commands)


def create_agent(model: str = "openrouter:anthropic/claude-haiku-4.5", ir: IRController | None = None) -> Agent:
    """Create the Clawdia PydanticAI agent."""
    if ir:
        prompt = build_system_prompt(ir)
    else:
        prompt = SYSTEM_PROMPT.format(ir_commands="No IR commands recorded yet.")
    return Agent(
        model,
        output_type=ClawdiaResponse,
        instructions=prompt,
    )
