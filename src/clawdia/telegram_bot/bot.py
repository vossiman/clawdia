from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import telegram
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

if TYPE_CHECKING:
    from clawdia.brain import Brain

logger = logging.getLogger(__name__)


class ClawdiaTelegramBot:
    """Telegram bot for Clawdia - receives commands, sends notifications."""

    def __init__(self, token: str, chat_id: int, brain: Brain):
        self.token = token
        self.chat_id = chat_id
        self.brain = brain
        self._bot = telegram.Bot(token=token)
        self._app: Application | None = None

    async def notify(self, text: str) -> None:
        """Send a notification message to the configured chat."""
        try:
            await self._bot.send_message(chat_id=self.chat_id, text=text)
        except Exception:
            logger.exception("Failed to send Telegram notification")

    def _build_app(self) -> Application:
        """Build the Telegram application with handlers."""
        app = Application.builder().token(self.token).build()
        app.add_handler(CommandHandler("start", self._handle_start))
        app.add_handler(CommandHandler("ir", self._handle_ir_list))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message))
        return app

    async def _handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command."""
        await update.message.reply_text(
            "Hi! I'm Clawdia, your home assistant.\n\n"
            "Send me a message and I'll process it.\n"
            "Use /ir to see available IR commands."
        )

    async def _handle_ir_list(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /ir command - list available IR commands."""
        await update.message.reply_text("IR command listing coming soon.")

    async def _handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle text messages - send to brain for processing."""
        if update.effective_chat.id != self.chat_id:
            await update.message.reply_text("Sorry, I only respond to my owner.")
            return

        text = update.message.text
        logger.info("Telegram message received: %s", text)

        try:
            response = await self.brain.process(text)
            await update.message.reply_text(response.message)
        except Exception:
            logger.exception("Error processing message")
            await update.message.reply_text("Sorry, something went wrong.")

    async def start(self) -> None:
        """Start the Telegram bot (non-blocking, uses polling)."""
        self._app = self._build_app()
        await self._app.initialize()
        await self._app.start()
        await self._app.updater.start_polling(allowed_updates=Update.ALL_TYPES)
        logger.info("Telegram bot started")

    async def stop(self) -> None:
        """Stop the Telegram bot."""
        if self._app:
            await self._app.updater.stop()
            await self._app.stop()
            await self._app.shutdown()
            logger.info("Telegram bot stopped")
