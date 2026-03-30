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


class ClawdiaResponse(BaseModel):
    """Structured response from the Clawdia brain."""
    action: Literal["ir", "respond", "music"] = Field(
        description="'ir' to send an IR command, 'respond' to reply with text, 'music' to control music"
    )
    ir: IRAction | None = Field(
        default=None, description="IR command details, required if action='ir'"
    )
    music: MusicAction | None = Field(
        default=None, description="Music command details, required if action='music'"
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
        return self
