import pytest
from clawdia.brain.models import ClawdiaResponse, MusicAction


def test_music_action_play_query():
    action = MusicAction(command="play_query", query="chill jazz")
    assert action.command == "play_query"
    assert action.query == "chill jazz"
    assert action.volume is None


def test_music_action_volume():
    action = MusicAction(command="volume", volume=75)
    assert action.volume == 75


def test_music_action_pause():
    action = MusicAction(command="pause")
    assert action.command == "pause"
    assert action.query is None


def test_music_response():
    r = ClawdiaResponse(
        action="music",
        music=MusicAction(command="play_query", query="jazz"),
        message="Playing jazz",
    )
    assert r.action == "music"
    assert r.music.command == "play_query"
    assert r.music.query == "jazz"


def test_music_response_requires_music_field():
    with pytest.raises(Exception):
        ClawdiaResponse(action="music", message="oops")


def test_ir_response_still_works():
    from clawdia.brain.models import IRAction
    r = ClawdiaResponse(
        action="ir",
        ir=IRAction(command="power"),
        message="Turning off the TV",
    )
    assert r.action == "ir"
    assert r.ir.command == "power"
    assert r.music is None
