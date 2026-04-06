from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from loguru import logger

from clawdia.logger_db import InteractionLogger, ms_since

if TYPE_CHECKING:
    from clawdia.brain import Brain
    from clawdia.brain.models import ClawdiaResponse, MusicAction
    from clawdia.ir import IRController
    from clawdia.music import MusicController
    from clawdia.pc.controller import PCController
    from clawdia.pc.knowledge import KnowledgeBase
    from clawdia.playback import PlaybackCoordinator
    from clawdia.telegram_bot import ClawdiaTelegramBot
    from clawdia.voice.stt import SpeechToText

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
        interaction_logger: InteractionLogger | None = None,
    ):
        self.brain = brain
        self.ir = ir
        self.telegram = telegram
        self.stt = stt
        self.music = music
        self.pc = pc
        self.knowledge = knowledge
        self.coordinator = coordinator
        self.interaction_logger = interaction_logger

    async def _handle_music(
        self,
        action: MusicAction,
        music: MusicController,
        chat_id: int | None = None,
    ) -> str:
        """Dispatch a music action to the controller."""
        handler = MUSIC_DISPATCH.get(action.command)
        if not handler:
            return f"Unknown music command: {action.command}"
        service_key = f"spotify:{chat_id}" if chat_id else "spotify:default"
        is_playback_cmd = action.command in ("play", "play_query", "play_playlist")
        if self.coordinator and is_playback_cmd:
            result = await self.coordinator.play(
                service=service_key,
                source="voice" if chat_id is None else "telegram",
                user_chat_id=chat_id,
                callback=lambda: handler(music, action),
                description=action.query or "music",
            )
        elif self.coordinator and action.command == "pause":
            result = await handler(music, action)
            await self.coordinator.stop(service_key)
        else:
            result = await handler(music, action)
        if isinstance(result, list):
            if not result:
                return "No results found."
            lines = [
                f"• {r['name']} — {r.get('artists', '')}" if "artists" in r else f"• {r['name']}"
                for r in result
            ]
            return "\n".join(lines)
        return result

    async def handle_text_command(
        self,
        text: str,
        *,
        reply: Callable[[str], Awaitable[None]] | None = None,
        context_id: str = "default",
        music_override: MusicController | None = None,
        source: str = "voice",
        on_typing: Callable[[], Awaitable[None]] | None = None,
        on_progress: Callable[[str], Awaitable[None]] | None = None,
        chat_id: int | None = None,
    ) -> None:
        """Process a text command through the full pipeline."""
        logger.info("Processing command: '{}' (source={}, context={})", text, source, context_id)

        async def send(msg: str) -> None:
            if reply:
                await reply(msg)
            else:
                await self.telegram.notify(msg)

        # Start typing indicator loop
        typing_task: asyncio.Task | None = None
        if on_typing:

            async def _typing_loop() -> None:
                try:
                    while True:
                        await on_typing()
                        await asyncio.sleep(4)
                except asyncio.CancelledError:
                    pass

            typing_task = asyncio.create_task(_typing_loop())

        start_time = time.monotonic()
        response: ClawdiaResponse | None = None
        success: bool | None = None
        response_msg: str = ""

        try:
            llm_start = time.monotonic()
            try:
                response = await self.brain.process(text, context_id=context_id)
            except Exception:
                logger.exception("Brain processing failed")
                response_msg = "Sorry, I had trouble understanding that."
                await send(response_msg)
                success = False
                return
            llm_ms = ms_since(llm_start)

            if response.action == "ir" and response.ir:
                if not self.ir.has_command(response.ir.command):
                    response_msg = (
                        f"IR command '{response.ir.command}' not available. Record it first."
                    )
                    logger.warning(response_msg)
                    await send(response_msg)
                    success = False
                    return

                ok = await self.ir.send(command=response.ir.command, repeat=response.ir.repeat)
                if ok:
                    response_msg = response.message
                    success = True
                else:
                    response_msg = f"Failed to send IR command: {response.ir.command}"
                    success = False
                await send(response_msg)

            elif response.action == "music" and response.music:
                music = music_override or self.music
                if not music:
                    response_msg = "Music playback is not configured."
                    await send(response_msg)
                    success = False
                    return
                result = await self._handle_music(response.music, music, chat_id=chat_id)
                response_msg = result
                success = True
                await send(response_msg)

            elif response.action == "pc" and response.pc:
                if not self.pc:
                    response_msg = "PC remote control is not configured."
                    await send(response_msg)
                    success = False
                    return

                if response.pc.command_type == "computer_use" and response.pc.goal:
                    if on_progress:
                        await on_progress("Working on it, this may take a minute...")
                    knowledge_ctx = self.knowledge.to_prompt_context() if self.knowledge else ""
                    result = await self.pc.run_computer_use(response.pc.goal, knowledge_ctx)
                elif response.pc.command_type == "shell" and response.pc.shell_command:
                    result = await self.pc.run_shell(response.pc.shell_command)
                else:
                    response_msg = "Invalid PC command."
                    await send(response_msg)
                    success = False
                    return

                if result.success:
                    response_msg = response.message
                    success = True
                else:
                    response_msg = f"PC command failed: {result.output}"
                    success = False
                await send(response_msg)

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
                response_msg = response.message
                success = True
                await send(response_msg)

            elif response.action == "respond":
                response_msg = response.message
                success = True
                await send(response_msg)

        finally:
            # Stop typing indicator
            if typing_task:
                typing_task.cancel()
                try:
                    await typing_task
                except asyncio.CancelledError:
                    pass

            # Log interaction
            if self.interaction_logger:
                action_detail = None
                if response:
                    for field in ("ir", "music", "pc", "learn"):
                        obj = getattr(response, field, None)
                        if obj is not None:
                            action_detail = obj.model_dump()
                            break
                await self.interaction_logger.log(
                    source=source,
                    context_id=context_id,
                    user_input=text,
                    action=response.action if response else None,
                    action_detail=action_detail,
                    response_message=response_msg,
                    success=success,
                    duration_ms=ms_since(start_time),
                    llm_duration_ms=llm_ms if response else None,
                )

    async def handle_audio(
        self,
        pcm_data: bytes,
        *,
        reply: Callable[[str], Awaitable[None]] | None = None,
        context_id: str = "default",
        source: str = "voice",
        on_error: Callable[[], Awaitable[None]] | None = None,
    ) -> None:
        """Process captured audio through STT -> brain -> action."""
        if self.stt is None:
            logger.error("STT not configured")
            return

        wav_data = self.stt.pcm_to_wav(pcm_data)

        try:
            text = await self.stt.transcribe(wav_data)
        except Exception:
            logger.exception("STT transcription failed")
            if on_error:
                await on_error()
            return

        if not text:
            logger.info("STT returned empty transcript, ignoring")
            if on_error:
                await on_error()
            return

        await self.handle_text_command(
            text,
            reply=reply,
            context_id=context_id,
            source=source,
        )
