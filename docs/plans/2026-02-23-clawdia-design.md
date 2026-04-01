# Clawdia - Design Document

**Date:** 2026-02-23 (updated 2026-03-28)
**Status:** Approved — all 7 phases implemented, hardware wired
**Author:** Gernot Greimler + Claude

## Overview

Clawdia is an open-source Raspberry Pi voice assistant with IR TV remote control. Cloud-first architecture: all heavy compute (STT, LLM, future TTS) runs via cloud APIs. The Pi handles wake word detection, audio capture, IR control, and orchestration.

## Goals

- Voice-controlled TV via IR (power, volume, channels, menu navigation)
- General assistant capabilities (weather, timers, knowledge questions)
- Responses delivered via Telegram bot (TTS added later with speaker)
- Remote command support via OpenClawd polling (future)
- PydanticAI-based intent engine with OpenRouter as LLM backend

## Non-Goals (for MVP)

- Home Assistant integration
- Local LLM inference
- Display shield UI
- Camera features
- Multi-room support

## Architecture

```
                          +-------------------------------------+
                          |              CLOUD                   |
                          |                                      |
                          |  OpenAI Whisper API  <-- audio       |
                          |       | transcript                   |
                          |       v                              |
                          |  OpenRouter (LLM)  <-- PydanticAI    |
                          |       | structured response          |
                          |       v                              |
                          |  Telegram Bot API  --> user          |
                          +----------------+--------------------+
                                           |
                          +----------------+--------------------+
                          |         RASPBERRY PI 5 (8GB)         |
                          |                                      |
  [Mic] --> openWakeWord --> Audio Capture --> Orchestrator       |
                          |                      |               |
                          |              PydanticAI Brain        |
                          |              (cloud LLM call)        |
                          |                   |                  |
                          |           Action Router              |
                          |            +-- IR Controller --> [TV]|
                          |            +-- Telegram Notify       |
                          |                                      |
                          |  +----------------------------+      |
                          |  | OpenClawd Poller (future)  |      |
                          |  | polls VPS for commands     |      |
                          |  +----------------------------+      |
                          +--------------------------------------+
```

## Components

> **Note:** Originally designed as separate Docker services. Implementation runs as a single container with all components in one Python package.

| Component | Module | Local/Cloud |
|-----------|--------|-------------|
| Wake word listener | `clawdia.voice.listener` | Local |
| Orchestrator | `clawdia.orchestrator` | Local |
| Brain (intent engine) | `clawdia.brain` | Cloud call (OpenRouter) |
| IR Controller | `clawdia.ir` | Local (ir-ctl) |
| Telegram Bot | `clawdia.telegram_bot` | Cloud call |
| Music Controller | `clawdia.music` | Cloud call (Spotify API) |
| PC Controller | `clawdia.pc` | LAN (SSH) |
| Interaction Logger | `clawdia.logger_db` | Local (SQLite) |

## Data Flow

### Voice Command Path

1. `wakeword` service continuously listens on mic via ALSA
2. Wake word "Hey Clawdia" detected -> starts recording audio chunk (until silence or timeout)
3. Audio sent to OpenAI Whisper API -> transcript returned
4. Transcript sent to `brain` service (PydanticAI agent via OpenRouter)
5. Brain returns structured response, e.g.:
   - `{"action": "ir", "command": "power"}` for TV commands
   - `{"action": "respond", "text": "It's 15 degrees in Graz"}` for information
6. Action router dispatches:
   - IR command -> `ir` service executes via ir-ctl
   - Text response -> Telegram bot sends message to user
7. Confirmation sent to Telegram regardless ("Turned off the TV" / answer text)

### Remote Command Path (Future)

1. User tells OpenClawd in Telegram: "tell Clawdia to turn off the TV"
2. OpenClawd writes command to a shared queue/endpoint
3. `openclaw-poller` on Pi picks it up via outbound polling (no inbound port needed)
4. Same brain -> action router flow as voice commands

### Telegram Command Path

1. User sends command directly to Clawdia's Telegram bot
2. Bot service receives update, sends text to brain
3. Same brain -> action router flow

## PydanticAI Brain Design

The brain is a PydanticAI agent with structured output. The LLM provider is configurable via OpenRouter, defaulting to a fast/cheap model (e.g., Claude Haiku or GPT-4o-mini).

```python
from pydantic_ai import Agent
from pydantic import BaseModel
from typing import Literal

class IRCommand(BaseModel):
    command: str  # e.g., "power", "vol_up", "channel_3"

class TextResponse(BaseModel):
    text: str

class ClawdiaResponse(BaseModel):
    action: Literal["ir", "respond"]
    ir_command: IRCommand | None = None
    text_response: TextResponse | None = None

agent = Agent(
    'openrouter:anthropic/claude-3-haiku',
    system_prompt="You are Clawdia, a home assistant. Available IR commands: ...",
    result_type=ClawdiaResponse,
)
```

The intent engine interface is abstract enough to swap backends later (direct Anthropic API, local model, etc.) without changing the rest of the pipeline.

## IR Control

### Hardware Wiring

**Note:** GPIO 17 and 18 are used by the ReSpeaker 2-Mic HAT (I2S CLK and button).
IR uses alternative pins to avoid conflict.

- IR receiver: AZDelivery KY-022 module (CHQ1838, 38kHz) on **GPIO 22**
- IR transmitter: AZDelivery KY-005 module on **GPIO 24** via NPN transistor (2N2222) + 1K ohm base resistor
- Transistor drives IR LED at higher current (~100-200mA) for 5-10m range
- Configured via `/boot/config.txt` device tree overlays:
  - `dtoverlay=gpio-ir,gpio_pin=22`
  - `dtoverlay=gpio-ir-tx,gpio_pin=24`

### Software

- **Tool:** `ir-ctl` (kernel-native, part of v4l-utils). Simpler than LIRC.
- **Recording:** One-time manual recording of each remote button via `ir-ctl --receive`
- **Storage:** Raw IR pulse/space files in `ir-codes/` directory (e.g., `power.txt`, `vol_up.txt`)
- **Playback:** `ir-ctl --send=codes/power.txt`
- **API:** Internal FastAPI service: `POST /ir/send {"command": "power"}`

### Initial Command Set

**TV Control:**
- Power on/off
- Volume up/down/mute
- Channel up/down
- Input source switch
- Number keys 0-9
- Menu navigation: up, down, left, right, ok, back

**General Assistant:**
- Weather queries
- Timers/alarms
- General knowledge questions (routed to LLM, answer via Telegram)

## Custom Wake Word

Train "Hey Clawdia" for openWakeWord:

1. Generate synthetic training audio using cloud TTS APIs (multiple voices, speeds, background noise variations)
2. Mix with negative examples (general speech, similar-sounding phrases)
3. Fine-tune openWakeWord base model using the provided training scripts
4. Deploy as custom `.tflite` model file in the `wakeword` container
5. Tune detection threshold for false positive/negative balance

## Project Structure

> **Note:** The original design proposed separate microservices. Implementation uses a single Python package for simplicity — all components run in one Docker container.

```
clawdia/
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
├── .env.example                # Template for API keys
├── .env                        # Actual API keys (gitignored)
├── src/clawdia/
│   ├── main.py                 # Entry point, component init
│   ├── config.py               # Settings via pydantic-settings
│   ├── orchestrator.py         # Unified action router for all inputs
│   ├── logger_db.py            # SQLite interaction logging
│   ├── brain/                  # PydanticAI intent engine
│   │   ├── __init__.py         # Brain class with conversation history
│   │   ├── agent.py            # Agent factory with dynamic system prompt
│   │   └── models.py           # Structured response models
│   ├── ir/                     # IR send/receive via ir-ctl
│   │   └── controller.py
│   ├── music/                  # Spotify integration via spotipy
│   │   └── controller.py
│   ├── pc/                     # PC remote control via SSH
│   │   ├── controller.py       # Shell + computer_use execution
│   │   └── knowledge.py        # YAML knowledge base
│   ├── pc_agent/               # Computer use agent (screenshot loop)
│   │   ├── agent.py            # Claude-powered GUI automation
│   │   └── actions.py          # Screenshot, click, type, key actions
│   ├── playback/               # Playback coordination
│   │   └── coordinator.py      # Prevents multiple audio sources
│   ├── telegram_bot/           # Telegram bot
│   │   └── bot.py              # Slash commands + message delegation
│   └── voice/                  # Voice input
│       ├── listener.py         # openWakeWord wake word detection
│       └── stt.py              # OpenAI Whisper transcription
├── ir-codes/                   # Recorded IR pulse/space files
├── pc_knowledge.yaml           # Learned PC facts
├── docs/
└── tests/
```

## API Keys & Configuration

See `.env.example` for the full list. Key variables:

| Key | Service | Purpose |
|-----|---------|---------|
| `OPENROUTER_API_KEY` | OpenRouter | LLM calls for intent processing |
| `OPENROUTER_MODEL` | OpenRouter | Model selection (default: `anthropic/claude-haiku-4.5`) |
| `OPENAI_API_KEY` | OpenAI | Whisper STT API (optional, voice only) |
| `TELEGRAM_BOT_TOKEN` | Telegram BotFather | Clawdia's own Telegram bot |
| `TELEGRAM_CHAT_IDS` | Telegram | Comma-separated allowed chat IDs |
| `SPOTIFY_CLIENT_ID` | Spotify | Music playback (optional) |
| `SPOTIFY_CLIENT_SECRET` | Spotify | Music playback (optional) |
| `SPOTIFY_USERS` | Spotify | Multi-user: `chat_id:cache:device,...` |
| `PC_SSH_HOST` | SSH | PC remote control target (optional) |
| `PC_SSH_USER` | SSH | PC remote control user (optional) |

## Security Considerations

- No inbound ports exposed on the Pi (LAN only)
- OpenClawd integration via outbound polling (Clawdia initiates connection)
- API keys stored in `.env`, never committed to git
- Docker containers run with minimal privileges
- IR service only accessible from internal Docker network

## Future Enhancements

- **TTS via speaker:** Add cloud TTS (OpenAI TTS / ElevenLabs), speaker already purchased
- **Display shield:** Show status, current command, weather on Pi display
- **Camera:** Visual features (person detection, gesture control)
- **OpenClawd integration:** Polling-based remote command execution
- **Pi 3B+ as satellite:** Second room mic/speaker connected to main Pi
- **Local fallback:** Optional local STT/TTS for offline operation
