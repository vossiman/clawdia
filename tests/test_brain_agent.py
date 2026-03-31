import pytest
from unittest.mock import MagicMock
from pydantic_ai.models.test import TestModel

from clawdia.brain.agent import create_agent, build_system_prompt
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


def test_system_prompt_includes_music_section():
    ir = MagicMock()
    ir.list_commands_with_descriptions.return_value = []
    prompt = build_system_prompt(ir=ir, music=None)
    assert "music" in prompt.lower() or "Music" in prompt


def test_system_prompt_with_music_enabled():
    ir = MagicMock()
    ir.list_commands_with_descriptions.return_value = []
    music = MagicMock()
    prompt = build_system_prompt(ir=ir, music=music)
    assert 'action="music"' in prompt


def test_system_prompt_includes_pc_section_when_enabled():
    ir = MagicMock()
    ir.list_commands_with_descriptions.return_value = []
    prompt = build_system_prompt(ir=ir, pc_enabled=True, pc_knowledge="browser: firefox\nservices:\n  emby:\n    url: http://emby:8096")
    assert "PC Remote Control" in prompt
    assert "firefox" in prompt
    assert "emby" in prompt


def test_system_prompt_pc_disabled_when_no_knowledge():
    ir = MagicMock()
    ir.list_commands_with_descriptions.return_value = []
    prompt = build_system_prompt(ir=ir, pc_knowledge="")
    assert "not configured" in prompt.lower()


def test_system_prompt_includes_learn_action():
    ir = MagicMock()
    ir.list_commands_with_descriptions.return_value = []
    prompt = build_system_prompt(ir=ir, pc_enabled=True, pc_knowledge="browser: firefox")
    assert "learn" in prompt
    assert "correction" in prompt.lower()
