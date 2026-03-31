from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    # OpenRouter
    openrouter_api_key: str = ""
    openrouter_model: str = "anthropic/claude-haiku-4.5"

    # OpenAI (Whisper STT)
    openai_api_key: str = ""
    stt_model: str = "gpt-4o-mini-transcribe"

    # Telegram
    telegram_bot_token: str = ""
    telegram_chat_ids: str = ""  # Comma-separated list of allowed chat IDs

    # IR
    ir_device_send: str = "/dev/lirc0"
    ir_device_receive: str = "/dev/lirc1"
    ir_codes_dir: str = "ir-codes"

    # Voice
    wake_word_model: str = "hey_jarvis"
    wake_word_threshold: float = 0.5
    audio_sample_rate: int = 16000
    audio_chunk_size: int = 1280

    # Spotify
    spotify_client_id: str = ""
    spotify_client_secret: str = ""
    spotify_redirect_uri: str = "http://127.0.0.1:8888/callback"
    spotify_device_name: str = "clawdia"
    spotify_cache_path: str = ".spotify_cache"
    spotify_users: str = ""  # Multi-user: chat_id:cache[:client_id:secret],...

    # General
    debug: bool = False


settings = Settings()
