from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from clawdia.telegram_bot.bot import ClawdiaTelegramBot


@pytest.fixture
def bot():
    b = ClawdiaTelegramBot(
        token="test-token",
        chat_id=12345,
        brain=AsyncMock(),
        ir=MagicMock(),
        music=AsyncMock(),
    )
    return b


def _make_update(text, chat_id=12345, args=None):
    update = MagicMock()
    update.message.text = text
    update.effective_chat.id = chat_id
    update.message.reply_text = AsyncMock()
    context = MagicMock()
    context.args = args or []
    return update, context


async def test_play_command(bot):
    bot.music.play_query.return_value = "Now playing: Song by Artist"
    update, context = _make_update("/play jazz", args=["jazz"])
    await bot._handle_play(update, context)
    bot.music.play_query.assert_called_once_with("jazz")
    update.message.reply_text.assert_called_once_with("Now playing: Song by Artist")


async def test_play_no_query(bot):
    bot.music.play.return_value = "Resuming playback."
    update, context = _make_update("/play", args=[])
    await bot._handle_play(update, context)
    bot.music.play.assert_called_once()


async def test_pause_command(bot):
    bot.music.pause.return_value = "Playback paused."
    update, context = _make_update("/pause")
    await bot._handle_pause(update, context)
    bot.music.pause.assert_called_once()


async def test_skip_command(bot):
    bot.music.skip.return_value = "Skipped to next track."
    update, context = _make_update("/skip")
    await bot._handle_skip(update, context)
    bot.music.skip.assert_called_once()


async def test_prev_command(bot):
    bot.music.previous.return_value = "Back to previous track."
    update, context = _make_update("/prev")
    await bot._handle_prev(update, context)
    bot.music.previous.assert_called_once()


async def test_np_command(bot):
    bot.music.now_playing.return_value = "Playing: Song by Artist (Album)"
    update, context = _make_update("/np")
    await bot._handle_np(update, context)
    bot.music.now_playing.assert_called_once()


async def test_vol_command(bot):
    bot.music.volume.return_value = "Volume set to 75%."
    update, context = _make_update("/vol 75", args=["75"])
    await bot._handle_vol(update, context)
    bot.music.volume.assert_called_once_with(75)


async def test_vol_no_arg(bot):
    update, context = _make_update("/vol", args=[])
    await bot._handle_vol(update, context)
    bot.music.volume.assert_not_called()
    update.message.reply_text.assert_called_once()
    assert "usage" in update.message.reply_text.call_args[0][0].lower()


async def test_playlist_command(bot):
    bot.music.play_playlist.return_value = "Now playing playlist: Chill Mix"
    update, context = _make_update("/playlist chill", args=["chill"])
    await bot._handle_playlist(update, context)
    bot.music.play_playlist.assert_called_once_with("chill")


async def test_queue_command(bot):
    bot.music.queue_track.return_value = "Added to queue: Song by Artist"
    update, context = _make_update("/queue jazz song", args=["jazz", "song"])
    await bot._handle_queue(update, context)
    bot.music.queue_track.assert_called_once_with("jazz song")


async def test_playlists_command(bot):
    bot.music.list_playlists.return_value = [
        {"name": "Playlist A", "uri": "spotify:playlist:a"},
        {"name": "Playlist B", "uri": "spotify:playlist:b"},
    ]
    update, context = _make_update("/playlists")
    await bot._handle_playlists(update, context)
    update.message.reply_text.assert_called_once()
    text = update.message.reply_text.call_args[0][0]
    assert "Playlist A" in text
    assert "Playlist B" in text


async def test_music_command_no_controller():
    bot = ClawdiaTelegramBot(
        token="test-token",
        chat_id=12345,
        brain=AsyncMock(),
    )
    update, context = _make_update("/play jazz", args=["jazz"])
    await bot._handle_play(update, context)
    assert "not configured" in update.message.reply_text.call_args[0][0].lower()
