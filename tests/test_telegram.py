from unittest.mock import AsyncMock, patch

from clawdia.telegram_bot.bot import ClawdiaTelegramBot


def test_bot_initialization():
    bot = ClawdiaTelegramBot(
        token="test-token",
        chat_ids={12345},
        brain=AsyncMock(),
    )
    assert 12345 in bot.chat_ids
    assert bot.brain is not None


async def test_notify():
    bot = ClawdiaTelegramBot(
        token="test-token",
        chat_ids={12345},
        brain=AsyncMock(),
    )
    with patch.object(bot, "_bot") as mock_bot:
        mock_bot.send_message = AsyncMock()
        await bot.notify("Test message")
        mock_bot.send_message.assert_called_once_with(chat_id=12345, text="Test message")
