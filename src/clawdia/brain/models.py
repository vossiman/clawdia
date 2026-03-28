from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class IRAction(BaseModel):
    """An IR command to send to the TV."""
    command: str = Field(description="IR command name, e.g. 'power', 'vol_up', 'channel_3'")
    repeat: int = Field(default=1, description="Number of times to send the command", ge=1, le=10)


class ClawdiaResponse(BaseModel):
    """Structured response from the Clawdia brain."""
    action: Literal["ir", "respond"] = Field(
        description="'ir' to send an IR command, 'respond' to reply with text"
    )
    ir: IRAction | None = Field(
        default=None, description="IR command details, required if action='ir'"
    )
    message: str = Field(
        description="Human-readable message describing what was done or the answer"
    )

    @model_validator(mode="after")
    def ir_required_for_ir_action(self) -> ClawdiaResponse:
        if self.action == "ir" and self.ir is None:
            raise ValueError("'ir' field is required when action is 'ir'")
        return self
