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

## Services (Docker Compose)

| Service | Purpose | Local/Cloud |
|---------|---------|-------------|
| `wakeword` | Listens for "Hey Clawdia" via openWakeWord | Local |
| `orchestrator` | Coordinates pipeline: capture -> STT -> brain -> action | Local |
| `brain` | PydanticAI intent engine, calls LLM via OpenRouter | Cloud call |
| `ir` | IR send/receive via ir-ctl, internal REST API | Local |
| `telegram-bot` | Clawdia's own Telegram bot for status/responses + receiving commands | Cloud call |
| `openclaw-poller` | (Future) Polls OpenClawd VPS for remote commands | Cloud call |

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

```
clawdia/
├── docker-compose.yml
├── .env.example                # Template for API keys
├── .env                        # Actual API keys (gitignored)
├── services/
│   ├── wakeword/
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── main.py             # openWakeWord listener + audio capture
│   ├── orchestrator/
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── main.py             # Pipeline coordinator
│   ├── brain/
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   ├── agent.py            # PydanticAI agent definition
│   │   ├── tools.py            # Available tools/commands for the agent
│   │   └── main.py             # FastAPI service wrapping the agent
│   ├── ir/
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   ├── main.py             # FastAPI IR control service
│   │   └── codes/              # Recorded IR code files (.txt)
│   └── telegram-bot/
│       ├── Dockerfile
│       ├── requirements.txt
│       └── main.py             # Telegram bot for notifications + commands
├── scripts/
│   ├── record-ir.sh            # Helper to record IR codes interactively
│   └── train-wakeword.py       # Wake word model training script
├── docs/
│   └── plans/
│       └── 2026-02-23-clawdia-design.md
└── tests/
```

## API Keys Required

| Key | Service | Purpose |
|-----|---------|---------|
| `OPENROUTER_API_KEY` | OpenRouter | LLM calls for intent processing |
| `OPENAI_API_KEY` | OpenAI | Whisper STT API |
| `TELEGRAM_BOT_TOKEN` | Telegram BotFather | Clawdia's own Telegram bot |
| `TELEGRAM_CHAT_ID` | Telegram | Your chat ID for notifications |

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
