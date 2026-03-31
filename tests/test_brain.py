from pydantic_ai.models.test import TestModel

from clawdia.brain import Brain
from clawdia.brain.models import ClawdiaResponse

# PydanticAI structured output produces 3 messages per exchange:
# 1. ModelRequest (user prompt)
# 2. ModelResponse (tool call for final_result)
# 3. ModelRequest (tool return confirmation)
MSGS_PER_EXCHANGE = 3


async def test_brain_process_command():
    model = TestModel(custom_output_args={
        "action": "ir",
        "ir": {"command": "vol_up"},
        "message": "Turning volume up",
    })
    brain = Brain(model=model)
    response = await brain.process("Turn the volume up")
    assert isinstance(response, ClawdiaResponse)
    assert response.action == "ir"
    assert response.ir.command == "vol_up"


async def test_brain_history_accumulates():
    model = TestModel(custom_output_args={
        "action": "respond",
        "message": "Hello!",
    })
    brain = Brain(model=model)
    await brain.process("Hi", context_id="user1")
    assert len(brain._history["user1"]) == MSGS_PER_EXCHANGE

    await brain.process("How are you?", context_id="user1")
    assert len(brain._history["user1"]) == MSGS_PER_EXCHANGE * 2


async def test_brain_history_context_isolation():
    model = TestModel(custom_output_args={
        "action": "respond",
        "message": "Hi!",
    })
    brain = Brain(model=model)
    await brain.process("Hello", context_id="user1")
    await brain.process("Hey", context_id="user2")

    assert "user1" in brain._history
    assert "user2" in brain._history
    assert len(brain._history["user1"]) == MSGS_PER_EXCHANGE
    assert len(brain._history["user2"]) == MSGS_PER_EXCHANGE


async def test_brain_history_trimmed_to_3_exchanges():
    model = TestModel(custom_output_args={
        "action": "respond",
        "message": "Ok",
    })
    brain = Brain(model=model)
    for i in range(5):
        await brain.process(f"Message {i}", context_id="test")

    # 5 exchanges stored in full
    assert len(brain._history["test"]) == MSGS_PER_EXCHANGE * 5
    # Trimmed returns only last 3 exchanges
    trimmed = brain._trimmed_history("test")
    assert len(trimmed) == MSGS_PER_EXCHANGE * 3


async def test_brain_default_context_id():
    model = TestModel(custom_output_args={
        "action": "respond",
        "message": "Hi!",
    })
    brain = Brain(model=model)
    await brain.process("Hello")
    assert "default" in brain._history
    assert len(brain._history["default"]) == MSGS_PER_EXCHANGE
