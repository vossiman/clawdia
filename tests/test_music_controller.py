import pytest
from unittest.mock import MagicMock, patch

from clawdia.music.controller import MusicController


@pytest.fixture
def mock_spotify():
    """Mock spotipy.Spotify client."""
    return MagicMock()


@pytest.fixture
def controller(mock_spotify):
    with patch("clawdia.music.controller.spotipy.Spotify", return_value=mock_spotify):
        with patch("clawdia.music.controller.SpotifyOAuth"):
            c = MusicController(
                client_id="test-id",
                client_secret="test-secret",
                redirect_uri="http://localhost:8888/callback",
                device_name="clawdia",
                cache_path="/tmp/test-cache",
            )
            c._sp = mock_spotify
            return c


def _device_list(name="clawdia"):
    return {"devices": [{"id": "dev123", "name": name, "is_active": True}]}


def _current_playback(track="Chill Vibes", artist="DJ Test"):
    return {
        "is_playing": True,
        "item": {
            "name": track,
            "artists": [{"name": artist}],
            "album": {"name": "Test Album"},
        },
    }


async def test_play_query(controller, mock_spotify):
    mock_spotify.devices.return_value = _device_list()
    mock_spotify.search.return_value = {
        "tracks": {"items": [{"uri": "spotify:track:123", "name": "Jazz Song", "artists": [{"name": "Artist"}]}]}
    }
    result = await controller.play_query("jazz")
    mock_spotify.start_playback.assert_called_once_with(device_id="dev123", uris=["spotify:track:123"])
    assert "Jazz Song" in result


async def test_pause(controller, mock_spotify):
    mock_spotify.devices.return_value = _device_list()
    result = await controller.pause()
    mock_spotify.pause_playback.assert_called_once_with(device_id="dev123")
    assert "pause" in result.lower()


async def test_skip(controller, mock_spotify):
    mock_spotify.devices.return_value = _device_list()
    result = await controller.skip()
    mock_spotify.next_track.assert_called_once_with(device_id="dev123")
    assert "skip" in result.lower()


async def test_previous(controller, mock_spotify):
    mock_spotify.devices.return_value = _device_list()
    result = await controller.previous()
    mock_spotify.previous_track.assert_called_once_with(device_id="dev123")
    assert "previous" in result.lower()


async def test_volume(controller, mock_spotify):
    mock_spotify.devices.return_value = _device_list()
    result = await controller.volume(75)
    mock_spotify.volume.assert_called_once_with(75, device_id="dev123")
    assert "75" in result


async def test_now_playing(controller, mock_spotify):
    mock_spotify.current_playback.return_value = _current_playback()
    result = await controller.now_playing()
    assert "Chill Vibes" in result
    assert "DJ Test" in result


async def test_now_playing_nothing(controller, mock_spotify):
    mock_spotify.current_playback.return_value = None
    result = await controller.now_playing()
    assert "nothing" in result.lower()


async def test_play_playlist(controller, mock_spotify):
    mock_spotify.devices.return_value = _device_list()
    mock_spotify.current_user_playlists.return_value = {
        "items": [{"name": "Chill Mix", "uri": "spotify:playlist:abc"}],
    }
    result = await controller.play_playlist("chill")
    mock_spotify.start_playback.assert_called_once_with(device_id="dev123", context_uri="spotify:playlist:abc")
    assert "Chill Mix" in result


async def test_play_playlist_not_found(controller, mock_spotify):
    mock_spotify.current_user_playlists.return_value = {"items": []}
    result = await controller.play_playlist("nonexistent")
    assert "not find" in result.lower() or "no playlist" in result.lower()


async def test_queue_track(controller, mock_spotify):
    mock_spotify.devices.return_value = _device_list()
    mock_spotify.search.return_value = {
        "tracks": {"items": [{"uri": "spotify:track:456", "name": "Queue Song", "artists": [{"name": "Artist"}]}]}
    }
    result = await controller.queue_track("queue song")
    mock_spotify.add_to_queue.assert_called_once_with("spotify:track:456", device_id="dev123")
    assert "Queue Song" in result


async def test_search(controller, mock_spotify):
    mock_spotify.search.return_value = {
        "tracks": {"items": [
            {"name": "Track 1", "artists": [{"name": "A1"}], "uri": "spotify:track:1"},
            {"name": "Track 2", "artists": [{"name": "A2"}], "uri": "spotify:track:2"},
        ]}
    }
    results = await controller.search("test")
    assert len(results) == 2
    assert results[0]["name"] == "Track 1"


async def test_list_playlists(controller, mock_spotify):
    mock_spotify.current_user_playlists.return_value = {
        "items": [
            {"name": "Playlist A", "uri": "spotify:playlist:a"},
            {"name": "Playlist B", "uri": "spotify:playlist:b"},
        ]
    }
    results = await controller.list_playlists()
    assert len(results) == 2
    assert results[0]["name"] == "Playlist A"


async def test_device_not_found(controller, mock_spotify):
    mock_spotify.devices.return_value = {"devices": []}
    result = await controller.play_query("test")
    assert "not found" in result.lower() or "offline" in result.lower()
    mock_spotify.start_playback.assert_not_called()


async def test_play_resume(controller, mock_spotify):
    mock_spotify.devices.return_value = _device_list()
    result = await controller.play()
    mock_spotify.start_playback.assert_called_once_with(device_id="dev123")
    assert "resum" in result.lower()


def _device_list_inactive(name="clawdia"):
    return {"devices": [{"id": "dev123", "name": name, "is_active": False}]}


async def test_play_retries_when_device_not_active(controller, mock_spotify):
    """When start_playback succeeds but device stays inactive, retry and report failure."""
    mock_spotify.devices.side_effect = [
        _device_list(),           # _get_device_id
        _device_list_inactive(),  # verify attempt 1
        _device_list_inactive(),  # retry: verify attempt 2
        _device_list_inactive(),  # retry: verify attempt 1
        _device_list_inactive(),  # retry: verify attempt 2
    ]
    result = await controller.play(uri="spotify:track:123")
    assert "did not start" in result.lower()
    assert mock_spotify.start_playback.call_count == 2


async def test_play_succeeds_on_retry(controller, mock_spotify):
    """When first play attempt fails but retry succeeds."""
    mock_spotify.devices.side_effect = [
        _device_list(),           # _get_device_id
        _device_list_inactive(),  # verify attempt 1
        _device_list_inactive(),  # verify attempt 2
        _device_list(),           # retry: verify attempt 1 — now active
    ]
    result = await controller.play(uri="spotify:track:123")
    assert "playing" in result.lower()
    assert mock_spotify.start_playback.call_count == 2
