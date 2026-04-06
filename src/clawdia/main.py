from __future__ import annotations

import asyncio
import signal

from dotenv import load_dotenv

load_dotenv()

from loguru import logger  # noqa: E402

from clawdia.brain import Brain  # noqa: E402
from clawdia.config import settings  # noqa: E402
from clawdia.ir import IRController  # noqa: E402
from clawdia.log import setup as setup_logging  # noqa: E402
from clawdia.logger_db import InteractionLogger  # noqa: E402
from clawdia.music import MusicController  # noqa: E402
from clawdia.orchestrator import Orchestrator  # noqa: E402
from clawdia.playback import PlaybackCoordinator  # noqa: E402
from clawdia.telegram_bot import ClawdiaTelegramBot  # noqa: E402


async def run() -> None:
    """Main async entry point for Clawdia."""
    setup_logging(data_dir=settings.data_dir, debug=settings.debug)
    logger.info("Starting Clawdia...")

    # Initialize components
    ir = IRController(
        device_send=settings.ir_device_send,
        codes_dir=settings.ir_codes_dir,
    )

    # Optional: Spotify music (needs client credentials)
    music = None
    music_controllers: dict[int, MusicController] = {}
    if settings.spotify_users:
        # Format: chat_id:cache_path:device_name[:client_id:client_secret],...
        for entry in settings.spotify_users.split(","):
            parts = entry.strip().split(":")
            if len(parts) < 3:
                logger.warning("Invalid SPOTIFY_USERS entry (need chat_id:cache:device): {}", entry)
                continue
            chat_id = int(parts[0])
            cache_path = parts[1]
            device_name = parts[2]
            client_id = parts[3] if len(parts) > 3 else settings.spotify_client_id
            client_secret = parts[4] if len(parts) > 4 else settings.spotify_client_secret
            mc = MusicController(
                client_id=client_id,
                client_secret=client_secret,
                redirect_uri=settings.spotify_redirect_uri,
                device_name=device_name,
                cache_path=cache_path,
            )
            music_controllers[chat_id] = mc
            logger.info(
                "Spotify controller for chat {} (device: {}, cache: {})",
                chat_id,
                device_name,
                cache_path,
            )
        if music_controllers:
            music = next(iter(music_controllers.values()))
    elif settings.spotify_client_id and settings.spotify_client_secret:
        music = MusicController(
            client_id=settings.spotify_client_id,
            client_secret=settings.spotify_client_secret,
            redirect_uri=settings.spotify_redirect_uri,
            device_name=settings.spotify_device_name,
            cache_path=settings.spotify_cache_path,
        )
        logger.info(
            "Spotify music controller initialized (device: {})", settings.spotify_device_name
        )
    else:
        logger.info("Spotify not configured (missing client credentials)")

    # Optional: PC Remote Control (needs SSH config)
    pc = None
    knowledge = None
    pc_knowledge = ""
    if settings.pc_enabled:
        from clawdia.pc import KnowledgeBase, PCController

        pc = PCController(
            ssh_host=settings.pc_ssh_host,
            ssh_user=settings.pc_ssh_user,
            ssh_key_path=settings.pc_ssh_key_path,
            agent_path=settings.pc_agent_path,
        )
        knowledge = KnowledgeBase("pc_knowledge.yaml")
        pc_knowledge = knowledge.to_prompt_context()
        logger.info("PC remote control enabled (host: {})", settings.pc_ssh_host)
    else:
        logger.info("PC remote control not configured (missing SSH host/user)")

    coordinator = PlaybackCoordinator()
    for chat_id, mc in music_controllers.items():
        coordinator.register_service(f"spotify:{chat_id}", stop=mc.pause)
        logger.info("Registered playback service spotify:{}", chat_id)
    if music and not music_controllers:
        coordinator.register_service("spotify:default", stop=music.pause)

    # Interaction logger & database
    interaction_logger = InteractionLogger(db_path=f"{settings.data_dir}/clawdia.db")
    await interaction_logger.init_db()

    brain = Brain(
        model=f"openrouter:{settings.openrouter_model}",
        ir=ir,
        music=music,
        pc_enabled=pc is not None,
        pc_knowledge=pc_knowledge,
        coordinator=coordinator,
        db=interaction_logger,
    )
    await brain.load_history()

    chat_ids = {int(x.strip()) for x in settings.telegram_chat_ids.split(",") if x.strip()}
    logger.info("Allowed Telegram chat IDs: {}", chat_ids)

    telegram = ClawdiaTelegramBot(
        token=settings.telegram_bot_token,
        chat_ids=chat_ids,
        brain=brain,
        ir=ir,
        music=music,
        music_controllers=music_controllers or None,
        coordinator=coordinator,
    )

    # Optional: STT (needs OpenAI API key)
    stt = None
    if settings.openai_api_key:
        from clawdia.voice.stt import SpeechToText

        stt = SpeechToText(
            api_key=settings.openai_api_key,
            model=settings.stt_model,
        )

    # Optional: TTS (needs OpenAI API key)
    tts = None
    if settings.openai_api_key and settings.voice_response_tts:
        from clawdia.voice.tts import TextToSpeech

        tts = TextToSpeech(
            api_key=settings.openai_api_key,
            model=settings.tts_model,
            voice=settings.tts_voice,
        )

    orchestrator = Orchestrator(
        brain=brain,
        ir=ir,
        telegram=telegram,
        stt=stt,
        music=music,
        pc=pc,
        knowledge=knowledge,
        coordinator=coordinator,
        interaction_logger=interaction_logger,
    )

    # Wire orchestrator into telegram bot
    telegram.set_orchestrator(orchestrator)

    # Start services
    await telegram.start()

    # Run startup health checks
    from clawdia.health import periodic_health_check, startup_health_check

    issues = await startup_health_check(
        music_controllers=music_controllers or None,
        pc=pc,
        ir=ir,
    )
    if issues:
        status_msg = "Clawdia is online with issues:\n" + "\n".join(f"- {i}" for i in issues)
    else:
        status_msg = "Clawdia is online! All systems go."
    await telegram.notify(status_msg)
    logger.info("Clawdia is running. Telegram bot active. Ctrl+C to stop.")

    # Periodic health checks (every 5 minutes)
    health_task = asyncio.create_task(
        periodic_health_check(
            music_controllers=music_controllers or None,
            notify=telegram.notify,
        )
    )

    # Optional: Start wake word listener (needs hardware)
    listener_task = None
    try:
        from pathlib import Path

        from clawdia.voice.listener import WakeWordListener
        from clawdia.voice.pipeline import make_on_error, make_voice_reply
        from clawdia.voice.player import AudioPlayer

        player = AudioPlayer()
        sounds_dir = str(Path(__file__).parent / "voice" / "sounds")

        voice_reply = make_voice_reply(
            telegram=telegram,
            tts=tts,
            player=player,
            music=music,
            response_telegram=settings.voice_response_telegram,
            response_tts=settings.voice_response_tts,
        )

        on_error = make_on_error(
            telegram=telegram,
            player=player,
            error_sound=f"{sounds_dir}/error.wav",
        )

        async def on_wake_word():
            logger.info("Wake word detected! Playing chime...")
            await player.play_file(f"{sounds_dir}/chime.wav")
            logger.info("Capturing audio...")
            audio_data = await listener.capture_audio(duration=5.0)
            await orchestrator.handle_audio(
                audio_data,
                reply=voice_reply,
                context_id=settings.voice_context_id,
                source="voice",
                on_error=on_error,
            )

        listener = WakeWordListener(
            model_path=settings.wake_word_model,
            threshold=settings.wake_word_threshold,
            sample_rate=settings.audio_sample_rate,
            chunk_size=settings.audio_chunk_size,
            cooldown=settings.wake_word_cooldown,
            on_wake_word=on_wake_word,
        )
        listener_task = asyncio.create_task(listener.start_listening())
        logger.info("Wake word listener started")
    except Exception:
        logger.info("Wake word listener not available (missing hardware/packages)")

    # Keep running until interrupted
    stop_event = asyncio.Event()

    def _signal_handler():
        stop_event.set()

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _signal_handler)

    await stop_event.wait()

    # Cleanup
    logger.info("Shutting down...")
    health_task.cancel()
    if listener_task:
        listener_task.cancel()
    await telegram.stop()
    logger.info("Clawdia stopped.")


def main():
    """Sync entry point."""
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
