from unittest.mock import MagicMock

from clawdia.brain.agent import build_system_prompt


def test_system_prompt_includes_playback_state():
    ir = MagicMock()
    ir.list_commands_with_descriptions.return_value = []
    music = MagicMock()
    result = build_system_prompt(ir=ir, music=music, playback_state="Currently playing: Jazz by Miles (spotify:123, since 2 min ago)")
    assert "Currently playing: Jazz by Miles" in result


def test_system_prompt_nothing_playing():
    ir = MagicMock()
    ir.list_commands_with_descriptions.return_value = []
    music = MagicMock()
    result = build_system_prompt(ir=ir, music=music, playback_state="Nothing is currently playing.")
    assert "Nothing is currently playing." in result


def test_system_prompt_no_playback_state():
    ir = MagicMock()
    ir.list_commands_with_descriptions.return_value = []
    result = build_system_prompt(ir=ir, music=None)
    assert "Nothing is currently playing." not in result
    assert "Music playback is not currently configured." in result
