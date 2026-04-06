from unittest.mock import AsyncMock


async def test_voice_reply_sends_to_telegram_when_enabled():
    """Test that voice_reply sends to Telegram when voice_response_telegram is True."""
    from clawdia.voice.player import AudioPlayer
    from clawdia.voice.tts import TextToSpeech

    telegram = AsyncMock()
    tts = AsyncMock(spec=TextToSpeech)
    player = AsyncMock(spec=AudioPlayer)
    music = AsyncMock()

    tts.synthesize = AsyncMock(return_value=b"audio-data")

    from clawdia.voice.pipeline import make_voice_reply

    reply = make_voice_reply(
        telegram=telegram,
        tts=tts,
        player=player,
        music=music,
        response_telegram=True,
        response_tts=False,
    )
    await reply("Hello there")

    telegram.notify.assert_called_once_with("\U0001f399 Hello there")
    tts.synthesize.assert_not_called()


async def test_voice_reply_speaks_when_enabled():
    """Test that voice_reply synthesizes and plays TTS when voice_response_tts is True."""
    from clawdia.voice.player import AudioPlayer
    from clawdia.voice.tts import TextToSpeech

    telegram = AsyncMock()
    tts = AsyncMock(spec=TextToSpeech)
    player = AsyncMock(spec=AudioPlayer)
    music = AsyncMock()

    tts.synthesize = AsyncMock(return_value=b"audio-data")

    from clawdia.voice.pipeline import make_voice_reply

    reply = make_voice_reply(
        telegram=telegram,
        tts=tts,
        player=player,
        music=music,
        response_telegram=False,
        response_tts=True,
    )
    await reply("Hello there")

    tts.synthesize.assert_called_once_with("Hello there")
    player.play_bytes.assert_called_once_with(b"audio-data", suffix=".wav")
    telegram.notify.assert_not_called()


async def test_voice_reply_ducks_spotify():
    """Test that Spotify is paused before TTS and resumed after."""
    from clawdia.voice.player import AudioPlayer
    from clawdia.voice.tts import TextToSpeech

    telegram = AsyncMock()
    tts = AsyncMock(spec=TextToSpeech)
    player = AsyncMock(spec=AudioPlayer)
    music = AsyncMock()

    tts.synthesize = AsyncMock(return_value=b"audio-data")

    call_order = []
    music.pause = AsyncMock(side_effect=lambda: call_order.append("pause"))
    music.play = AsyncMock(side_effect=lambda: call_order.append("resume"))
    player.play_bytes = AsyncMock(side_effect=lambda *a, **kw: call_order.append("play"))

    from clawdia.voice.pipeline import make_voice_reply

    reply = make_voice_reply(
        telegram=telegram,
        tts=tts,
        player=player,
        music=music,
        response_telegram=False,
        response_tts=True,
    )
    await reply("Playing jazz")

    assert call_order == ["pause", "play", "resume"]


async def test_voice_reply_no_duck_without_music():
    """Test that TTS works without a music controller (no ducking)."""
    from clawdia.voice.player import AudioPlayer
    from clawdia.voice.tts import TextToSpeech

    telegram = AsyncMock()
    tts = AsyncMock(spec=TextToSpeech)
    player = AsyncMock(spec=AudioPlayer)

    tts.synthesize = AsyncMock(return_value=b"audio-data")

    from clawdia.voice.pipeline import make_voice_reply

    reply = make_voice_reply(
        telegram=telegram,
        tts=tts,
        player=player,
        music=None,
        response_telegram=False,
        response_tts=True,
    )
    await reply("Hello")

    tts.synthesize.assert_called_once()
    player.play_bytes.assert_called_once()


async def test_voice_reply_tts_failure_falls_back_to_telegram():
    """Test that TTS failure sends the message to Telegram instead."""
    from clawdia.voice.player import AudioPlayer
    from clawdia.voice.tts import TextToSpeech

    telegram = AsyncMock()
    tts = AsyncMock(spec=TextToSpeech)
    player = AsyncMock(spec=AudioPlayer)

    tts.synthesize = AsyncMock(return_value=b"")  # failure returns empty

    from clawdia.voice.pipeline import make_voice_reply

    reply = make_voice_reply(
        telegram=telegram,
        tts=tts,
        player=player,
        music=None,
        response_telegram=True,
        response_tts=True,
    )
    await reply("Hello")

    # TTS failed, should not play
    player.play_bytes.assert_not_called()
    # Should still send to telegram
    telegram.notify.assert_called_once()


async def test_on_error_plays_error_sound_and_notifies():
    """Test that the error callback plays error.wav and notifies Telegram."""
    from clawdia.voice.pipeline import make_on_error

    telegram = AsyncMock()
    player = AsyncMock()

    on_error = make_on_error(telegram=telegram, player=player, error_sound="/path/error.wav")
    await on_error()

    player.play_file.assert_called_once_with("/path/error.wav")
    telegram.notify.assert_called_once()
    assert "not understood" in telegram.notify.call_args[0][0].lower()
