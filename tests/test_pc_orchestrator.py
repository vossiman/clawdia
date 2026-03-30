import pytest
from unittest.mock import AsyncMock, MagicMock

from clawdia.brain.models import ClawdiaResponse, PCAction, LearnAction
from clawdia.orchestrator import Orchestrator
from clawdia.pc.controller import PCResult


@pytest.fixture
def mock_brain():
    return AsyncMock()


@pytest.fixture
def mock_ir():
    ir = MagicMock()
    ir.has_command.return_value = True
    ir.send = AsyncMock(return_value=True)
    return ir


@pytest.fixture
def mock_telegram():
    return AsyncMock()


@pytest.fixture
def mock_pc():
    pc = AsyncMock()
    pc.run_shell = AsyncMock(return_value=PCResult(success=True, output="ok"))
    pc.run_computer_use = AsyncMock(return_value=PCResult(success=True, output="done"))
    return pc


@pytest.fixture
def mock_knowledge():
    kb = MagicMock()
    kb.to_prompt_context.return_value = "browser: firefox"
    return kb


@pytest.fixture
def orchestrator(mock_brain, mock_ir, mock_telegram, mock_pc, mock_knowledge):
    return Orchestrator(
        brain=mock_brain, ir=mock_ir, telegram=mock_telegram,
        pc=mock_pc, knowledge=mock_knowledge,
    )


async def test_handle_pc_shell_command(orchestrator, mock_brain, mock_pc, mock_telegram):
    response = ClawdiaResponse(
        action="pc",
        pc=PCAction(command_type="shell", shell_command="firefox http://emby:8096"),
        message="Opening Emby in Firefox",
    )
    mock_brain.process.return_value = response

    await orchestrator.handle_text_command("open emby")

    mock_pc.run_shell.assert_called_once_with("firefox http://emby:8096")
    mock_telegram.notify.assert_called_once_with("Opening Emby in Firefox")


async def test_handle_pc_shell_failure(orchestrator, mock_brain, mock_pc, mock_telegram):
    response = ClawdiaResponse(
        action="pc",
        pc=PCAction(command_type="shell", shell_command="badcmd"),
        message="Running command",
    )
    mock_brain.process.return_value = response
    mock_pc.run_shell.return_value = PCResult(success=False, output="command not found")

    await orchestrator.handle_text_command("run bad thing")

    mock_telegram.notify.assert_called_once()
    assert "failed" in mock_telegram.notify.call_args[0][0].lower()


async def test_handle_pc_computer_use(orchestrator, mock_brain, mock_pc, mock_telegram, mock_knowledge):
    response = ClawdiaResponse(
        action="pc",
        pc=PCAction(command_type="computer_use", goal="play Stranger Things"),
        message="Navigating Emby",
    )
    mock_brain.process.return_value = response

    await orchestrator.handle_text_command("play stranger things on emby")

    mock_pc.run_computer_use.assert_called_once_with("play Stranger Things", "browser: firefox")
    mock_telegram.notify.assert_called()


async def test_handle_learn_action(orchestrator, mock_brain, mock_telegram, mock_knowledge):
    response = ClawdiaResponse(
        action="learn",
        learn=LearnAction(section="services", key="emby", value={"url": "http://192.168.1.50:8096"}),
        message="Got it, I'll remember that Emby is at 192.168.1.50:8096",
    )
    mock_brain.process.return_value = response

    await orchestrator.handle_text_command("emby is at 192.168.1.50:8096")

    mock_knowledge.update.assert_called_once_with("services", "emby", {"url": "http://192.168.1.50:8096"})
    mock_brain.reload_commands.assert_called_once()
    mock_telegram.notify.assert_called_once_with("Got it, I'll remember that Emby is at 192.168.1.50:8096")


async def test_handle_pc_without_controller(mock_brain, mock_ir, mock_telegram):
    orchestrator = Orchestrator(brain=mock_brain, ir=mock_ir, telegram=mock_telegram)
    response = ClawdiaResponse(
        action="pc",
        pc=PCAction(command_type="shell", shell_command="echo hi"),
        message="hi",
    )
    mock_brain.process.return_value = response

    await orchestrator.handle_text_command("say hi on pc")

    mock_telegram.notify.assert_called_once()
    assert "not configured" in mock_telegram.notify.call_args[0][0].lower()
