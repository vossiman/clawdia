import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from clawdia.voice.player import AudioPlayer


@pytest.fixture
def player():
    return AudioPlayer()


async def test_play_file(player):
    with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
        mock_proc = AsyncMock()
        mock_proc.wait = AsyncMock(return_value=0)
        mock_proc.returncode = 0
        mock_exec.return_value = mock_proc

        await player.play_file("/path/to/chime.wav")

        mock_exec.assert_called_once_with(
            "paplay",
            "/path/to/chime.wav",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )


async def test_play_bytes_writes_temp_and_plays(player):
    with (
        patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec,
        patch("tempfile.NamedTemporaryFile") as mock_tmp,
    ):
        mock_proc = AsyncMock()
        mock_proc.wait = AsyncMock(return_value=0)
        mock_proc.returncode = 0
        mock_exec.return_value = mock_proc

        mock_file = mock_tmp.return_value.__enter__.return_value
        mock_file.name = "/tmp/clawdia_tts.wav"

        await player.play_bytes(b"fake-wav-data", suffix=".wav")

        mock_file.write.assert_called_once_with(b"fake-wav-data")
        mock_file.flush.assert_called_once()
        mock_exec.assert_called_once_with(
            "paplay",
            "/tmp/clawdia_tts.wav",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )


async def test_play_file_logs_on_failure(player):
    with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
        mock_proc = AsyncMock()
        mock_proc.wait = AsyncMock(return_value=1)
        mock_proc.returncode = 1
        mock_exec.return_value = mock_proc

        # Should not raise, just log
        await player.play_file("/path/to/missing.wav")
