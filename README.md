# Clawdia

A Raspberry Pi voice assistant with IR remote control, Spotify playback, PC remote control, and Telegram bot interface.

Cloud-first architecture: heavy compute (STT, LLM) runs via cloud APIs while the Pi handles wake word detection, audio capture, IR control, and orchestration.

## Features

- **Voice control** via wake word detection ("Hey Jarvis") and OpenAI Whisper STT
- **IR remote control** for TV and surround system (power, volume, HDMI switching, etc.)
- **Spotify playback** with multi-user support and per-chat controllers
- **PC remote control** via SSH — shell commands and AI-powered GUI interaction (computer use)
- **Telegram bot** for sending commands and receiving responses
- **Conversation history** for context-aware follow-up commands
- **Interaction logging** to SQLite for analytics and debugging
- **Knowledge base** that learns from corrections and user preferences
- **Startup health checks** with auto-recovery for stale Spotify sessions
- **Typing indicators** in Telegram while processing commands

## Quick Start

### 1. Clone and configure

```bash
git clone https://github.com/vossiman/clawdia.git
cd clawdia
cp .env.example .env
```

Edit `.env` with your API keys:

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENROUTER_API_KEY` | Yes | LLM for intent detection (via OpenRouter) |
| `OPENROUTER_MODEL` | No | LLM model, default: `anthropic/claude-haiku-4.5` |
| `OPENAI_API_KEY` | No | OpenAI Whisper STT (only needed for voice) |
| `TELEGRAM_BOT_TOKEN` | Yes | From [@BotFather](https://t.me/BotFather) |
| `TELEGRAM_CHAT_IDS` | Yes | Comma-separated allowed Telegram chat IDs |
| `SPOTIFY_CLIENT_ID` | No | Spotify app credentials (for music) |
| `SPOTIFY_CLIENT_SECRET` | No | Spotify app credentials (for music) |
| `SPOTIFY_USERS` | No | Multi-user: `chat_id:cache:device,...` |
| `PC_SSH_HOST` | No | PC IP address (for remote control) |
| `PC_SSH_USER` | No | PC SSH username |
| `DEBUG` | No | Set `true` for verbose logging |

### 2. Deploy with Docker

```bash
docker compose up -d --build
```

The container runs as uid 1000 (matching the Pi user) and needs access to:
- `/dev/lirc0`, `/dev/lirc1` — IR transmitter/receiver
- `/dev/snd` — Audio devices
- Host network — for Spotify Connect (librespot)
- Systemd/dbus user sockets — for restarting librespot on stale sessions

### 3. Deploy to Raspberry Pi

```bash
# Build and push on the Pi
ssh clawdia
cd ~/clawdia
git pull
docker compose up -d --build
```

## Usage

### Telegram Bot

Send messages directly to your Clawdia Telegram bot. It understands natural language:

- "Turn off the TV"
- "Play some jazz"
- "Switch to HDMI 2"
- "Open Firefox on the PC"
- "What's playing?"

#### Slash Commands

| Command | Description |
|---------|-------------|
| `/help` | Show available commands |
| `/ir` | List available IR commands |
| `/record <name> <desc>` | Record a new IR code from your remote |
| `/play <query>` | Search and play a song |
| `/pause` | Pause playback |
| `/skip` | Next track |
| `/prev` | Previous track |
| `/np` | Now playing |
| `/vol <0-100>` | Set volume |
| `/playlist <name>` | Play a playlist |
| `/queue <query>` | Add to queue |
| `/playlists` | List your playlists |
| `/pc` | PC remote control info |

### Voice

Say the wake word ("Hey Jarvis") and then speak your command. Clawdia captures 5 seconds of audio, transcribes it via Whisper, and processes it through the same pipeline as Telegram messages.

Requires the voice extras: `pip install clawdia[voice]`

### Testing

Clawdia uses three separate validation layers so hosted CI does not pretend to be Raspberry Pi hardware:

- **Standard hosted CI**: installs base dependencies plus `dev` tooling only. This runs Ruff, Pyright, and the main pytest suite without compiling microphone-specific native packages.
- **Hosted voice smoke**: installs Linux audio headers plus the `voice` extra, then checks that voice modules import and that non-hardware voice tests pass.
- **Pi hardware validation**: any real microphone or device-level tests should run on the Raspberry Pi, not on GitHub-hosted Ubuntu.

Standard local verification:

```bash
uv sync --extra dev
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest -m "not hardware and not pi"
```

Hosted voice smoke equivalent:

```bash
sudo apt-get install -y portaudio19-dev
uv sync --extra dev --extra voice
uv run pytest tests/test_listener.py tests/test_stt.py -v
```

`pyaudio` depends on PortAudio headers, so the voice smoke lane installs `portaudio19-dev` explicitly. The standard CI jobs intentionally do not install `clawdia[voice]`; that keeps linting, type checking, and unit tests focused on application logic instead of native audio build requirements.

If you add true hardware coverage later, mark those tests with `@pytest.mark.hardware` or `@pytest.mark.pi` so they stay out of normal hosted CI.

### PC Remote Control

Clawdia can control a Linux PC via SSH. Two modes:

- **Shell commands** — fast, for simple actions like toggling fullscreen (`xdotool key F11`), opening URLs, launching apps
- **Computer use** — AI-powered GUI interaction via screenshots + click/type/key actions, for complex tasks like navigating web apps

The brain decides which mode to use based on the request.

#### Knowledge Base

Clawdia learns about your PC setup over time. Correct it and it remembers:

> "Open Twitch in Firefox" -> (brain learns: browser=firefox, streaming=twitch)

Facts are stored in `pc_knowledge.yaml` and injected into the system prompt so the brain makes better decisions.

### IR Remote Control

Record IR codes from your existing remote, then control your TV/sound system via Telegram or voice:

```
/record tv_power_on Turn TV on
# Point your remote at the IR receiver and press the button
```

Clawdia generates Samsung and NEC protocol codes automatically for common commands, or records raw signals from any remote.

## Architecture

```
Input ──> [Voice / Telegram] ──> Brain (PydanticAI + OpenRouter)
                                      |
                               Conversation History
                               Playback State
                               Knowledge Base
                                      |
                                Action Router
                          ┌───────┼───────┬──────────┐
                          v       v       v          v
                         IR    Music     PC       Respond
                      (ir-ctl) (Spotify) (SSH)   (Telegram)
```

### Components

| Component | File | Description |
|-----------|------|-------------|
| Brain | `src/clawdia/brain/` | PydanticAI agent with structured output, conversation history |
| Orchestrator | `src/clawdia/orchestrator.py` | Unified action router for all input sources |
| IR Controller | `src/clawdia/ir/` | Send/receive IR via `ir-ctl`, code storage |
| Music Controller | `src/clawdia/music/` | Spotify playback via spotipy |
| PC Controller | `src/clawdia/pc/` | SSH command execution + computer use agent |
| Telegram Bot | `src/clawdia/telegram_bot/` | Message handling, slash commands, notifications |
| Voice | `src/clawdia/voice/` | Wake word (openWakeWord) + STT (Whisper) |
| Playback Coordinator | `src/clawdia/playback/` | Prevents multiple audio sources playing at once |
| Health Checks | `src/clawdia/health.py` | Startup verification, Spotify auto-recovery |
| Interaction Logger | `src/clawdia/logger_db.py` | SQLite logging of all interactions |

### Startup Health Checks

On startup, Clawdia verifies all services before sending the "online" notification:

- **Spotify devices** — checks each librespot device is visible via the Spotify API. If a device is missing (stale session), Clawdia automatically restarts the corresponding `librespot-*` systemd service and retries.
- **IR device** — verifies `/dev/lirc0` exists.
- **PC remote control** — skipped at startup (on-demand by nature, PC may be off).

The Telegram notification reflects the result:
- "Clawdia is online! All systems go." — everything checked out
- "Clawdia is online with issues: ..." — lists what's wrong

### Spotify Auto-Recovery

Librespot sessions can go stale (`SESSION_DELETED`) after periods of inactivity. When this happens, the Spotify API returns no devices and playback commands fail.

Clawdia handles this automatically:
1. When any music command can't find the Spotify device, it triggers auto-recovery
2. The corresponding `librespot-<name>` systemd user service is restarted
3. After a short wait, the device lookup is retried
4. If recovery succeeds, the original command proceeds transparently

This also runs at startup — so a deploy or restart won't leave you with broken Spotify.

The container runs as uid 1000 (matching the host user) with the systemd and dbus sockets mounted, so `systemctl --user restart librespot-*` works natively from inside Docker.

### Typing Indicator

While processing any command, the Telegram bot shows a "typing..." indicator that refreshes every 4 seconds. For long-running operations like `computer_use` (which can take 60+ seconds), a progress message is also sent: "Working on it, this may take a minute..."

### Interaction Logging

Every command is logged to `clawdia_interactions.db` (SQLite):

```sql
SELECT timestamp, source, user_input, action, success, duration_ms
FROM interactions
ORDER BY id DESC LIMIT 10;
```

Fields: `timestamp`, `source` (telegram/voice), `context_id`, `user_input`, `action`, `action_detail` (JSON), `response_message`, `success`, `duration_ms`, `llm_duration_ms`.

## Hardware

- Raspberry Pi 4B (or 5)
- ReSpeaker 2-Mic HAT (microphone input)
- KY-022 IR Receiver on GPIO 22
- KY-005 IR Transmitter on GPIO 24 (via 2N2222 NPN transistor)
- USB speaker (for future TTS)

See [docs/plans/2026-02-23-hardware-shopping-list.md](docs/plans/2026-02-23-hardware-shopping-list.md) for wiring details.

## Development

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Lint
ruff check src/ tests/
```

### Project Structure

```
clawdia/
├── src/clawdia/          # Main package
│   ├── brain/            # LLM intent engine (PydanticAI)
│   ├── ir/               # IR send/receive controller
│   ├── music/            # Spotify integration
│   ├── pc/               # PC remote control + knowledge base
│   ├── pc_agent/         # Computer use agent (screenshot + actions)
│   ├── playback/         # Playback coordination
│   ├── telegram_bot/     # Telegram bot handlers
│   ├── voice/            # Wake word + STT
│   ├── config.py         # Settings (pydantic-settings)
│   ├── health.py         # Startup checks + Spotify auto-recovery
│   ├── logger_db.py      # SQLite interaction logger
│   ├── main.py           # Entry point
│   └── orchestrator.py   # Unified action router
├── ir-codes/             # Recorded IR pulse/space files
├── pc_knowledge.yaml     # Learned PC facts
├── docker-compose.yml    # Container config
├── Dockerfile
├── pyproject.toml
└── tests/
```

## License

Open source. Built by Gernot Greimler with Claude.
