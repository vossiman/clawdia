import pytest

from clawdia.brain.models import ClawdiaResponse, LearnAction, PCAction


def test_pc_shell_response():
    r = ClawdiaResponse(
        action="pc",
        pc=PCAction(command_type="shell", shell_command="firefox http://emby:8096"),
        message="Opening Emby in Firefox",
    )
    assert r.action == "pc"
    assert r.pc.command_type == "shell"
    assert r.pc.shell_command == "firefox http://emby:8096"
    assert r.pc.goal is None


def test_pc_computer_use_response():
    r = ClawdiaResponse(
        action="pc",
        pc=PCAction(command_type="computer_use", goal="navigate to TV Shows in Emby"),
        message="Navigating Emby",
    )
    assert r.pc.command_type == "computer_use"
    assert r.pc.goal == "navigate to TV Shows in Emby"
    assert r.pc.shell_command is None


def test_pc_response_requires_pc_field():
    with pytest.raises(Exception):
        ClawdiaResponse(action="pc", message="oops")


def test_learn_response():
    r = ClawdiaResponse(
        action="learn",
        learn=LearnAction(
            section="services",
            key="emby",
            value={"url": "http://192.168.1.50:8096"},
        ),
        message="Got it, I'll remember that.",
    )
    assert r.action == "learn"
    assert r.learn.section == "services"
    assert r.learn.key == "emby"


def test_learn_response_requires_learn_field():
    with pytest.raises(Exception):
        ClawdiaResponse(action="learn", message="oops")


def test_existing_ir_response_still_works():
    from clawdia.brain.models import IRAction

    r = ClawdiaResponse(
        action="ir",
        ir=IRAction(command="power"),
        message="Turning off the TV",
    )
    assert r.action == "ir"


def test_existing_respond_still_works():
    r = ClawdiaResponse(action="respond", message="Hello!")
    assert r.action == "respond"
