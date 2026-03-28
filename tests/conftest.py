import pytest
from clawdia.config import Settings


@pytest.fixture
def test_settings():
    """Settings with test/dummy values."""
    return Settings(
        openrouter_api_key="test-key",
        openai_api_key="test-key",
        telegram_bot_token="test-token",
        telegram_chat_id=12345,
        ir_codes_dir="/tmp/test-ir-codes",
        debug=True,
    )
