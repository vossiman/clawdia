from clawdia.config import Settings


def test_settings_defaults():
    s = Settings(openrouter_api_key="k", openai_api_key="k",
                 telegram_bot_token="t", telegram_chat_id=1)
    assert s.openrouter_model == "anthropic/claude-haiku-4.5"
    assert s.stt_model == "gpt-4o-mini-transcribe"
    assert s.audio_sample_rate == 16000
    assert s.audio_chunk_size == 1280
    assert s.wake_word_threshold == 0.5
    assert s.debug is False


def test_settings_from_env(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-router-key")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "99999")
    monkeypatch.setenv("DEBUG", "true")

    s = Settings()
    assert s.openrouter_api_key == "test-router-key"
    assert s.openai_api_key == "test-openai-key"
    assert s.telegram_bot_token == "test-token"
    assert s.telegram_chat_id == 99999
    assert s.debug is True


def test_spotify_settings():
    s = Settings(
        spotify_client_id="test-id",
        spotify_client_secret="test-secret",
        spotify_device_name="test-device",
    )
    assert s.spotify_client_id == "test-id"
    assert s.spotify_client_secret == "test-secret"
    assert s.spotify_redirect_uri == "http://127.0.0.1:8888/callback"
    assert s.spotify_device_name == "test-device"
    assert s.spotify_cache_path == ".spotify_cache"


def test_pc_settings_defaults():
    s = Settings(
        openrouter_api_key="k",
        telegram_bot_token="t",
        telegram_chat_id=1,
    )
    assert s.pc_ssh_host == ""
    assert s.pc_ssh_user == ""
    assert s.pc_ssh_key_path == "~/.ssh/id_ed25519"
    assert s.pc_agent_path == "~/clawdia-agent"
    assert s.pc_enabled is False


def test_pc_enabled_when_configured():
    s = Settings(
        openrouter_api_key="k",
        telegram_bot_token="t",
        telegram_chat_id=1,
        pc_ssh_host="192.168.1.100",
        pc_ssh_user="vossi",
    )
    assert s.pc_enabled is True
