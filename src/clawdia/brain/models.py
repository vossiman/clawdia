from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class IRAction(BaseModel):
    """An IR command to send to the TV."""
    command: str = Field(description="IR command name, e.g. 'power', 'vol_up', 'channel_3'")
    repeat: int = Field(default=1, description="Number of times to send the command", ge=1, le=10)


class MusicAction(BaseModel):
    """A music playback command."""
    command: Literal[
        "play", "pause", "skip", "previous", "volume",
        "search", "play_query", "play_playlist", "queue",
        "now_playing", "list_playlists",
    ] = Field(description="Music command to execute")
    query: str | None = Field(default=None, description="Search query or playlist name")
    volume: int | None = Field(default=None, description="Volume level 0-100", ge=0, le=100)


class PCAction(BaseModel):
    """A command to execute on the remote Linux PC."""
    command_type: Literal["shell", "computer_use"] = Field(
        description="'shell' for direct commands, 'computer_use' for GUI interaction"
    )
    shell_command: str | None = Field(
        default=None, description="Shell command to run, required if command_type='shell'"
    )
    goal: str | None = Field(
        default=None, description="Natural language goal for computer use agent, required if command_type='computer_use'"
    )


class LearnAction(BaseModel):
    """A correction or fact to add to the knowledge base."""
    section: str = Field(description="Knowledge base section: 'pc', 'services', 'preferences', or 'corrections'")
    key: str = Field(description="Key within the section, e.g. 'browser', 'emby'")
    value: str | dict = Field(description="The fact to store")


class ClawdiaResponse(BaseModel):
    """Structured response from the Clawdia brain."""
    action: Literal["ir", "respond", "music", "pc", "learn"] = Field(
        description=(
            "'ir' to send an IR command, 'respond' to reply with text, "
            "'music' to control music, 'pc' to control the Linux PC, "
            "'learn' to store a correction or fact"
        )
    )
    ir: IRAction | None = Field(
        default=None, description="IR command details, required if action='ir'"
    )
    music: MusicAction | None = Field(
        default=None, description="Music command details, required if action='music'"
    )
    pc: PCAction | None = Field(
        default=None, description="PC command details, required if action='pc'"
    )
    learn: LearnAction | None = Field(
        default=None, description="Learning details, required if action='learn'"
    )
    message: str = Field(
        description="Human-readable message describing what was done or the answer"
    )

    @model_validator(mode="after")
    def validate_action_fields(self) -> ClawdiaResponse:
        if self.action == "ir" and self.ir is None:
            raise ValueError("'ir' field is required when action is 'ir'")
        if self.action == "music" and self.music is None:
            raise ValueError("'music' field is required when action is 'music'")
        if self.action == "pc" and self.pc is None:
            raise ValueError("'pc' field is required when action is 'pc'")
        if self.action == "learn" and self.learn is None:
            raise ValueError("'learn' field is required when action is 'learn'")
        return self
