import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from clawdia.audio import AudioOutput


@pytest.fixture
def audio():
    return AudioOutput(max_volume=80, startup_volume=60, mic_volume=250)


def _mock_proc(returncode=0):
    proc = AsyncMock()
    proc.wait = AsyncMock(return_value=returncode)
    proc.returncode = returncode
    return proc


async def test_set_volume_passes_through_below_max(audio):
    with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
        mock_exec.return_value = _mock_proc()
        result = await audio.set_volume(50)

    mock_exec.assert_called_once_with(
        "pactl",
        "set-sink-volume",
        "@DEFAULT_SINK@",
        "50%",
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    assert result == "Volume set to 50%."


async def test_set_volume_clamps_to_max(audio):
    with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
        mock_exec.return_value = _mock_proc()
        result = await audio.set_volume(100)

    assert mock_exec.call_args[0][3] == "80%"
    assert result == "Volume set to 80% (max)."


async def test_set_volume_clamps_negative_to_zero(audio):
    with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
        mock_exec.return_value = _mock_proc()
        result = await audio.set_volume(-5)

    assert mock_exec.call_args[0][3] == "0%"
    assert result == "Volume set to 0%."


async def test_set_volume_reports_pactl_failure(audio):
    with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
        mock_exec.return_value = _mock_proc(returncode=1)
        result = await audio.set_volume(50)

    assert "Failed" in result


async def test_initialize_sets_mic_and_startup_volume(audio):
    with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
        mock_exec.return_value = _mock_proc()
        await audio.initialize()

    calls = [c[0] for c in mock_exec.call_args_list]
    assert ("pactl", "set-source-volume", "@DEFAULT_SOURCE@", "250%") == calls[0][:4]
    assert ("pactl", "set-sink-volume", "@DEFAULT_SINK@", "60%") == calls[1][:4]
