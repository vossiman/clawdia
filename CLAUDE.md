# Clawdia Project Instructions

## Checking / Verification

Whenever the user asks you to "check something", "verify something", or "see if something is working", you must check it on the Clawdia Raspberry Pi by SSHing in:

```
ssh clawdia
```

Do not check locally — always check on the Pi.

## Deploying

After code changes, deploy to the Pi:
```bash
ssh clawdia "cd ~/clawdia && git pull && docker compose up -d --build"
```

## Running Tests

```bash
pytest tests/ -q
```

All 123 tests should pass. Tests use mocks — no hardware or API keys needed.

## Key Architecture Decisions

- **Single action router**: All input sources (Telegram, voice) go through `Orchestrator.handle_text_command()`. Do NOT add action routing logic in the Telegram bot — it delegates to the orchestrator.
- **Per-chat music controllers**: Telegram messages use per-user Spotify controllers via `music_override` parameter.
- **Conversation history**: Brain maintains per-context history (trimmed to 3 exchanges). Telegram uses `chat_id` as context, voice uses `"default"`.
- **Interaction logging**: All commands logged to `clawdia_interactions.db` via `InteractionLogger`. The orchestrator handles this automatically.
- **Knowledge base**: PC facts in `pc_knowledge.yaml`, injected into the brain's system prompt.

## Environment

- Python 3.12+ (Docker uses 3.12-slim)
- Dependencies managed via `pyproject.toml`
- Config via `.env` file (pydantic-settings)
- Docker Compose for deployment on Pi
