import pytest
import base64
from unittest.mock import AsyncMock, patch, MagicMock

from clawdia.pc_agent.agent import ComputerUseAgent, AgentResult


@pytest.fixture
def agent():
    return ComputerUseAgent(
        api_key="test-key",
        model="claude-sonnet-4-6-20250514",
        max_iterations=5,
    )


def test_agent_init(agent):
    assert agent.max_iterations == 5
    assert agent.model == "claude-sonnet-4-6-20250514"


async def test_agent_done_on_first_iteration(agent):
    fake_screenshot = b"fake-png"
    mock_response = MagicMock()
    mock_response.content = [
        MagicMock(type="text", text="Goal achieved — Emby is playing."),
    ]
    mock_response.stop_reason = "end_turn"

    with patch.object(agent, "_take_screenshot", return_value=fake_screenshot):
        with patch.object(agent, "_call_api", return_value=mock_response):
            result = await agent.run("open emby", knowledge_context="")

    assert result.success is True
    assert "Emby" in result.summary


async def test_agent_max_iterations(agent):
    fake_screenshot = b"fake-png"
    mock_tool_use = MagicMock()
    mock_tool_use.type = "tool_use"
    mock_tool_use.name = "computer"
    mock_tool_use.id = "tool_1"
    mock_tool_use.input = {"action": "screenshot"}

    mock_response = MagicMock()
    mock_response.content = [mock_tool_use]
    mock_response.stop_reason = "tool_use"

    with patch.object(agent, "_take_screenshot", return_value=fake_screenshot):
        with patch.object(agent, "_call_api", return_value=mock_response):
            with patch.object(agent, "_execute_tool", return_value=fake_screenshot):
                result = await agent.run("impossible goal", knowledge_context="")

    assert result.success is False
    assert "max iterations" in result.summary.lower()


def test_agent_result_to_json():
    result = AgentResult(success=True, summary="Done")
    data = result.to_json()
    assert '"success": true' in data
    assert '"summary": "Done"' in data
