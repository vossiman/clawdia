import pytest
from clawdia.brain.models import ClawdiaResponse, IRAction


def test_ir_response():
    r = ClawdiaResponse(
        action="ir",
        ir=IRAction(command="power"),
        message="Turning off the TV",
    )
    assert r.action == "ir"
    assert r.ir.command == "power"
    assert r.message == "Turning off the TV"


def test_text_response():
    r = ClawdiaResponse(
        action="respond",
        message="The weather in Graz is 15 degrees.",
    )
    assert r.action == "respond"
    assert r.ir is None


def test_ir_response_requires_ir_field():
    with pytest.raises(Exception):
        ClawdiaResponse(action="ir", message="oops")
