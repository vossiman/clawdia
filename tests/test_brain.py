from pydantic_ai.models.test import TestModel

from clawdia.brain import Brain
from clawdia.brain.models import ClawdiaResponse


async def test_brain_process_command():
    model = TestModel(custom_output_args={
        "action": "ir",
        "ir": {"command": "vol_up"},
        "message": "Turning volume up",
    })
    brain = Brain(model=model)
    response = await brain.process("Turn the volume up")
    assert isinstance(response, ClawdiaResponse)
    assert response.action == "ir"
    assert response.ir.command == "vol_up"
