import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from clawdia.pc.controller import PCController


@pytest.fixture
def controller():
    return PCController(
        ssh_host="192.168.1.100",
        ssh_user="vossi",
        ssh_key_path="~/.ssh/id_ed25519",
        agent_path="~/clawdia-agent",
    )


def test_build_ssh_command(controller):
    cmd = controller._build_ssh_cmd("echo hello")
    joined = " ".join(cmd)
    assert "ssh" in cmd
    assert "-i" in cmd
    assert "~/.ssh/id_ed25519" in cmd
    assert "vossi@192.168.1.100" in cmd
    assert "echo hello" in joined


def test_build_ssh_command_includes_display(controller):
    cmd = controller._build_ssh_cmd("firefox http://emby:8096")
    joined = " ".join(cmd)
    assert "DISPLAY=:0" in joined


async def test_run_shell_command(controller):
    mock_process = AsyncMock()
    mock_process.communicate.return_value = (b"ok\n", b"")
    mock_process.returncode = 0

    with patch("asyncio.create_subprocess_exec", return_value=mock_process) as mock_exec:
        result = await controller.run_shell("echo hello")

    assert result.success is True
    assert result.output == "ok"
    mock_exec.assert_called_once()


async def test_run_shell_command_failure(controller):
    mock_process = AsyncMock()
    mock_process.communicate.return_value = (b"", b"error\n")
    mock_process.returncode = 1

    with patch("asyncio.create_subprocess_exec", return_value=mock_process):
        result = await controller.run_shell("bad command")

    assert result.success is False
    assert "error" in result.output


async def test_run_computer_use(controller):
    mock_process = AsyncMock()
    mock_process.communicate.return_value = (b'{"success": true, "summary": "done"}\n', b"")
    mock_process.returncode = 0

    with patch("asyncio.create_subprocess_exec", return_value=mock_process) as mock_exec:
        result = await controller.run_computer_use("navigate to TV shows", "browser: firefox")

    assert result.success is True
    assert result.output == "done"
    call_args = mock_exec.call_args[0]
    joined = " ".join(call_args)
    assert "pc_agent" in joined
    assert "navigate to TV shows" in joined
