from unittest.mock import AsyncMock

from clawdia.voice.listener import WakeWordListener


def test_listener_init():
    listener = WakeWordListener(
        model_path="hey_jarvis",
        threshold=0.5,
        sample_rate=16000,
        chunk_size=1280,
    )
    assert listener.threshold == 0.5
    assert listener.sample_rate == 16000


async def test_listener_callback_called():
    """Test that the on_wake_word callback is invoked correctly."""
    callback = AsyncMock()
    listener = WakeWordListener(
        model_path="hey_jarvis",
        threshold=0.5,
        on_wake_word=callback,
    )
    await listener._on_detected()
    callback.assert_called_once()
