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
    from clawdia.ir import IRController

logger = logging.getLogger(__name__)


class ClawdiaTelegramBot:
    """Telegram bot for Clawdia - receives commands, sends notifications."""

    def __init__(self, token: str, chat_id: int, brain: Brain, ir: IRController | None = None):
        self.token = token
        self.chat_id = chat_id
        self.brain = brain
        self.ir = ir
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
        app.add_handler(CommandHandler("record", self._handle_record))
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
        if not self.ir:
            await update.message.reply_text("IR controller not configured.")
            return
        commands = self.ir.list_commands()
        if commands:
            await update.message.reply_text("Available IR commands:\n" + "\n".join(f"• {c}" for c in commands))
        else:
            await update.message.reply_text("No IR commands recorded yet. Use /record <name> to record one.")

    async def _handle_record(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /record <name> - record an IR code from the receiver."""
        if update.effective_chat.id != self.chat_id:
            await update.message.reply_text("Sorry, I only respond to my owner.")
            return

        if not self.ir:
            await update.message.reply_text("IR controller not configured.")
            return

        if not context.args:
            await update.message.reply_text("Usage: /record <name>\nExample: /record power_toggle")
            return

        command = context.args[0].lower().strip()

        if self.ir.has_command(command):
            await update.message.reply_text(
                f"'{command}' already exists. Recording will overwrite it.\n"
                "Point your remote at the IR receiver and press the button within 10 seconds..."
            )
        else:
            await update.message.reply_text(
                f"Recording '{command}'...\n"
                "Point your remote at the IR receiver and press the button within 10 seconds..."
            )

        success = await self.ir.record(command)
        if success:
            await update.message.reply_text(f"Recorded '{command}' successfully!")
        else:
            await update.message.reply_text(f"Failed to record '{command}'. Timed out or no signal received.")

    async def _handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle text messages - send to brain for processing."""
        if update.effective_chat.id != self.chat_id:
            await update.message.reply_text("Sorry, I only respond to my owner.")
            return

        text = update.message.text
        logger.info("Telegram message received: %s", text)

        try:
            response = await self.brain.process(text)
        except Exception:
            logger.exception("Error processing message")
            await update.message.reply_text("Sorry, something went wrong.")
            return

        if response.action == "ir" and response.ir and self.ir:
            if not self.ir.has_command(response.ir.command):
                await update.message.reply_text(
                    f"[IR: {response.ir.command}] not available. Record it with /record {response.ir.command}"
                )
                return

            success = await self.ir.send(
                command=response.ir.command,
                repeat=response.ir.repeat,
            )
            if success:
                await update.message.reply_text(f"[IR: {response.ir.command} x{response.ir.repeat}] {response.message}")
            else:
                await update.message.reply_text(f"[IR: {response.ir.command}] Failed to send.")
        else:
            await update.message.reply_text(response.message)

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
