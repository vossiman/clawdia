from unittest.mock import AsyncMock, MagicMock

import pytest

from clawdia.brain.models import ClawdiaResponse, IRAction
from clawdia.orchestrator import Orchestrator


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
def orchestrator(mock_brain, mock_ir, mock_telegram):
    return Orchestrator(brain=mock_brain, ir=mock_ir, telegram=mock_telegram)


async def test_handle_ir_command(orchestrator, mock_brain, mock_ir, mock_telegram):
    response = ClawdiaResponse(
        action="ir",
        ir=IRAction(command="power"),
        message="Turning off the TV",
    )
    mock_brain.process.return_value = response

    await orchestrator.handle_text_command("Turn off the TV")

    mock_brain.process.assert_called_once_with("Turn off the TV", context_id="default")
    mock_ir.send.assert_called_once_with(command="power", repeat=1)
    mock_telegram.notify.assert_called_once_with("Turning off the TV")


async def test_handle_text_response(orchestrator, mock_brain, mock_ir, mock_telegram):
    response = ClawdiaResponse(
        action="respond",
        message="It's 15 degrees in Graz.",
    )
    mock_brain.process.return_value = response

    await orchestrator.handle_text_command("What's the weather?")

    mock_brain.process.assert_called_once()
    mock_ir.send.assert_not_called()
    mock_telegram.notify.assert_called_once_with("It's 15 degrees in Graz.")


async def test_handle_ir_command_unknown(orchestrator, mock_brain, mock_ir, mock_telegram):
    response = ClawdiaResponse(
        action="ir",
        ir=IRAction(command="nonexistent"),
        message="Sending command",
    )
    mock_brain.process.return_value = response
    mock_ir.has_command.return_value = False

    await orchestrator.handle_text_command("Do something weird")

    mock_ir.send.assert_not_called()
    assert mock_telegram.notify.call_count == 1
    assert "not available" in mock_telegram.notify.call_args[0][0].lower()


async def test_handle_audio_calls_stt_and_routes(orchestrator, mock_brain, mock_telegram):
    """Test that handle_audio transcribes and routes to handle_text_command."""
    mock_stt = AsyncMock()
    mock_stt.pcm_to_wav = MagicMock(return_value=b"wav-data")
    mock_stt.transcribe = AsyncMock(return_value="play some jazz")
    orchestrator.stt = mock_stt

    response = ClawdiaResponse(action="respond", message="Playing jazz")
    mock_brain.process.return_value = response

    await orchestrator.handle_audio(b"pcm-data")

    mock_stt.pcm_to_wav.assert_called_once_with(b"pcm-data")
    mock_stt.transcribe.assert_called_once_with(b"wav-data")
    mock_brain.process.assert_called_once()


async def test_handle_audio_empty_transcript_calls_on_error(orchestrator):
    """Test that empty STT triggers on_error callback."""
    mock_stt = AsyncMock()
    mock_stt.pcm_to_wav = MagicMock(return_value=b"wav-data")
    mock_stt.transcribe = AsyncMock(return_value="")
    orchestrator.stt = mock_stt

    on_error = AsyncMock()
    await orchestrator.handle_audio(b"pcm-data", on_error=on_error)

    on_error.assert_called_once()


async def test_handle_audio_stt_exception_calls_on_error(orchestrator):
    """Test that STT failure triggers on_error callback."""
    mock_stt = AsyncMock()
    mock_stt.pcm_to_wav = MagicMock(return_value=b"wav-data")
    mock_stt.transcribe = AsyncMock(side_effect=Exception("API timeout"))
    orchestrator.stt = mock_stt

    on_error = AsyncMock()
    await orchestrator.handle_audio(b"pcm-data", on_error=on_error)

    on_error.assert_called_once()


async def test_handle_audio_no_stt(orchestrator):
    """Test that handle_audio is a no-op without STT configured."""
    orchestrator.stt = None
    await orchestrator.handle_audio(b"pcm-data")
    # Should not raise
