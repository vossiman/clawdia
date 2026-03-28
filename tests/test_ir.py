import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from clawdia.ir.controller import IRController


@pytest.fixture
def ir_codes_dir(tmp_path):
    codes_dir = tmp_path / "ir-codes"
    codes_dir.mkdir()
    (codes_dir / "power.txt").write_text("+889 -889 +1778 -1778\n")
    (codes_dir / "vol_up.txt").write_text("+889 -889 +889 -889\n")
    return codes_dir


@pytest.fixture
def controller(ir_codes_dir):
    return IRController(
        device_send="/dev/lirc0",
        codes_dir=str(ir_codes_dir),
    )


def test_list_commands(controller):
    commands = controller.list_commands()
    assert "power" in commands
    assert "vol_up" in commands


def test_has_command(controller):
    assert controller.has_command("power") is True
    assert controller.has_command("nonexistent") is False


async def test_send_command(controller):
    with patch("clawdia.ir.controller.asyncio") as mock_asyncio:
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"", b""))
        mock_asyncio.create_subprocess_exec = AsyncMock(return_value=mock_process)
        mock_asyncio.subprocess = __import__("asyncio").subprocess

        result = await controller.send(command="power")
        assert result is True

        mock_asyncio.create_subprocess_exec.assert_called_once()
        call_args = mock_asyncio.create_subprocess_exec.call_args[0]
        assert "ir-ctl" in call_args
        assert "--send" in " ".join(str(a) for a in call_args)


async def test_send_unknown_command(controller):
    result = await controller.send(command="nonexistent")
    assert result is False
