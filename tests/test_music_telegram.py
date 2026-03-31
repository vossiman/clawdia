from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from clawdia.telegram_bot.bot import ClawdiaTelegramBot


@pytest.fixture
def music_mock():
    return AsyncMock()


@pytest.fixture
def bot(music_mock):
    b = ClawdiaTelegramBot(
        token="test-token",
        chat_ids={12345},
        brain=AsyncMock(),
        ir=MagicMock(),
        music=music_mock,
        music_controllers={12345: music_mock},
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


async def test_play_command(bot, music_mock):
    music_mock.play_query.return_value = "Now playing: Song by Artist"
    update, context = _make_update("/play jazz", args=["jazz"])
    await bot._handle_play(update, context)
    music_mock.play_query.assert_called_once_with("jazz")
    update.message.reply_text.assert_called_once_with("Now playing: Song by Artist")


async def test_play_no_query(bot, music_mock):
    music_mock.play.return_value = "Resuming playback."
    update, context = _make_update("/play", args=[])
    await bot._handle_play(update, context)
    music_mock.play.assert_called_once()


async def test_pause_command(bot, music_mock):
    music_mock.pause.return_value = "Playback paused."
    update, context = _make_update("/pause")
    await bot._handle_pause(update, context)
    music_mock.pause.assert_called_once()


async def test_skip_command(bot, music_mock):
    music_mock.skip.return_value = "Skipped to next track."
    update, context = _make_update("/skip")
    await bot._handle_skip(update, context)
    music_mock.skip.assert_called_once()


async def test_prev_command(bot, music_mock):
    music_mock.previous.return_value = "Back to previous track."
    update, context = _make_update("/prev")
    await bot._handle_prev(update, context)
    music_mock.previous.assert_called_once()


async def test_np_command(bot, music_mock):
    music_mock.now_playing.return_value = "Playing: Song by Artist (Album)"
    update, context = _make_update("/np")
    await bot._handle_np(update, context)
    music_mock.now_playing.assert_called_once()


async def test_vol_command(bot, music_mock):
    music_mock.volume.return_value = "Volume set to 75%."
    update, context = _make_update("/vol 75", args=["75"])
    await bot._handle_vol(update, context)
    music_mock.volume.assert_called_once_with(75)


async def test_vol_no_arg(bot, music_mock):
    update, context = _make_update("/vol", args=[])
    await bot._handle_vol(update, context)
    music_mock.volume.assert_not_called()
    update.message.reply_text.assert_called_once()
    assert "usage" in update.message.reply_text.call_args[0][0].lower()


async def test_playlist_command(bot, music_mock):
    music_mock.play_playlist.return_value = "Now playing playlist: Chill Mix"
    update, context = _make_update("/playlist chill", args=["chill"])
    await bot._handle_playlist(update, context)
    music_mock.play_playlist.assert_called_once_with("chill")


async def test_queue_command(bot, music_mock):
    music_mock.queue_track.return_value = "Added to queue: Song by Artist"
    update, context = _make_update("/queue jazz song", args=["jazz", "song"])
    await bot._handle_queue(update, context)
    music_mock.queue_track.assert_called_once_with("jazz song")


async def test_playlists_command(bot, music_mock):
    music_mock.list_playlists.return_value = [
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
        chat_ids={12345},
        brain=AsyncMock(),
    )
    update, context = _make_update("/play jazz", args=["jazz"])
    await bot._handle_play(update, context)
    assert "not configured" in update.message.reply_text.call_args[0][0].lower()


async def test_music_per_user_routing():
    """Each chat ID gets its own music controller."""
    music_a = AsyncMock()
    music_b = AsyncMock()
    music_a.play_query.return_value = "Playing A"
    music_b.play_query.return_value = "Playing B"

    bot = ClawdiaTelegramBot(
        token="test-token",
        chat_ids={111, 222},
        brain=AsyncMock(),
        music_controllers={111: music_a, 222: music_b},
    )

    update_a, ctx_a = _make_update("/play jazz", chat_id=111, args=["jazz"])
    await bot._handle_play(update_a, ctx_a)
    music_a.play_query.assert_called_once_with("jazz")
    music_b.play_query.assert_not_called()

    update_b, ctx_b = _make_update("/play rock", chat_id=222, args=["rock"])
    await bot._handle_play(update_b, ctx_b)
    music_b.play_query.assert_called_once_with("rock")


async def test_music_fallback_to_default():
    """Unknown chat ID falls back to default music controller."""
    default_music = AsyncMock()
    default_music.pause.return_value = "Paused."

    bot = ClawdiaTelegramBot(
        token="test-token",
        chat_ids={999},
        brain=AsyncMock(),
        music=default_music,
        music_controllers={111: AsyncMock()},
    )

    update, context = _make_update("/pause", chat_id=999)
    await bot._handle_pause(update, context)
    default_music.pause.assert_called_once()
