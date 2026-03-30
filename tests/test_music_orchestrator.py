from unittest.mock import AsyncMock, MagicMock

from clawdia.brain.models import ClawdiaResponse, MusicAction
from clawdia.orchestrator import Orchestrator


async def test_handle_music_play_query():
    mock_brain = AsyncMock()
    mock_ir = MagicMock()
    mock_telegram = AsyncMock()
    mock_music = AsyncMock()
    mock_music.play_query.return_value = "Now playing: Jazz Song by Artist"

    response = ClawdiaResponse(
        action="music",
        music=MusicAction(command="play_query", query="jazz"),
        message="Playing jazz for you",
    )
    mock_brain.process.return_value = response

    orch = Orchestrator(brain=mock_brain, ir=mock_ir, telegram=mock_telegram, music=mock_music)
    await orch.handle_text_command("play some jazz")

    mock_music.play_query.assert_called_once_with("jazz")
    mock_telegram.notify.assert_called_once_with("Now playing: Jazz Song by Artist")


async def test_handle_music_pause():
    mock_brain = AsyncMock()
    mock_ir = MagicMock()
    mock_telegram = AsyncMock()
    mock_music = AsyncMock()
    mock_music.pause.return_value = "Playback paused."

    response = ClawdiaResponse(
        action="music",
        music=MusicAction(command="pause"),
        message="Pausing music",
    )
    mock_brain.process.return_value = response

    orch = Orchestrator(brain=mock_brain, ir=mock_ir, telegram=mock_telegram, music=mock_music)
    await orch.handle_text_command("pause the music")

    mock_music.pause.assert_called_once()
    mock_telegram.notify.assert_called_once_with("Playback paused.")


async def test_handle_music_volume():
    mock_brain = AsyncMock()
    mock_ir = MagicMock()
    mock_telegram = AsyncMock()
    mock_music = AsyncMock()
    mock_music.volume.return_value = "Volume set to 50%."

    response = ClawdiaResponse(
        action="music",
        music=MusicAction(command="volume", volume=50),
        message="Setting volume",
    )
    mock_brain.process.return_value = response

    orch = Orchestrator(brain=mock_brain, ir=mock_ir, telegram=mock_telegram, music=mock_music)
    await orch.handle_text_command("set volume to 50")

    mock_music.volume.assert_called_once_with(50)


async def test_handle_music_no_controller():
    mock_brain = AsyncMock()
    mock_ir = MagicMock()
    mock_telegram = AsyncMock()

    response = ClawdiaResponse(
        action="music",
        music=MusicAction(command="pause"),
        message="Pausing",
    )
    mock_brain.process.return_value = response

    orch = Orchestrator(brain=mock_brain, ir=mock_ir, telegram=mock_telegram)
    await orch.handle_text_command("pause")

    mock_telegram.notify.assert_called_once()
    assert "not configured" in mock_telegram.notify.call_args[0][0].lower()


async def test_ir_still_works_with_music():
    mock_brain = AsyncMock()
    mock_ir = MagicMock()
    mock_ir.has_command.return_value = True
    mock_ir.send = AsyncMock(return_value=True)
    mock_telegram = AsyncMock()
    mock_music = AsyncMock()

    from clawdia.brain.models import IRAction
    response = ClawdiaResponse(
        action="ir",
        ir=IRAction(command="power"),
        message="Turning off TV",
    )
    mock_brain.process.return_value = response

    orch = Orchestrator(brain=mock_brain, ir=mock_ir, telegram=mock_telegram, music=mock_music)
    await orch.handle_text_command("turn off the TV")

    mock_ir.send.assert_called_once()
    mock_music.play_query.assert_not_called()
