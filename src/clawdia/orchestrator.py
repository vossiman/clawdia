from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from clawdia.brain import Brain
    from clawdia.brain.models import MusicAction
    from clawdia.ir import IRController
    from clawdia.music import MusicController
    from clawdia.pc.controller import PCController
    from clawdia.pc.knowledge import KnowledgeBase
    from clawdia.playback import PlaybackCoordinator
    from clawdia.telegram_bot import ClawdiaTelegramBot
    from clawdia.voice.stt import SpeechToText

logger = logging.getLogger(__name__)

MUSIC_DISPATCH = {
    "play": lambda m, a: m.play(a.query),
    "pause": lambda m, a: m.pause(),
    "skip": lambda m, a: m.skip(),
    "previous": lambda m, a: m.previous(),
    "volume": lambda m, a: m.volume(a.volume),
    "play_query": lambda m, a: m.play_query(a.query),
    "play_playlist": lambda m, a: m.play_playlist(a.query),
    "queue": lambda m, a: m.queue_track(a.query),
    "search": lambda m, a: m.search(a.query),
    "now_playing": lambda m, a: m.now_playing(),
    "list_playlists": lambda m, a: m.list_playlists(),
}


class Orchestrator:
    """Coordinates the full Clawdia pipeline.

    Connects: voice -> STT -> brain -> action routing (IR / Music / Telegram).
    """

    def __init__(
        self,
        brain: Brain,
        ir: IRController,
        telegram: ClawdiaTelegramBot,
        stt: SpeechToText | None = None,
        music: MusicController | None = None,
        pc: PCController | None = None,
        knowledge: KnowledgeBase | None = None,
        coordinator: PlaybackCoordinator | None = None,
    ):
        self.brain = brain
        self.ir = ir
        self.telegram = telegram
        self.stt = stt
        self.music = music
        self.pc = pc
        self.knowledge = knowledge
        self.coordinator = coordinator

    async def _handle_music(self, action: MusicAction) -> str:
        """Dispatch a music action to the controller."""
        if not self.music:
            return "Music playback is not configured."
        handler = MUSIC_DISPATCH.get(action.command)
        if not handler:
            return f"Unknown music command: {action.command}"
        is_playback_cmd = action.command in ("play", "play_query", "play_playlist")
        if self.coordinator and is_playback_cmd:
            result = await self.coordinator.play(
                service="spotify:default",
                source="voice",
                user_chat_id=None,
                callback=lambda: handler(self.music, action),
                description=action.query or "music",
            )
        elif self.coordinator and action.command == "pause":
            result = await handler(self.music, action)
            await self.coordinator.stop("spotify:default")
        else:
            result = await handler(self.music, action)
        if isinstance(result, list):
            if not result:
                return "No results found."
            lines = [f"• {r['name']} — {r.get('artists', '')}" if 'artists' in r else f"• {r['name']}" for r in result]
            return "\n".join(lines)
        return result

    async def handle_text_command(self, text: str) -> None:
        """Process a text command through the full pipeline."""
        logger.info("Processing command: '%s'", text)

        try:
            response = await self.brain.process(text)
        except Exception:
            logger.exception("Brain processing failed")
            await self.telegram.notify("Sorry, I had trouble understanding that.")
            return

        if response.action == "ir" and response.ir:
            if not self.ir.has_command(response.ir.command):
                msg = f"IR command '{response.ir.command}' not available. Record it first."
                logger.warning(msg)
                await self.telegram.notify(msg)
                return

            success = await self.ir.send(
                command=response.ir.command,
                repeat=response.ir.repeat,
            )
            if success:
                await self.telegram.notify(response.message)
            else:
                await self.telegram.notify(f"Failed to send IR command: {response.ir.command}")

        elif response.action == "music" and response.music:
            result = await self._handle_music(response.music)
            await self.telegram.notify(result)

        elif response.action == "pc" and response.pc:
            if not self.pc:
                await self.telegram.notify("PC remote control is not configured.")
                return

            if response.pc.command_type == "shell" and response.pc.shell_command:
                result = await self.pc.run_shell(response.pc.shell_command)
            elif response.pc.command_type == "computer_use" and response.pc.goal:
                knowledge_ctx = self.knowledge.to_prompt_context() if self.knowledge else ""
                result = await self.pc.run_computer_use(response.pc.goal, knowledge_ctx)
            else:
                await self.telegram.notify("Invalid PC command.")
                return

            if result.success:
                await self.telegram.notify(response.message)
            else:
                await self.telegram.notify(f"PC command failed: {result.output}")

        elif response.action == "learn" and response.learn:
            if self.knowledge:
                learn = response.learn
                if learn.section == "preferences":
                    self.knowledge.add_preference(str(learn.value))
                elif learn.section == "corrections":
                    self.knowledge.add_correction(learn.key, str(learn.value))
                else:
                    self.knowledge.update(learn.section, learn.key, learn.value)
                self.brain.reload_commands(pc_knowledge=self.knowledge.to_prompt_context())
            await self.telegram.notify(response.message)

        elif response.action == "respond":
            await self.telegram.notify(response.message)

    async def handle_audio(self, pcm_data: bytes) -> None:
        """Process captured audio through STT -> brain -> action."""
        if self.stt is None:
            logger.error("STT not configured")
            return

        wav_data = self.stt.pcm_to_wav(pcm_data)
        text = await self.stt.transcribe(wav_data)

        if not text:
            logger.info("STT returned empty transcript, ignoring")
            return

        await self.handle_text_command(text)
