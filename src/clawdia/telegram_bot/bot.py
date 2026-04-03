from __future__ import annotations

from typing import TYPE_CHECKING

import telegram
from loguru import logger
from telegram import Update
from telegram.constants import ChatAction
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
    from clawdia.orchestrator import Orchestrator
    from clawdia.playback import PlaybackCoordinator


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
        coordinator: PlaybackCoordinator | None = None,
    ):
        self.token = token
        self.chat_ids = chat_ids
        self.brain = brain
        self.ir = ir
        self.music = music
        self.music_controllers = music_controllers or {}
        self.coordinator = coordinator
        self._bot = telegram.Bot(token=token)
        self._app: Application | None = None
        self._orchestrator: Orchestrator | None = None

    def set_orchestrator(self, orchestrator: Orchestrator) -> None:
        """Set the orchestrator reference (called after both are constructed)."""
        self._orchestrator = orchestrator

    def _get_music(self, chat_id: int) -> MusicController | None:
        """Get the music controller for a chat, falling back to the default."""
        return self.music_controllers.get(chat_id, self.music)

    def _is_allowed(self, chat_id: int) -> bool:
        return chat_id in self.chat_ids

    def _require_message(self, update: Update) -> telegram.Message:
        message = update.message
        if message is None:
            raise RuntimeError("Telegram update has no message")
        return message

    def _require_chat(self, update: Update) -> telegram.Chat:
        chat = update.effective_chat
        if chat is None:
            raise RuntimeError("Telegram update has no chat")
        return chat

    async def notify(self, text: str) -> None:
        """Send a notification message to all allowed chats."""
        for chat_id in self.chat_ids:
            try:
                await self._bot.send_message(chat_id=chat_id, text=text)
            except Exception:
                logger.exception("Failed to send Telegram notification to {}", chat_id)

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
        app.add_handler(CommandHandler("pc", self._handle_pc_status))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message))
        return app

    async def _handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command."""
        message = update.message
        if message is None:
            return
        await message.reply_text(
            "Hi! I'm Clawdia, your home assistant.\n\n"
            "Send me a message and I'll process it.\n"
            "Use /ir to see available IR commands.\n"
            "Use /play <query> to play music.\n"
            "Use /pc for PC remote control info."
        )

    async def _handle_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /help command."""
        message = self._require_message(update)
        await message.reply_text(
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
        message = self._require_message(update)
        if not self.ir:
            await message.reply_text("IR controller not configured.")
            return
        commands = self.ir.list_commands()
        if commands:
            await message.reply_text(
                "Available IR commands:\n" + "\n".join(f"• {c}" for c in commands)
            )
        else:
            await message.reply_text(
                "No IR commands recorded yet. Use /record <name> to record one."
            )

    async def _handle_record(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /record <name> <description> - record an IR code from the receiver."""
        message = self._require_message(update)
        chat_id = self._require_chat(update).id
        if not self._is_allowed(chat_id):
            await message.reply_text("Sorry, you're not authorized.")
            return

        if not self.ir:
            await message.reply_text("IR controller not configured.")
            return

        if not context.args:
            await message.reply_text(
                "Usage: /record <name> <description>\nExample: /record power Toggle TV power on/off"
            )
            return

        command = context.args[0].lower().strip()
        description = " ".join(context.args[1:]).strip() if len(context.args) > 1 else ""

        if self.ir.has_command(command):
            await message.reply_text(
                f"'{command}' already exists. Recording will overwrite it.\n"
                "Point your remote at the IR receiver and press the button within 10 seconds..."
            )
        else:
            await message.reply_text(
                f"Recording '{command}'...\n"
                "Point your remote at the IR receiver and press the button within 10 seconds..."
            )

        success = await self.ir.record(command)
        if success:
            if description:
                self.ir.set_description(command, description)
            self.brain.reload_commands()
            await message.reply_text(
                f"Recorded '{command}': {description}" if description else f"Recorded '{command}'"
            )
        else:
            await message.reply_text(
                f"Failed to record '{command}'. Timed out or no signal received."
            )

    async def _handle_play(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /play [query] - play music or search and play a track."""
        message = self._require_message(update)
        chat_id = self._require_chat(update).id
        music = self._get_music(chat_id)
        if not music:
            await message.reply_text("Music playback is not configured.")
            return
        if context.args:
            query = " ".join(context.args)
            if self.coordinator:
                result = await self.coordinator.play(
                    service=f"spotify:{chat_id}",
                    source="telegram",
                    user_chat_id=chat_id,
                    callback=lambda: music.play_query(query),
                    description=query,
                )
            else:
                result = await music.play_query(query)
        else:
            if self.coordinator:
                result = await self.coordinator.play(
                    service=f"spotify:{chat_id}",
                    source="telegram",
                    user_chat_id=chat_id,
                    callback=lambda: music.play(),
                    description="Resumed playback",
                )
            else:
                result = await music.play()
        await message.reply_text(result)

    async def _handle_pause(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /pause - pause playback."""
        message = self._require_message(update)
        chat_id = self._require_chat(update).id
        music = self._get_music(chat_id)
        if not music:
            await message.reply_text("Music playback is not configured.")
            return
        result = await music.pause()
        if self.coordinator:
            await self.coordinator.stop(f"spotify:{chat_id}")
        await message.reply_text(result)

    async def _handle_skip(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /skip - skip to next track."""
        message = self._require_message(update)
        music = self._get_music(self._require_chat(update).id)
        if not music:
            await message.reply_text("Music playback is not configured.")
            return
        result = await music.skip()
        await message.reply_text(result)

    async def _handle_prev(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /prev - go to previous track."""
        message = self._require_message(update)
        music = self._get_music(self._require_chat(update).id)
        if not music:
            await message.reply_text("Music playback is not configured.")
            return
        result = await music.previous()
        await message.reply_text(result)

    async def _handle_np(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /np - show now playing."""
        message = self._require_message(update)
        music = self._get_music(self._require_chat(update).id)
        if not music:
            await message.reply_text("Music playback is not configured.")
            return
        result = await music.now_playing()
        await message.reply_text(result)

    async def _handle_vol(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /vol <0-100> - set volume."""
        message = self._require_message(update)
        music = self._get_music(self._require_chat(update).id)
        if not music:
            await message.reply_text("Music playback is not configured.")
            return
        if not context.args:
            await message.reply_text("Usage: /vol <0-100>\nExample: /vol 75")
            return
        try:
            level = int(context.args[0])
        except ValueError:
            await message.reply_text("Usage: /vol <0-100>\nExample: /vol 75")
            return
        result = await music.volume(level)
        await message.reply_text(result)

    async def _handle_playlist(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /playlist <name> - play a playlist by name."""
        message = self._require_message(update)
        chat_id = self._require_chat(update).id
        music = self._get_music(chat_id)
        if not music:
            await message.reply_text("Music playback is not configured.")
            return
        if not context.args:
            await message.reply_text("Usage: /playlist <name>\nExample: /playlist chill")
            return
        name = " ".join(context.args)
        if self.coordinator:
            result = await self.coordinator.play(
                service=f"spotify:{chat_id}",
                source="telegram",
                user_chat_id=chat_id,
                callback=lambda: music.play_playlist(name),
                description=f"playlist: {name}",
            )
        else:
            result = await music.play_playlist(name)
        await message.reply_text(result)

    async def _handle_queue(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /queue <query> - add a track to the queue."""
        message = self._require_message(update)
        music = self._get_music(self._require_chat(update).id)
        if not music:
            await message.reply_text("Music playback is not configured.")
            return
        if not context.args:
            await message.reply_text("Usage: /queue <query>\nExample: /queue jazz classics")
            return
        query = " ".join(context.args)
        result = await music.queue_track(query)
        await message.reply_text(result)

    async def _handle_playlists(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /playlists - list available playlists."""
        message = self._require_message(update)
        music = self._get_music(self._require_chat(update).id)
        if not music:
            await message.reply_text("Music playback is not configured.")
            return
        playlists = await music.list_playlists()
        if not playlists:
            await message.reply_text("No playlists found.")
            return
        lines = [f"• {pl['name']}" for pl in playlists]
        await message.reply_text("Your playlists:\n" + "\n".join(lines))

    async def _handle_pc_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /pc command - show PC remote control status."""
        message = self._require_message(update)
        await message.reply_text(
            "PC Remote Control\n\n"
            "Just send me a message describing what you want to do on your PC.\n"
            "Examples:\n"
            "• 'Open Emby and play Stranger Things'\n"
            "• 'Set the volume to 50%'\n"
            "• 'Open Firefox'\n"
            "• 'Take a screenshot'"
        )

    async def _handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle text messages - delegate to orchestrator."""
        message = self._require_message(update)
        chat = self._require_chat(update)
        if not self._is_allowed(chat.id):
            await message.reply_text("Sorry, you're not authorized.")
            return

        text = message.text
        if text is None:
            return
        chat_id = chat.id
        logger.info("Telegram message received: {}", text)

        if not self._orchestrator:
            await message.reply_text("Sorry, I'm not fully initialized yet.")
            return

        async def reply_text(text: str) -> None:
            await message.reply_text(text)

        async def send_typing() -> None:
            try:
                await chat.send_action(ChatAction.TYPING)
            except Exception:
                pass

        await self._orchestrator.handle_text_command(
            text,
            reply=reply_text,
            context_id=str(chat_id),
            music_override=self._get_music(chat_id),
            source="telegram",
            on_typing=send_typing,
            on_progress=reply_text,
            chat_id=chat_id,
        )

    async def start(self) -> None:
        """Start the Telegram bot (non-blocking, uses polling)."""
        self._app = self._build_app()
        await self._app.initialize()
        await self._app.start()
        updater = self._app.updater
        if updater is None:
            raise RuntimeError("Telegram updater is unavailable")
        await updater.start_polling(allowed_updates=Update.ALL_TYPES)
        logger.info("Telegram bot started")

    async def stop(self) -> None:
        """Stop the Telegram bot."""
        if self._app:
            updater = self._app.updater
            if updater is None:
                raise RuntimeError("Telegram updater is unavailable")
            await updater.stop()
            await self._app.stop()
            await self._app.shutdown()
            logger.info("Telegram bot stopped")
