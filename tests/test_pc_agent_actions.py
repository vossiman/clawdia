import pytest
from unittest.mock import AsyncMock, patch

from clawdia.pc_agent.actions import (
    take_screenshot,
    click,
    type_text,
    press_key,
    ActionResult,
)


async def test_take_screenshot():
    mock_process = AsyncMock()
    mock_process.communicate.return_value = (b"", b"")
    mock_process.returncode = 0

    with patch("asyncio.create_subprocess_exec", return_value=mock_process):
        with patch("pathlib.Path.read_bytes", return_value=b"fake-png-data"):
            result = await take_screenshot()

    assert result.success is True
    assert result.data == b"fake-png-data"


async def test_click():
    mock_process = AsyncMock()
    mock_process.communicate.return_value = (b"", b"")
    mock_process.returncode = 0

    with patch("asyncio.create_subprocess_exec", return_value=mock_process) as mock_exec:
        result = await click(100, 200)

    assert result.success is True
    calls = mock_exec.call_args_list
    all_args = " ".join(str(c) for c in calls)
    assert "mousemove" in all_args
    assert "100" in all_args
    assert "200" in all_args


async def test_type_text():
    mock_process = AsyncMock()
    mock_process.communicate.return_value = (b"", b"")
    mock_process.returncode = 0

    with patch("asyncio.create_subprocess_exec", return_value=mock_process) as mock_exec:
        result = await type_text("hello world")

    assert result.success is True
    all_args = " ".join(str(c) for c in mock_exec.call_args_list)
    assert "hello world" in all_args


async def test_press_key():
    mock_process = AsyncMock()
    mock_process.communicate.return_value = (b"", b"")
    mock_process.returncode = 0

    with patch("asyncio.create_subprocess_exec", return_value=mock_process) as mock_exec:
        result = await press_key("ctrl+t")

    assert result.success is True
    all_args = " ".join(str(c) for c in mock_exec.call_args_list)
    assert "ctrl+t" in all_args


async def test_take_screenshot_failure():
    mock_process = AsyncMock()
    mock_process.communicate.return_value = (b"", b"scrot: error")
    mock_process.returncode = 1

    with patch("asyncio.create_subprocess_exec", return_value=mock_process):
        result = await take_screenshot()

    assert result.success is False
