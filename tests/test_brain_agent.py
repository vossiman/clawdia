import pytest
from pydantic_ai.models.test import TestModel

from clawdia.brain.agent import create_agent
from clawdia.brain.models import ClawdiaResponse


@pytest.fixture
def agent():
    return create_agent(model="test")


async def test_agent_returns_structured_response(agent):
    with agent.override(model=TestModel(custom_output_args={
        "action": "ir",
        "ir": {"command": "power"},
        "message": "Turning off the TV",
    })):
        result = await agent.run("Turn off the TV")
        assert isinstance(result.output, ClawdiaResponse)
        assert result.output.action == "ir"
        assert result.output.ir.command == "power"


async def test_agent_text_response(agent):
    with agent.override(model=TestModel(custom_output_args={
        "action": "respond",
        "message": "It is 15 degrees in Graz.",
    })):
        result = await agent.run("What's the weather?")
        assert result.output.action == "respond"
        assert "15 degrees" in result.output.message
