import io
import wave
from unittest.mock import AsyncMock, MagicMock, patch

from clawdia.voice.stt import SpeechToText


def _make_wav_bytes(duration_s: float = 1.0, sample_rate: int = 16000) -> bytes:
    """Generate silent WAV bytes for testing."""
    n_samples = int(sample_rate * duration_s)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00\x00" * n_samples)
    return buf.getvalue()


async def test_transcribe():
    wav_bytes = _make_wav_bytes()

    mock_response = MagicMock()
    mock_response.text = "turn off the tv"

    with patch("clawdia.voice.stt.openai.AsyncOpenAI") as MockClient:
        mock_client = AsyncMock()
        mock_client.audio.transcriptions.create = AsyncMock(return_value=mock_response)
        MockClient.return_value = mock_client

        stt = SpeechToText(api_key="test-key")
        result = await stt.transcribe(wav_bytes)
        assert result == "turn off the tv"


def test_pcm_to_wav():
    """Test that raw PCM samples can be wrapped in WAV format."""
    stt = SpeechToText(api_key="test-key")
    pcm_data = b"\x00\x00" * 16000  # 1 second of silence
    wav_bytes = stt.pcm_to_wav(pcm_data)
    assert wav_bytes[:4] == b"RIFF"
