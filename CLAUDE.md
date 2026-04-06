# Clawdia Project Instructions

## Checking / Verification

Whenever the user asks you to "check something", "verify something", or "see if something is working", you must check it on the Clawdia Raspberry Pi by SSHing in:

```bash
ssh clawdia
```

Do not check locally for runtime behavior. Use the Pi.

## Deploying

After code changes, deploy to the Pi:

```bash
ssh clawdia "cd ~/clawdia && git pull && source ~/.local/bin/env && uv sync --frozen --extra voice && systemctl --user restart clawdia"
```

Clawdia runs as a systemd user service on the Pi (not Docker). Related services:
- `pulseaudio.service` — audio output (librespot depends on this)
- `librespot-gernot.service` / `librespot-oxana.service` — Spotify Connect devices
- `clawdia.service` — the main app (depends on pulseaudio)

## Setup

- Python: `>=3.11` (`pyproject.toml`)
- Create the local environment and install dev tooling with:

```bash
uv venv
uv sync --all-extras
```

- Run project commands with `uv run ...`, or activate `.venv` first.

## Lint And Format

```bash
uv run ruff check .
uv run ruff check . --fix
uv run ruff format .
uv run ruff format --check .
```

## Type Checking

```bash
uv run pyright
```

## Tests And Coverage

```bash
uv run pytest
```

The test suite currently enforces coverage via `pyproject.toml`.

## Pre-commit

```bash
uv run pre-commit install
uv run pre-commit run --all-files
```

## Key Architecture Decisions

- **Single action router**: All input sources (Telegram, voice) go through `Orchestrator.handle_text_command()`. Do NOT add action routing logic in the Telegram bot.
- **Per-chat music controllers**: Telegram messages use per-user Spotify controllers via `music_override`.
- **Conversation history**: Brain maintains per-context history. Telegram uses `chat_id` as context, voice uses `"default"`.
- **Interaction logging**: Commands are logged to `clawdia.db` via `InteractionLogger`.
- **Knowledge base**: PC facts in `pc_knowledge.yaml`, injected into the brain prompt.

## Key Files

- `pyproject.toml`: dependencies, Ruff config, pytest config, coverage config, package metadata
- `Dockerfile`: container build for the app and voice dependencies
- `.pre-commit-config.yaml`: local git hooks for hygiene and Ruff
- `pyrightconfig.json`: type-checker scope and `.venv` settings
- `.github/workflows/ci.yml`: CI workflow for lint, type-check, and tests
- `.github/workflows/renovate.yml`: Renovate automation workflow
- `.env.example`: placeholder environment values for local `.env`

## Secrets

- Put real secrets in `.env` only.
- Keep placeholders in `.env.example`.
- `.env` is gitignored.
