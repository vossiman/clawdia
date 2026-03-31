from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic_ai import Agent

from clawdia.brain.models import ClawdiaResponse

if TYPE_CHECKING:
    from clawdia.ir import IRController
    from clawdia.music import MusicController

SYSTEM_PROMPT = """\
You are Clawdia, a voice-controlled home assistant running on a Raspberry Pi.

You can control devices via infrared commands, control music playback, control a Linux PC remotely, and answer general questions.

## Available IR Commands

{ir_commands}

## Music Playback

{music_section}

## PC Remote Control

{pc_section}

## Current Playback State

{playback_state}

## Rules

1. If the user wants to control a device (TV, etc.), respond with action="ir" and the exact command name.
2. If the user wants to play music, search for songs, control playback (pause, skip, volume, etc.), or manage playlists, respond with action="music" with the appropriate command.
3. If the user wants to control the Linux PC (open apps, browse websites, interact with desktop, run commands), respond with action="pc".
   - Use command_type="shell" for simple commands (opening URLs, launching apps, adjusting volume, terminal commands).
   - Use command_type="computer_use" when the task requires seeing and interacting with the screen (clicking through menus, navigating web apps, filling forms).
4. If the user is correcting or providing feedback about a previous action (e.g. "wrong URL", "not that browser"), respond with action="learn" to store the correction.
5. If the user asks a question or wants information, respond with action="respond" and your answer.
6. Always include a brief, friendly message describing what you did or your answer.
7. If you're unsure what the user wants, respond with action="respond" and ask for clarification.

### Music Commands Reference

- play: Resume playback
- pause: Pause playback
- skip: Skip to next track
- previous: Go to previous track
- volume: Set volume (include volume field, 0-100)
- play_query: Search and play a track (include query field)
- play_playlist: Find and play a playlist by name (include query field)
- queue: Add a track to the queue (include query field)
- search: Search for tracks (include query field)
- now_playing: Show what's currently playing
- list_playlists: List available playlists

### Learn Action

When the user corrects a previous action, extract the fact and store it:
- section: which part of the knowledge base to update ("pc", "services", "preferences", "corrections")
- key: the specific item (e.g. "browser", "emby")
- value: the corrected information (string or dict)
"""

MUSIC_ENABLED = "Music playback is available via Spotify. Use action=\"music\" for any music-related requests."
MUSIC_DISABLED = "Music playback is not currently configured."

PC_ENABLED = """\
PC remote control is available. Use action="pc" for any PC-related requests.

### Known facts about the PC:

{pc_knowledge}"""

PC_DISABLED = "PC remote control is not configured."


def build_system_prompt(
    ir: IRController,
    music: MusicController | None = None,
    pc_enabled: bool = False,
    pc_knowledge: str = "",
    playback_state: str | None = None,
) -> str:
    commands = ir.list_commands_with_descriptions()
    if commands:
        lines = [f"- {name}: {desc}" if desc else f"- {name}" for name, desc in commands]
        ir_commands = "\n".join(lines)
    else:
        ir_commands = "No IR commands recorded yet."

    music_section = MUSIC_ENABLED if music else MUSIC_DISABLED
    ps = playback_state if playback_state else ""

    if pc_enabled:
        pc_section = PC_ENABLED.format(pc_knowledge=pc_knowledge or "No facts recorded yet.")
    else:
        pc_section = PC_DISABLED

    return SYSTEM_PROMPT.format(
        ir_commands=ir_commands,
        music_section=music_section,
        pc_section=pc_section,
        playback_state=ps,
    )


def create_agent(
    model: str = "openrouter:anthropic/claude-haiku-4.5",
    ir: IRController | None = None,
    music: MusicController | None = None,
    pc_enabled: bool = False,
    pc_knowledge: str = "",
    playback_state: str | None = None,
) -> Agent:
    """Create the Clawdia PydanticAI agent."""
    if ir:
        prompt = build_system_prompt(ir=ir, music=music, pc_enabled=pc_enabled, pc_knowledge=pc_knowledge, playback_state=playback_state)
    else:
        prompt = SYSTEM_PROMPT.format(
            ir_commands="No IR commands recorded yet.",
            music_section=MUSIC_ENABLED if music else MUSIC_DISABLED,
            pc_section=PC_ENABLED.format(pc_knowledge=pc_knowledge or "No facts recorded yet.") if pc_enabled else PC_DISABLED,
            playback_state=playback_state or "",
        )
    return Agent(
        model,
        output_type=ClawdiaResponse,
        instructions=prompt,
    )
