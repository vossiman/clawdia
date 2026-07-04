import sys
import types
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


def test_single_frame_above_threshold_does_not_trigger_with_patience():
    """A lone high-scoring frame (e.g. a TV noise spike) must not trigger."""
    listener = WakeWordListener(threshold=0.5, patience=2)
    assert listener._should_trigger(0.9, now=1.0) is False


def test_consecutive_frames_trigger():
    """Sustained high scores across `patience` frames trigger exactly once."""
    listener = WakeWordListener(threshold=0.5, patience=2, cooldown=5.0)
    assert listener._should_trigger(0.9, now=1.0) is False
    assert listener._should_trigger(0.9, now=1.1) is True


def test_non_consecutive_frames_do_not_trigger():
    """A low-score frame resets the streak."""
    listener = WakeWordListener(threshold=0.5, patience=2)
    assert listener._should_trigger(0.9, now=1.0) is False
    assert listener._should_trigger(0.2, now=1.1) is False
    assert listener._should_trigger(0.9, now=1.2) is False


def test_patience_one_triggers_on_single_frame():
    listener = WakeWordListener(threshold=0.5, patience=1)
    assert listener._should_trigger(0.9, now=1.0) is True


def test_cooldown_blocks_retrigger():
    listener = WakeWordListener(threshold=0.5, patience=1, cooldown=5.0)
    assert listener._should_trigger(0.9, now=1.0) is True
    assert listener._should_trigger(0.9, now=2.0) is False
    assert listener._should_trigger(0.9, now=7.0) is True


def test_suppressed_blocks_and_resets_streak():
    """While suppressed nothing triggers, and the streak restarts afterwards."""
    listener = WakeWordListener(threshold=0.5, patience=2)
    listener._suppressed = True
    assert listener._should_trigger(0.9, now=1.0) is False
    assert listener._should_trigger(0.9, now=1.1) is False
    listener._suppressed = False
    assert listener._should_trigger(0.9, now=1.2) is False
    assert listener._should_trigger(0.9, now=1.3) is True


def test_vad_threshold_passed_to_model(monkeypatch):
    """_init_model forwards vad_threshold to the openwakeword Model."""
    captured: dict = {}

    class FakeModel:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    fake_module = types.ModuleType("openwakeword.model")
    fake_module.Model = FakeModel
    monkeypatch.setitem(sys.modules, "openwakeword.model", fake_module)

    listener = WakeWordListener(model_path="hey_jarvis_v0.1", vad_threshold=0.5)
    listener._init_model()

    assert captured["vad_threshold"] == 0.5
    assert captured["wakeword_models"] == ["hey_jarvis_v0.1"]


def _fake_oww(monkeypatch) -> dict:
    captured: dict = {}

    class FakeModel:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    fake_module = types.ModuleType("openwakeword.model")
    fake_module.Model = FakeModel
    monkeypatch.setitem(sys.modules, "openwakeword.model", fake_module)
    return captured


def test_verifier_model_passed_to_model(monkeypatch):
    """A configured verifier model is passed to openwakeword keyed by model name."""
    captured = _fake_oww(monkeypatch)

    listener = WakeWordListener(
        model_path="hey_jarvis_v0.1",
        verifier_model="/data/models/verifier.pkl",
        verifier_threshold=0.3,
    )
    listener._init_model()

    assert captured["custom_verifier_models"] == {"hey_jarvis_v0.1": "/data/models/verifier.pkl"}
    assert captured["custom_verifier_threshold"] == 0.3


def test_no_verifier_kwargs_when_unconfigured(monkeypatch):
    """Without a verifier model, openwakeword gets no verifier kwargs."""
    captured = _fake_oww(monkeypatch)

    listener = WakeWordListener(model_path="hey_jarvis_v0.1")
    listener._init_model()

    assert "custom_verifier_models" not in captured
    assert "custom_verifier_threshold" not in captured


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
