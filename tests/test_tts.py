from unittest.mock import AsyncMock, MagicMock, patch

from clawdia.voice.tts import TextToSpeech


async def test_synthesize():
    mock_audio_data = b"fake-mp3-data"

    with patch("clawdia.voice.tts.openai.AsyncOpenAI") as MockClient:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.read.return_value = mock_audio_data
        mock_client.audio.speech.create = AsyncMock(return_value=mock_response)
        MockClient.return_value = mock_client

        tts = TextToSpeech(api_key="test-key")
        result = await tts.synthesize("Hello world")

        assert result == mock_audio_data
        mock_client.audio.speech.create.assert_called_once_with(
            model="tts-1",
            voice="alloy",
            input="Hello world",
            response_format="wav",
        )


async def test_synthesize_custom_voice():
    with patch("clawdia.voice.tts.openai.AsyncOpenAI") as MockClient:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.read.return_value = b"data"
        mock_client.audio.speech.create = AsyncMock(return_value=mock_response)
        MockClient.return_value = mock_client

        tts = TextToSpeech(api_key="test-key", model="tts-1-hd", voice="nova")
        await tts.synthesize("Hi")

        call_kwargs = mock_client.audio.speech.create.call_args[1]
        assert call_kwargs["model"] == "tts-1-hd"
        assert call_kwargs["voice"] == "nova"


async def test_synthesize_failure_returns_empty():
    with patch("clawdia.voice.tts.openai.AsyncOpenAI") as MockClient:
        mock_client = AsyncMock()
        mock_client.audio.speech.create = AsyncMock(side_effect=Exception("API error"))
        MockClient.return_value = mock_client

        tts = TextToSpeech(api_key="test-key")
        result = await tts.synthesize("Hello")
        assert result == b""
