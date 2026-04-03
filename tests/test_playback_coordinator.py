from unittest.mock import AsyncMock

import pytest

from clawdia.playback.coordinator import PlaybackCoordinator


@pytest.fixture
def coordinator():
    return PlaybackCoordinator()


async def test_play_sets_state(coordinator):
    callback = AsyncMock(return_value="Now playing: Jazz Song by Artist")
    result = await coordinator.play(
        service="spotify:123",
        source="telegram",
        user_chat_id=123,
        callback=callback,
        description="Jazz Song by Artist",
    )
    callback.assert_called_once()
    assert result == "Now playing: Jazz Song by Artist"
    assert coordinator.state is not None
    assert coordinator.state.service == "spotify:123"
    assert coordinator.state.description == "Jazz Song by Artist"
    assert coordinator.state.source == "telegram"
    assert coordinator.state.user_chat_id == 123


async def test_play_stops_previous_service(coordinator):
    stop_a = AsyncMock()
    stop_b = AsyncMock()
    coordinator.register_service("spotify:111", stop=stop_a)
    coordinator.register_service("spotify:222", stop=stop_b)

    await coordinator.play(
        service="spotify:111",
        source="telegram",
        user_chat_id=111,
        callback=AsyncMock(return_value="Playing A"),
        description="Song A",
    )
    stop_a.assert_not_called()

    await coordinator.play(
        service="spotify:222",
        source="telegram",
        user_chat_id=222,
        callback=AsyncMock(return_value="Playing B"),
        description="Song B",
    )
    stop_a.assert_called_once()
    stop_b.assert_not_called()
    assert coordinator.state.service == "spotify:222"


async def test_play_same_service_does_not_stop(coordinator):
    stop = AsyncMock()
    coordinator.register_service("spotify:123", stop=stop)

    await coordinator.play(
        service="spotify:123",
        source="telegram",
        user_chat_id=123,
        callback=AsyncMock(return_value="Playing A"),
        description="Song A",
    )
    await coordinator.play(
        service="spotify:123",
        source="telegram",
        user_chat_id=123,
        callback=AsyncMock(return_value="Playing B"),
        description="Song B",
    )
    stop.assert_not_called()
    assert coordinator.state.description == "Song B"


async def test_stop_clears_state(coordinator):
    coordinator.register_service("spotify:123", stop=AsyncMock())
    await coordinator.play(
        service="spotify:123",
        source="telegram",
        user_chat_id=123,
        callback=AsyncMock(return_value="Playing"),
        description="Song",
    )
    await coordinator.stop("spotify:123")
    assert coordinator.state is None


async def test_stop_wrong_service_keeps_state(coordinator):
    coordinator.register_service("spotify:123", stop=AsyncMock())
    coordinator.register_service("spotify:456", stop=AsyncMock())
    await coordinator.play(
        service="spotify:123",
        source="telegram",
        user_chat_id=123,
        callback=AsyncMock(return_value="Playing"),
        description="Song",
    )
    await coordinator.stop("spotify:456")
    assert coordinator.state is not None
    assert coordinator.state.service == "spotify:123"


async def test_get_state_for_prompt_nothing(coordinator):
    result = coordinator.get_state_for_prompt()
    assert result == "Nothing is currently playing."


async def test_get_state_for_prompt_playing(coordinator):
    await coordinator.play(
        service="spotify:123",
        source="telegram",
        user_chat_id=123,
        callback=AsyncMock(return_value="Playing"),
        description="No Surprises by Radiohead",
    )
    result = coordinator.get_state_for_prompt()
    assert "No Surprises by Radiohead" in result
    assert "spotify:123" in result


async def test_stop_callback_failure_does_not_block_play(coordinator):
    stop_a = AsyncMock(side_effect=Exception("API down"))
    coordinator.register_service("spotify:111", stop=stop_a)

    await coordinator.play(
        service="spotify:111",
        source="telegram",
        user_chat_id=111,
        callback=AsyncMock(return_value="Playing A"),
        description="Song A",
    )

    callback_b = AsyncMock(return_value="Playing B")
    result = await coordinator.play(
        service="spotify:222",
        source="voice",
        user_chat_id=None,
        callback=callback_b,
        description="Song B",
    )
    callback_b.assert_called_once()
    assert result == "Playing B"
    assert coordinator.state.service == "spotify:222"


async def test_play_with_voice_source(coordinator):
    await coordinator.play(
        service="spotify:123",
        source="voice",
        user_chat_id=None,
        callback=AsyncMock(return_value="Playing"),
        description="Some song",
    )
    assert coordinator.state.source == "voice"
    assert coordinator.state.user_chat_id is None
