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
    from clawdia.music import MusicController

logger = logging.getLogger(__name__)


class ClawdiaTelegramBot:
    """Telegram bot for Clawdia - receives commands, sends notifications."""

    def __init__(
        self,
        token: str,
        chat_ids: set[int],
        brain: Brain,
        ir: IRController | None = None,
        music: MusicController | None = None,
        music_controllers: dict[int, MusicController] | None = None,
    ):
        self.token = token
        self.chat_ids = chat_ids
        self.brain = brain
        self.ir = ir
        self.music = music
        self.music_controllers = music_controllers or {}
        self._bot = telegram.Bot(token=token)
        self._app: Application | None = None

    def _get_music(self, chat_id: int) -> MusicController | None:
        """Get the music controller for a chat, falling back to the default."""
        return self.music_controllers.get(chat_id, self.music)

    def _is_allowed(self, chat_id: int) -> bool:
        return chat_id in self.chat_ids

    async def notify(self, text: str) -> None:
        """Send a notification message to all allowed chats."""
        for chat_id in self.chat_ids:
            try:
                await self._bot.send_message(chat_id=chat_id, text=text)
            except Exception:
                logger.exception("Failed to send Telegram notification to %s", chat_id)

    def _build_app(self) -> Application:
        """Build the Telegram application with handlers."""
        app = Application.builder().token(self.token).build()
        app.add_handler(CommandHandler("start", self._handle_start))
        app.add_handler(CommandHandler("help", self._handle_help))
        app.add_handler(CommandHandler("ir", self._handle_ir_list))
        app.add_handler(CommandHandler("record", self._handle_record))
        app.add_handler(CommandHandler("play", self._handle_play))
        app.add_handler(CommandHandler("pause", self._handle_pause))
        app.add_handler(CommandHandler("skip", self._handle_skip))
        app.add_handler(CommandHandler("prev", self._handle_prev))
        app.add_handler(CommandHandler("np", self._handle_np))
        app.add_handler(CommandHandler("vol", self._handle_vol))
        app.add_handler(CommandHandler("playlist", self._handle_playlist))
        app.add_handler(CommandHandler("queue", self._handle_queue))
        app.add_handler(CommandHandler("playlists", self._handle_playlists))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message))
        return app

    async def _handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command."""
        await update.message.reply_text(
            "Hi! I'm Clawdia, your home assistant.\n\n"
            "Send me a message and I'll process it.\n"
            "Use /ir to see available IR commands.\n"
            "Use /play <query> to play music."
        )

    async def _handle_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /help command."""
        await update.message.reply_text(
            "Available commands:\n\n"
            "General:\n"
            "  /help - Show this message\n"
            "  /ir - List available IR commands\n"
            "  /record <name> <desc> - Record an IR code\n\n"
            "Music:\n"
            "  /play <query> - Play a song (or resume)\n"
            "  /pause - Pause playback\n"
            "  /skip - Next track\n"
            "  /prev - Previous track\n"
            "  /np - Now playing\n"
            "  /vol <0-100> - Set volume\n"
            "  /playlist <name> - Play a playlist\n"
            "  /queue <query> - Add to queue\n"
            "  /playlists - List playlists\n\n"
            "Or just send a message and I'll figure it out!"
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
        """Handle /record <name> <description> - record an IR code from the receiver."""
        if not self._is_allowed(update.effective_chat.id):
            await update.message.reply_text("Sorry, you're not authorized.")
            return

        if not self.ir:
            await update.message.reply_text("IR controller not configured.")
            return

        if not context.args:
            await update.message.reply_text(
                "Usage: /record <name> <description>\n"
                "Example: /record power Toggle TV power on/off"
            )
            return

        command = context.args[0].lower().strip()
        description = " ".join(context.args[1:]).strip() if len(context.args) > 1 else ""

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
            if description:
                self.ir.set_description(command, description)
            self.brain.reload_commands()
            await update.message.reply_text(f"Recorded '{command}': {description}" if description else f"Recorded '{command}'")
        else:
            await update.message.reply_text(f"Failed to record '{command}'. Timed out or no signal received.")

    async def _handle_play(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /play [query] - play music or search and play a track."""
        music = self._get_music(update.effective_chat.id)
        if not music:
            await update.message.reply_text("Music playback is not configured.")
            return
        if context.args:
            query = " ".join(context.args)
            result = await music.play_query(query)
        else:
            result = await music.play()
        await update.message.reply_text(result)

    async def _handle_pause(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /pause - pause playback."""
        music = self._get_music(update.effective_chat.id)
        if not music:
            await update.message.reply_text("Music playback is not configured.")
            return
        result = await music.pause()
        await update.message.reply_text(result)

    async def _handle_skip(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /skip - skip to next track."""
        music = self._get_music(update.effective_chat.id)
        if not music:
            await update.message.reply_text("Music playback is not configured.")
            return
        result = await music.skip()
        await update.message.reply_text(result)

    async def _handle_prev(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /prev - go to previous track."""
        music = self._get_music(update.effective_chat.id)
        if not music:
            await update.message.reply_text("Music playback is not configured.")
            return
        result = await music.previous()
        await update.message.reply_text(result)

    async def _handle_np(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /np - show now playing."""
        music = self._get_music(update.effective_chat.id)
        if not music:
            await update.message.reply_text("Music playback is not configured.")
            return
        result = await music.now_playing()
        await update.message.reply_text(result)

    async def _handle_vol(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /vol <0-100> - set volume."""
        music = self._get_music(update.effective_chat.id)
        if not music:
            await update.message.reply_text("Music playback is not configured.")
            return
        if not context.args:
            await update.message.reply_text("Usage: /vol <0-100>\nExample: /vol 75")
            return
        try:
            level = int(context.args[0])
        except ValueError:
            await update.message.reply_text("Usage: /vol <0-100>\nExample: /vol 75")
            return
        result = await music.volume(level)
        await update.message.reply_text(result)

    async def _handle_playlist(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /playlist <name> - play a playlist by name."""
        music = self._get_music(update.effective_chat.id)
        if not music:
            await update.message.reply_text("Music playback is not configured.")
            return
        if not context.args:
            await update.message.reply_text("Usage: /playlist <name>\nExample: /playlist chill")
            return
        name = " ".join(context.args)
        result = await music.play_playlist(name)
        await update.message.reply_text(result)

    async def _handle_queue(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /queue <query> - add a track to the queue."""
        music = self._get_music(update.effective_chat.id)
        if not music:
            await update.message.reply_text("Music playback is not configured.")
            return
        if not context.args:
            await update.message.reply_text("Usage: /queue <query>\nExample: /queue jazz classics")
            return
        query = " ".join(context.args)
        result = await music.queue_track(query)
        await update.message.reply_text(result)

    async def _handle_playlists(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /playlists - list available playlists."""
        music = self._get_music(update.effective_chat.id)
        if not music:
            await update.message.reply_text("Music playback is not configured.")
            return
        playlists = await music.list_playlists()
        if not playlists:
            await update.message.reply_text("No playlists found.")
            return
        lines = [f"• {pl['name']}" for pl in playlists]
        await update.message.reply_text("Your playlists:\n" + "\n".join(lines))

    async def _handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle text messages - send to brain for processing."""
        if not self._is_allowed(update.effective_chat.id):
            await update.message.reply_text("Sorry, you're not authorized.")
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

        elif response.action == "music" and response.music:
            music = self._get_music(update.effective_chat.id)
            if not music:
                await update.message.reply_text("Music playback is not configured.")
                return
            from clawdia.orchestrator import MUSIC_DISPATCH
            handler = MUSIC_DISPATCH.get(response.music.command)
            if not handler:
                await update.message.reply_text(f"Unknown music command: {response.music.command}")
                return
            result = await handler(music, response.music)
            if isinstance(result, list):
                if not result:
                    await update.message.reply_text("No results found.")
                else:
                    lines = [
                        f"• {r['name']} — {r.get('artists', '')}" if "artists" in r else f"• {r['name']}"
                        for r in result
                    ]
                    await update.message.reply_text("\n".join(lines))
            else:
                await update.message.reply_text(result)

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
