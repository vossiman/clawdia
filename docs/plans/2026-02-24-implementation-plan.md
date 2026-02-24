# Clawdia Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a single-process Raspberry Pi voice assistant that listens for "Hey Clawdia", transcribes speech via cloud STT, processes intent via PydanticAI/OpenRouter, controls a TV via IR, and communicates via Telegram.

**Architecture:** Monorepo, single Python process, asyncio event loop. All modules (brain, IR, telegram, voice) are imported directly - no inter-service HTTP. One Docker container for deployment on Pi 4B.

**Tech Stack:** Python 3.12, PydanticAI (OpenRouter), openai (Whisper STT), python-telegram-bot, openwakeword, PyAudio, ir-ctl (subprocess), pydantic-settings, pytest, Docker.

---

## Phase 1: Project Foundation

### Task 1.1: Initialize Python project

**Files:**
- Create: `pyproject.toml`
- Create: `src/clawdia/__init__.py`
- Create: `src/clawdia/config.py`
- Create: `.env.example`
- Create: `.gitignore`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

**Step 1: Create pyproject.toml**

```toml
[project]
name = "clawdia"
version = "0.1.0"
description = "Open-source Raspberry Pi voice assistant with IR TV control"
requires-python = ">=3.11"
dependencies = [
    "pydantic>=2.0",
    "pydantic-settings>=2.0",
    "pydantic-ai-slim[openrouter]>=1.0",
    "openai>=1.0",
    "python-telegram-bot>=22.0",
    "httpx>=0.27",
]

[project.optional-dependencies]
voice = [
    "openwakeword>=0.6",
    "pyaudio>=0.2",
    "numpy>=1.24",
    "scipy>=1.10",
]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
    "pytest-mock>=3.0",
    "ruff>=0.8",
]

[project.scripts]
clawdia = "clawdia.main:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/clawdia"]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"

[tool.ruff]
target-version = "py311"
line-length = 100
```

**Step 2: Create config module**

```python
# src/clawdia/config.py
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    # OpenRouter
    openrouter_api_key: str = ""
    openrouter_model: str = "anthropic/claude-3-haiku-20240307"

    # OpenAI (Whisper STT)
    openai_api_key: str = ""
    stt_model: str = "gpt-4o-mini-transcribe"

    # Telegram
    telegram_bot_token: str = ""
    telegram_chat_id: int = 0

    # IR
    ir_device_send: str = "/dev/lirc0"
    ir_device_receive: str = "/dev/lirc1"
    ir_codes_dir: str = "ir-codes"

    # Voice
    wake_word_model: str = "hey_jarvis"
    wake_word_threshold: float = 0.5
    audio_sample_rate: int = 16000
    audio_chunk_size: int = 1280

    # General
    debug: bool = False


settings = Settings()
```

**Step 3: Create .env.example**

```
# OpenRouter (LLM intent processing)
OPENROUTER_API_KEY=your-openrouter-key-here
OPENROUTER_MODEL=anthropic/claude-3-haiku-20240307

# OpenAI (Whisper STT)
OPENAI_API_KEY=your-openai-key-here

# Telegram Bot
TELEGRAM_BOT_TOKEN=your-telegram-bot-token
TELEGRAM_CHAT_ID=your-telegram-chat-id

# IR (adjust after checking /dev/lirc* on your Pi)
IR_DEVICE_SEND=/dev/lirc0
IR_DEVICE_RECEIVE=/dev/lirc1

# Debug
DEBUG=false
```

**Step 4: Create .gitignore**

```
__pycache__/
*.py[cod]
*.egg-info/
dist/
.eggs/
*.egg
.env
.venv/
venv/
*.pyc
.pytest_cache/
.ruff_cache/
ir-codes/
*.tflite
```

**Step 5: Create package init and test conftest**

```python
# src/clawdia/__init__.py
"""Clawdia - Open-source Raspberry Pi voice assistant with IR TV control."""
```

```python
# tests/__init__.py
```

```python
# tests/conftest.py
import pytest
from clawdia.config import Settings


@pytest.fixture
def test_settings():
    """Settings with test/dummy values."""
    return Settings(
        openrouter_api_key="test-key",
        openai_api_key="test-key",
        telegram_bot_token="test-token",
        telegram_chat_id=12345,
        ir_codes_dir="/tmp/test-ir-codes",
        debug=True,
    )
```

**Step 6: Install in dev mode and run tests**

Run: `pip install -e ".[dev]" && pytest tests/ -v`
Expected: 0 tests collected, no errors (clean install)

**Step 7: Commit**

```
git add -A
git commit -m "feat: initialize project structure with config and dependencies"
```

---

### Task 1.2: Write config tests

**Files:**
- Create: `tests/test_config.py`

**Step 1: Write tests for config loading**

```python
# tests/test_config.py
import os
from clawdia.config import Settings


def test_settings_defaults():
    s = Settings(openrouter_api_key="k", openai_api_key="k",
                 telegram_bot_token="t", telegram_chat_id=1)
    assert s.openrouter_model == "anthropic/claude-3-haiku-20240307"
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
```

**Step 2: Run tests**

Run: `pytest tests/test_config.py -v`
Expected: 2 passed

**Step 3: Commit**

```
git commit -am "test: add config settings tests"
```

---

## Phase 2: Brain Service (PydanticAI)

### Task 2.1: Define response models

**Files:**
- Create: `src/clawdia/brain/__init__.py`
- Create: `src/clawdia/brain/models.py`
- Create: `tests/test_brain_models.py`

**Step 1: Write tests for response models**

```python
# tests/test_brain_models.py
import pytest
from clawdia.brain.models import ClawdiaResponse, IRAction, TextAction


def test_ir_response():
    r = ClawdiaResponse(
        action="ir",
        ir=IRAction(command="power"),
        message="Turning off the TV",
    )
    assert r.action == "ir"
    assert r.ir.command == "power"
    assert r.message == "Turning off the TV"


def test_text_response():
    r = ClawdiaResponse(
        action="respond",
        message="The weather in Graz is 15 degrees.",
    )
    assert r.action == "respond"
    assert r.ir is None


def test_ir_response_requires_ir_field():
    with pytest.raises(Exception):
        ClawdiaResponse(action="ir", message="oops")  # missing ir field
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_brain_models.py -v`
Expected: FAIL (module not found)

**Step 3: Implement models**

```python
# src/clawdia/brain/__init__.py
```

```python
# src/clawdia/brain/models.py
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class IRAction(BaseModel):
    """An IR command to send to the TV."""
    command: str = Field(description="IR command name, e.g. 'power', 'vol_up', 'channel_3'")
    repeat: int = Field(default=1, description="Number of times to send the command", ge=1, le=10)


class ClawdiaResponse(BaseModel):
    """Structured response from the Clawdia brain."""
    action: Literal["ir", "respond"] = Field(
        description="'ir' to send an IR command, 'respond' to reply with text"
    )
    ir: IRAction | None = Field(default=None, description="IR command details, required if action='ir'")
    message: str = Field(description="Human-readable message describing what was done or the answer")

    @model_validator(mode="after")
    def ir_required_for_ir_action(self) -> ClawdiaResponse:
        if self.action == "ir" and self.ir is None:
            raise ValueError("'ir' field is required when action is 'ir'")
        return self
```

**Step 4: Run tests**

Run: `pytest tests/test_brain_models.py -v`
Expected: 3 passed

**Step 5: Commit**

```
git commit -am "feat: add brain response models with validation"
```

---

### Task 2.2: Build PydanticAI agent

**Files:**
- Create: `src/clawdia/brain/agent.py`
- Create: `tests/test_brain_agent.py`

**Step 1: Write agent tests (using test model)**

```python
# tests/test_brain_agent.py
import pytest
from pydantic_ai.models.test import TestModel

from clawdia.brain.agent import create_agent
from clawdia.brain.models import ClawdiaResponse


@pytest.fixture
def agent():
    return create_agent(model="test")


async def test_agent_returns_structured_response(agent):
    with agent.override(model=TestModel(custom_result_args={
        "action": "ir",
        "ir": {"command": "power"},
        "message": "Turning off the TV",
    })):
        result = await agent.run("Turn off the TV")
        assert isinstance(result.output, ClawdiaResponse)
        assert result.output.action == "ir"
        assert result.output.ir.command == "power"


async def test_agent_text_response(agent):
    with agent.override(model=TestModel(custom_result_args={
        "action": "respond",
        "message": "It is 15 degrees in Graz.",
    })):
        result = await agent.run("What's the weather?")
        assert result.output.action == "respond"
        assert "15 degrees" in result.output.message
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_brain_agent.py -v`
Expected: FAIL (module not found)

**Step 3: Implement agent**

```python
# src/clawdia/brain/agent.py
from __future__ import annotations

from pydantic_ai import Agent

from clawdia.brain.models import ClawdiaResponse

SYSTEM_PROMPT = """\
You are Clawdia, a voice-controlled home assistant running on a Raspberry Pi.

You can control a TV via infrared commands and answer general questions.

## Available IR Commands

TV control:
- power: Turn TV on/off
- vol_up: Volume up
- vol_down: Volume down
- mute: Toggle mute
- ch_up: Channel up
- ch_down: Channel down
- input_source: Switch input source
- num_0 through num_9: Number keys
- menu_up, menu_down, menu_left, menu_right: Menu navigation
- menu_ok: Confirm/select
- menu_back: Go back

## Rules

1. If the user wants to control the TV, respond with action="ir" and the appropriate command.
2. If the user asks a question or wants information, respond with action="respond" and your answer.
3. Always include a brief, friendly message describing what you did or your answer.
4. For channel numbers, use num_X commands (e.g., channel 3 = num_3). For multi-digit channels, \
the IR commands will be sent in sequence.
5. If you're unsure what the user wants, respond with action="respond" and ask for clarification.
"""


def create_agent(model: str = "openrouter:anthropic/claude-3-haiku-20240307") -> Agent:
    """Create the Clawdia PydanticAI agent."""
    return Agent(
        model,
        output_type=ClawdiaResponse,
        instructions=SYSTEM_PROMPT,
    )
```

**Step 4: Run tests**

Run: `pytest tests/test_brain_agent.py -v`
Expected: 2 passed

**Step 5: Commit**

```
git commit -am "feat: add PydanticAI brain agent with structured output"
```

---

### Task 2.3: Brain module public interface

**Files:**
- Modify: `src/clawdia/brain/__init__.py`
- Create: `tests/test_brain.py`

**Step 1: Write integration test**

```python
# tests/test_brain.py
import pytest
from pydantic_ai.models.test import TestModel

from clawdia.brain import Brain
from clawdia.brain.models import ClawdiaResponse


@pytest.fixture
def brain():
    return Brain(model="test")


async def test_brain_process_command(brain):
    with brain.agent.override(model=TestModel(custom_result_args={
        "action": "ir",
        "ir": {"command": "vol_up"},
        "message": "Turning volume up",
    })):
        response = await brain.process("Turn the volume up")
        assert isinstance(response, ClawdiaResponse)
        assert response.action == "ir"
        assert response.ir.command == "vol_up"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_brain.py -v`
Expected: FAIL

**Step 3: Implement Brain class**

```python
# src/clawdia/brain/__init__.py
from __future__ import annotations

from clawdia.brain.agent import create_agent
from clawdia.brain.models import ClawdiaResponse


class Brain:
    """High-level interface to the Clawdia intent engine."""

    def __init__(self, model: str = "openrouter:anthropic/claude-3-haiku-20240307"):
        self.agent = create_agent(model=model)

    async def process(self, text: str) -> ClawdiaResponse:
        """Process a text command and return a structured response."""
        result = await self.agent.run(text)
        return result.output
```

**Step 4: Run tests**

Run: `pytest tests/test_brain.py tests/test_brain_agent.py tests/test_brain_models.py -v`
Expected: All passed

**Step 5: Commit**

```
git commit -am "feat: add Brain class as public interface to intent engine"
```

---

## Phase 3: IR Control Module

### Task 3.1: IR controller

**Files:**
- Create: `src/clawdia/ir/__init__.py`
- Create: `src/clawdia/ir/controller.py`
- Create: `tests/test_ir.py`

**Step 1: Write tests**

```python
# tests/test_ir.py
import os
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from pathlib import Path

from clawdia.ir.controller import IRController


@pytest.fixture
def ir_codes_dir(tmp_path):
    codes_dir = tmp_path / "ir-codes"
    codes_dir.mkdir()
    # Create a fake IR code file
    (codes_dir / "power.txt").write_text("+889 -889 +1778 -1778\n")
    (codes_dir / "vol_up.txt").write_text("+889 -889 +889 -889\n")
    return codes_dir


@pytest.fixture
def controller(ir_codes_dir):
    return IRController(
        device_send="/dev/lirc0",
        codes_dir=str(ir_codes_dir),
    )


def test_list_commands(controller):
    commands = controller.list_commands()
    assert "power" in commands
    assert "vol_up" in commands


def test_has_command(controller):
    assert controller.has_command("power") is True
    assert controller.has_command("nonexistent") is False


async def test_send_command(controller):
    with patch("clawdia.ir.controller.asyncio") as mock_asyncio:
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"", b""))
        mock_asyncio.create_subprocess_exec = AsyncMock(return_value=mock_process)

        result = await controller.send(command="power")
        assert result is True

        mock_asyncio.create_subprocess_exec.assert_called_once()
        call_args = mock_asyncio.create_subprocess_exec.call_args[0]
        assert "ir-ctl" in call_args
        assert "--send" in " ".join(str(a) for a in call_args)


async def test_send_unknown_command(controller):
    result = await controller.send(command="nonexistent")
    assert result is False
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_ir.py -v`
Expected: FAIL

**Step 3: Implement IR controller**

```python
# src/clawdia/ir/__init__.py
from clawdia.ir.controller import IRController

__all__ = ["IRController"]
```

```python
# src/clawdia/ir/controller.py
from __future__ import annotations

import asyncio
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class IRController:
    """Controls IR sending/receiving via ir-ctl subprocess."""

    def __init__(self, device_send: str = "/dev/lirc0", codes_dir: str = "ir-codes"):
        self.device_send = device_send
        self.codes_dir = Path(codes_dir)
        self.codes_dir.mkdir(parents=True, exist_ok=True)

    def list_commands(self) -> list[str]:
        """List all available IR command names."""
        return sorted(
            p.stem for p in self.codes_dir.glob("*.txt")
        )

    def has_command(self, command: str) -> bool:
        """Check if an IR command code file exists."""
        return (self.codes_dir / f"{command}.txt").is_file()

    def get_code_path(self, command: str) -> Path | None:
        """Get the path to an IR code file."""
        path = self.codes_dir / f"{command}.txt"
        return path if path.is_file() else None

    async def send(self, command: str, repeat: int = 1) -> bool:
        """Send an IR command via ir-ctl.

        Returns True if successful, False otherwise.
        """
        code_path = self.get_code_path(command)
        if code_path is None:
            logger.warning("IR command '%s' not found in %s", command, self.codes_dir)
            return False

        for i in range(repeat):
            try:
                process = await asyncio.create_subprocess_exec(
                    "ir-ctl",
                    "-d", self.device_send,
                    f"--send={code_path}",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await process.communicate()

                if process.returncode != 0:
                    logger.error(
                        "ir-ctl send failed (code %d): %s",
                        process.returncode,
                        stderr.decode().strip(),
                    )
                    return False

                if repeat > 1 and i < repeat - 1:
                    await asyncio.sleep(0.1)  # small gap between repeats

            except FileNotFoundError:
                logger.error("ir-ctl not found. Install v4l-utils: sudo apt install v4l-utils")
                return False

        logger.info("IR command '%s' sent successfully (repeat=%d)", command, repeat)
        return True

    async def record(self, command: str, timeout: float = 10.0) -> bool:
        """Record an IR code from the receiver.

        Returns True if a code was captured, False on timeout/error.
        """
        code_path = self.codes_dir / f"{command}.txt"

        try:
            process = await asyncio.create_subprocess_exec(
                "ir-ctl",
                "-d", self.device_send.replace("lirc0", "lirc1"),  # use receiver device
                "-r", "--one-shot",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=timeout
            )

            if process.returncode == 0 and stdout:
                code_path.write_bytes(stdout)
                logger.info("IR code recorded: %s -> %s", command, code_path)
                return True

            logger.warning("IR recording returned no data for '%s'", command)
            return False

        except asyncio.TimeoutError:
            process.kill()
            logger.warning("IR recording timed out for '%s'", command)
            return False
        except FileNotFoundError:
            logger.error("ir-ctl not found. Install v4l-utils.")
            return False
```

**Step 4: Run tests**

Run: `pytest tests/test_ir.py -v`
Expected: All passed

**Step 5: Commit**

```
git commit -am "feat: add IR controller with send/record via ir-ctl"
```

---

## Phase 4: Telegram Bot

### Task 4.1: Telegram bot module

**Files:**
- Create: `src/clawdia/telegram_bot/__init__.py`
- Create: `src/clawdia/telegram_bot/bot.py`
- Create: `tests/test_telegram.py`

**Step 1: Write tests**

```python
# tests/test_telegram.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from clawdia.telegram_bot.bot import ClawdiaTelegramBot


@pytest.fixture
def mock_brain():
    brain = AsyncMock()
    return brain


@pytest.fixture
def bot(mock_brain):
    return ClawdiaTelegramBot(
        token="test-token",
        chat_id=12345,
        brain=mock_brain,
    )


def test_bot_initialization(bot):
    assert bot.chat_id == 12345
    assert bot.brain is not None


async def test_notify(bot):
    with patch.object(bot, "_bot") as mock_bot:
        mock_bot.send_message = AsyncMock()
        await bot.notify("Test message")
        mock_bot.send_message.assert_called_once_with(
            chat_id=12345, text="Test message"
        )
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_telegram.py -v`
Expected: FAIL

**Step 3: Implement Telegram bot**

```python
# src/clawdia/telegram_bot/__init__.py
from clawdia.telegram_bot.bot import ClawdiaTelegramBot

__all__ = ["ClawdiaTelegramBot"]
```

```python
# src/clawdia/telegram_bot/bot.py
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import telegram
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

if TYPE_CHECKING:
    from clawdia.brain import Brain

logger = logging.getLogger(__name__)


class ClawdiaTelegramBot:
    """Telegram bot for Clawdia - receives commands, sends notifications."""

    def __init__(self, token: str, chat_id: int, brain: Brain):
        self.token = token
        self.chat_id = chat_id
        self.brain = brain
        self._bot = telegram.Bot(token=token)
        self._app: Application | None = None

    async def notify(self, text: str) -> None:
        """Send a notification message to the configured chat."""
        try:
            await self._bot.send_message(chat_id=self.chat_id, text=text)
        except Exception:
            logger.exception("Failed to send Telegram notification")

    def _build_app(self) -> Application:
        """Build the Telegram application with handlers."""
        app = Application.builder().token(self.token).build()
        app.add_handler(CommandHandler("start", self._handle_start))
        app.add_handler(CommandHandler("ir", self._handle_ir_list))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message))
        return app

    async def _handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command."""
        await update.message.reply_text(
            "Hi! I'm Clawdia, your home assistant.\n\n"
            "Send me a message and I'll process it.\n"
            "Use /ir to see available IR commands."
        )

    async def _handle_ir_list(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /ir command - list available IR commands."""
        # This will be connected to the IR controller later
        await update.message.reply_text("IR command listing coming soon.")

    async def _handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle text messages - send to brain for processing."""
        if update.effective_chat.id != self.chat_id:
            await update.message.reply_text("Sorry, I only respond to my owner.")
            return

        text = update.message.text
        logger.info("Telegram message received: %s", text)

        try:
            response = await self.brain.process(text)
            await update.message.reply_text(response.message)
            # Return the response for the orchestrator to act on
            # (IR commands are handled by the orchestrator, not here)
        except Exception:
            logger.exception("Error processing message")
            await update.message.reply_text("Sorry, something went wrong.")

    async def start(self) -> None:
        """Start the Telegram bot (non-blocking, uses polling)."""
        self._app = self._build_app()
        await self._app.initialize()
        await self._app.start()
        await self._app.updater.start_polling(allowed_updates=Update.ALL_TYPES)
        logger.info("Telegram bot started")

    async def stop(self) -> None:
        """Stop the Telegram bot."""
        if self._app:
            await self._app.updater.stop()
            await self._app.stop()
            await self._app.shutdown()
            logger.info("Telegram bot stopped")
```

**Step 4: Run tests**

Run: `pytest tests/test_telegram.py -v`
Expected: All passed

**Step 5: Commit**

```
git commit -am "feat: add Telegram bot with message handling and notifications"
```

---

## Phase 5: Voice Pipeline (Wake Word + STT)

### Task 5.1: STT module (OpenAI Whisper)

**Files:**
- Create: `src/clawdia/voice/__init__.py`
- Create: `src/clawdia/voice/stt.py`
- Create: `tests/test_stt.py`

**Step 1: Write tests**

```python
# tests/test_stt.py
import io
import wave
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from clawdia.voice.stt import SpeechToText


@pytest.fixture
def stt():
    return SpeechToText(api_key="test-key", model="gpt-4o-mini-transcribe")


def _make_wav_bytes(duration_s: float = 1.0, sample_rate: int = 16000) -> bytes:
    """Generate silent WAV bytes for testing."""
    import struct
    n_samples = int(sample_rate * duration_s)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00\x00" * n_samples)
    return buf.getvalue()


async def test_transcribe(stt):
    wav_bytes = _make_wav_bytes()

    mock_response = MagicMock()
    mock_response.text = "turn off the tv"

    with patch("clawdia.voice.stt.openai.AsyncOpenAI") as MockClient:
        mock_client = AsyncMock()
        mock_client.audio.transcriptions.create = AsyncMock(return_value=mock_response)
        MockClient.return_value = mock_client

        stt_instance = SpeechToText(api_key="test-key")
        result = await stt_instance.transcribe(wav_bytes)
        assert result == "turn off the tv"


def test_pcm_to_wav(stt):
    """Test that raw PCM samples can be wrapped in WAV format."""
    import numpy as np
    pcm_data = np.zeros(16000, dtype=np.int16).tobytes()  # 1 second of silence
    wav_bytes = stt.pcm_to_wav(pcm_data)
    assert wav_bytes[:4] == b"RIFF"  # WAV header
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_stt.py -v`
Expected: FAIL

**Step 3: Implement STT module**

```python
# src/clawdia/voice/__init__.py
```

```python
# src/clawdia/voice/stt.py
from __future__ import annotations

import io
import logging
import wave

import openai

logger = logging.getLogger(__name__)


class SpeechToText:
    """Transcribe audio using OpenAI Whisper API."""

    def __init__(self, api_key: str, model: str = "gpt-4o-mini-transcribe"):
        self.model = model
        self._client = openai.AsyncOpenAI(api_key=api_key)

    def pcm_to_wav(self, pcm_data: bytes, sample_rate: int = 16000) -> bytes:
        """Wrap raw PCM int16 mono data in a WAV container."""
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(pcm_data)
        return buf.getvalue()

    async def transcribe(self, audio_bytes: bytes, language: str = "en") -> str:
        """Transcribe WAV audio bytes to text.

        Args:
            audio_bytes: WAV-formatted audio data.
            language: Language hint for the model.

        Returns:
            Transcribed text string.
        """
        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = "audio.wav"

        try:
            response = await self._client.audio.transcriptions.create(
                model=self.model,
                file=audio_file,
                language=language,
            )
            text = response.text.strip()
            logger.info("STT result: '%s'", text)
            return text
        except Exception:
            logger.exception("STT transcription failed")
            return ""
```

**Step 4: Run tests**

Run: `pytest tests/test_stt.py -v`
Expected: All passed

**Step 5: Commit**

```
git commit -am "feat: add speech-to-text module using OpenAI Whisper API"
```

---

### Task 5.2: Wake word listener (stub for pre-hardware)

**Files:**
- Create: `src/clawdia/voice/listener.py`
- Create: `tests/test_listener.py`

**Step 1: Write tests**

```python
# tests/test_listener.py
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import asyncio

from clawdia.voice.listener import WakeWordListener


def test_listener_init():
    listener = WakeWordListener(
        model_path="hey_jarvis",
        threshold=0.5,
        sample_rate=16000,
        chunk_size=1280,
    )
    assert listener.threshold == 0.5
    assert listener.sample_rate == 16000


async def test_listener_callback_called():
    """Test that the on_wake_word callback is invoked correctly."""
    callback = AsyncMock()
    listener = WakeWordListener(
        model_path="hey_jarvis",
        threshold=0.5,
        on_wake_word=callback,
    )
    # Simulate a wake word detection
    await listener._on_detected()
    callback.assert_called_once()
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_listener.py -v`
Expected: FAIL

**Step 3: Implement listener (with hardware-optional design)**

```python
# src/clawdia/voice/listener.py
from __future__ import annotations

import asyncio
import logging
from typing import Callable, Awaitable

logger = logging.getLogger(__name__)


class WakeWordListener:
    """Listens for wake word using openWakeWord.

    Designed to work without hardware for testing - actual mic capture
    is only started when start_listening() is called on a Pi with a mic.
    """

    def __init__(
        self,
        model_path: str = "hey_jarvis",
        threshold: float = 0.5,
        sample_rate: int = 16000,
        chunk_size: int = 1280,
        on_wake_word: Callable[[], Awaitable[None]] | None = None,
    ):
        self.model_path = model_path
        self.threshold = threshold
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.on_wake_word = on_wake_word
        self._running = False
        self._oww_model = None

    async def _on_detected(self) -> None:
        """Called when wake word is detected."""
        logger.info("Wake word detected!")
        if self.on_wake_word:
            await self.on_wake_word()

    def _init_model(self):
        """Initialize the openWakeWord model. Requires openwakeword package."""
        try:
            from openwakeword.model import Model
            self._oww_model = Model(
                wakeword_models=[self.model_path] if not self.model_path.startswith("hey_") else [],
                inference_framework="tflite",
            )
            logger.info("Wake word model loaded: %s", self.model_path)
        except ImportError:
            logger.warning("openwakeword not installed. Wake word detection disabled.")
        except Exception:
            logger.exception("Failed to load wake word model")

    async def start_listening(self) -> None:
        """Start listening for the wake word on the microphone.

        This blocks in a loop until stop() is called.
        Requires: openwakeword, pyaudio, and a working microphone.
        """
        try:
            import pyaudio
            import numpy as np
        except ImportError:
            logger.error("pyaudio/numpy not installed. Install with: pip install clawdia[voice]")
            return

        self._init_model()
        if self._oww_model is None:
            logger.error("No wake word model available. Cannot listen.")
            return

        audio = pyaudio.PyAudio()
        stream = audio.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=self.sample_rate,
            input=True,
            frames_per_buffer=self.chunk_size,
        )

        self._running = True
        logger.info("Listening for wake word '%s'...", self.model_path)

        try:
            while self._running:
                audio_frame = np.frombuffer(
                    stream.read(self.chunk_size, exception_on_overflow=False),
                    dtype=np.int16,
                )
                predictions = self._oww_model.predict(audio_frame)

                for model_name, score in predictions.items():
                    if score > self.threshold:
                        await self._on_detected()

                # Yield to the event loop
                await asyncio.sleep(0)
        finally:
            stream.stop_stream()
            stream.close()
            audio.terminate()

    async def capture_audio(self, duration: float = 5.0) -> bytes:
        """Capture audio from mic for a given duration. Returns raw PCM bytes.

        Requires pyaudio.
        """
        try:
            import pyaudio
        except ImportError:
            logger.error("pyaudio not installed")
            return b""

        audio = pyaudio.PyAudio()
        stream = audio.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=self.sample_rate,
            input=True,
            frames_per_buffer=self.chunk_size,
        )

        frames = []
        num_chunks = int(self.sample_rate / self.chunk_size * duration)

        logger.info("Capturing audio for %.1fs...", duration)
        for _ in range(num_chunks):
            data = stream.read(self.chunk_size, exception_on_overflow=False)
            frames.append(data)
            await asyncio.sleep(0)

        stream.stop_stream()
        stream.close()
        audio.terminate()

        return b"".join(frames)

    def stop(self) -> None:
        """Stop listening."""
        self._running = False
```

**Step 4: Run tests**

Run: `pytest tests/test_listener.py -v`
Expected: All passed

**Step 5: Commit**

```
git commit -am "feat: add wake word listener with hardware-optional design"
```

---

## Phase 6: Orchestrator + Main Entry Point

### Task 6.1: Orchestrator

**Files:**
- Create: `src/clawdia/orchestrator.py`
- Create: `tests/test_orchestrator.py`

**Step 1: Write tests**

```python
# tests/test_orchestrator.py
import pytest
from unittest.mock import AsyncMock, MagicMock

from clawdia.brain.models import ClawdiaResponse, IRAction
from clawdia.orchestrator import Orchestrator


@pytest.fixture
def mock_brain():
    brain = AsyncMock()
    return brain


@pytest.fixture
def mock_ir():
    ir = AsyncMock()
    ir.has_command.return_value = True
    ir.send.return_value = True
    return ir


@pytest.fixture
def mock_telegram():
    tg = AsyncMock()
    return tg


@pytest.fixture
def orchestrator(mock_brain, mock_ir, mock_telegram):
    return Orchestrator(brain=mock_brain, ir=mock_ir, telegram=mock_telegram)


async def test_handle_ir_command(orchestrator, mock_brain, mock_ir, mock_telegram):
    response = ClawdiaResponse(
        action="ir",
        ir=IRAction(command="power"),
        message="Turning off the TV",
    )
    mock_brain.process.return_value = response

    await orchestrator.handle_text_command("Turn off the TV")

    mock_brain.process.assert_called_once_with("Turn off the TV")
    mock_ir.send.assert_called_once_with(command="power", repeat=1)
    mock_telegram.notify.assert_called_once_with("Turning off the TV")


async def test_handle_text_response(orchestrator, mock_brain, mock_ir, mock_telegram):
    response = ClawdiaResponse(
        action="respond",
        message="It's 15 degrees in Graz.",
    )
    mock_brain.process.return_value = response

    await orchestrator.handle_text_command("What's the weather?")

    mock_brain.process.assert_called_once()
    mock_ir.send.assert_not_called()
    mock_telegram.notify.assert_called_once_with("It's 15 degrees in Graz.")


async def test_handle_ir_command_unknown(orchestrator, mock_brain, mock_ir, mock_telegram):
    response = ClawdiaResponse(
        action="ir",
        ir=IRAction(command="nonexistent"),
        message="Sending command",
    )
    mock_brain.process.return_value = response
    mock_ir.has_command.return_value = False

    await orchestrator.handle_text_command("Do something weird")

    mock_ir.send.assert_not_called()
    # Should notify about the error
    assert mock_telegram.notify.call_count == 1
    assert "not found" in mock_telegram.notify.call_args[0][0].lower() or \
           "not available" in mock_telegram.notify.call_args[0][0].lower()
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_orchestrator.py -v`
Expected: FAIL

**Step 3: Implement orchestrator**

```python
# src/clawdia/orchestrator.py
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from clawdia.brain import Brain
    from clawdia.ir import IRController
    from clawdia.telegram_bot import ClawdiaTelegramBot
    from clawdia.voice.stt import SpeechToText

logger = logging.getLogger(__name__)


class Orchestrator:
    """Coordinates the full Clawdia pipeline.

    Connects: voice -> STT -> brain -> action routing (IR / Telegram).
    """

    def __init__(
        self,
        brain: Brain,
        ir: IRController,
        telegram: ClawdiaTelegramBot,
        stt: SpeechToText | None = None,
    ):
        self.brain = brain
        self.ir = ir
        self.telegram = telegram
        self.stt = stt

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
```

**Step 4: Run tests**

Run: `pytest tests/test_orchestrator.py -v`
Expected: All passed

**Step 5: Commit**

```
git commit -am "feat: add orchestrator to coordinate brain, IR, and Telegram"
```

---

### Task 6.2: Main entry point

**Files:**
- Create: `src/clawdia/main.py`

**Step 1: Implement main.py**

```python
# src/clawdia/main.py
from __future__ import annotations

import asyncio
import logging
import signal
import sys

from clawdia.config import settings
from clawdia.brain import Brain
from clawdia.ir import IRController
from clawdia.orchestrator import Orchestrator
from clawdia.telegram_bot import ClawdiaTelegramBot

logger = logging.getLogger(__name__)


async def run() -> None:
    """Main async entry point for Clawdia."""
    logging.basicConfig(
        level=logging.DEBUG if settings.debug else logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    logger.info("Starting Clawdia...")

    # Initialize components
    brain = Brain(model=f"openrouter:{settings.openrouter_model}")

    ir = IRController(
        device_send=settings.ir_device_send,
        codes_dir=settings.ir_codes_dir,
    )

    telegram = ClawdiaTelegramBot(
        token=settings.telegram_bot_token,
        chat_id=settings.telegram_chat_id,
        brain=brain,
    )

    # Optional: STT (needs OpenAI API key)
    stt = None
    if settings.openai_api_key:
        from clawdia.voice.stt import SpeechToText
        stt = SpeechToText(
            api_key=settings.openai_api_key,
            model=settings.stt_model,
        )

    orchestrator = Orchestrator(
        brain=brain,
        ir=ir,
        telegram=telegram,
        stt=stt,
    )

    # Wire up Telegram message handler to orchestrator
    original_handler = telegram._handle_message

    async def enhanced_message_handler(update, context):
        """Enhanced handler that routes brain responses through orchestrator."""
        if update.effective_chat.id != telegram.chat_id:
            await update.message.reply_text("Sorry, I only respond to my owner.")
            return

        text = update.message.text
        logger.info("Telegram command: %s", text)
        await orchestrator.handle_text_command(text)

    telegram._handle_message = enhanced_message_handler

    # Start services
    await telegram.start()
    await telegram.notify("Clawdia is online!")
    logger.info("Clawdia is running. Telegram bot active. Ctrl+C to stop.")

    # Optional: Start wake word listener (needs hardware)
    listener_task = None
    try:
        from clawdia.voice.listener import WakeWordListener

        async def on_wake_word():
            logger.info("Wake word detected! Capturing audio...")
            audio_data = await listener.capture_audio(duration=5.0)
            await orchestrator.handle_audio(audio_data)

        listener = WakeWordListener(
            model_path=settings.wake_word_model,
            threshold=settings.wake_word_threshold,
            sample_rate=settings.audio_sample_rate,
            chunk_size=settings.audio_chunk_size,
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
```

**Step 2: Verify it imports cleanly**

Run: `python -c "from clawdia.main import main; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```
git commit -am "feat: add main entry point with full pipeline wiring"
```

---

## Phase 7: Docker Deployment

### Task 7.1: Dockerfile and docker-compose

**Files:**
- Create: `Dockerfile`
- Create: `docker-compose.yml`

**Step 1: Create Dockerfile**

```dockerfile
FROM python:3.12-slim

# System deps for pyaudio and ir-ctl
RUN apt-get update && apt-get install -y --no-install-recommends \
    portaudio19-dev \
    v4l-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps
COPY pyproject.toml .
RUN pip install --no-cache-dir ".[voice]"

# Copy source
COPY src/ src/

# Install the package
RUN pip install --no-cache-dir -e .

# Create IR codes directory
RUN mkdir -p ir-codes

CMD ["python", "-m", "clawdia.main"]
```

**Step 2: Create docker-compose.yml**

```yaml
services:
  clawdia:
    build: .
    restart: unless-stopped
    env_file: .env
    devices:
      - /dev/lirc0:/dev/lirc0
      - /dev/lirc1:/dev/lirc1
      - /dev/snd:/dev/snd
    volumes:
      - ./ir-codes:/app/ir-codes
      - ./models:/app/models
    environment:
      - PULSE_SERVER=unix:/run/user/1000/pulse/native
    volumes:
      - /run/user/1000/pulse:/run/user/1000/pulse
```

**Step 3: Commit**

```
git commit -am "feat: add Dockerfile and docker-compose for Pi deployment"
```

---

## Phase Summary

| Phase | What | Can Test Without Hardware |
|-------|------|--------------------------|
| 1 | Project foundation, config, deps | Yes |
| 2 | PydanticAI brain + intent engine | Yes (test model) |
| 3 | IR controller (ir-ctl wrapper) | Yes (mocked subprocess) |
| 4 | Telegram bot | Yes (with real token) |
| 5 | Voice pipeline (wake word + STT) | STT yes, wake word needs mic |
| 6 | Orchestrator + main entry point | Yes (all mocked) |
| 7 | Docker deployment | Needs Pi |

## Testing Strategy

- **Unit tests:** Each module tested in isolation with mocks
- **Integration test (Telegram):** With a real bot token, send a message and verify response
- **Integration test (Brain):** With a real OpenRouter key, verify structured output
- **Hardware test (on Pi):** Full pipeline with mic, IR, and Telegram

## First Run Checklist (when hardware arrives)

1. Flash Raspberry Pi OS to SD card
2. Boot Pi, connect via SSH
3. Install Docker: `curl -fsSL https://get.docker.com | sh`
4. Clone repo, copy `.env.example` to `.env`, fill in API keys
5. Configure IR GPIO in `/boot/config.txt` (add dtoverlays)
6. Wire up KY-022 (GPIO 22) and KY-005 + transistor (GPIO 24)
7. Attach ReSpeaker 2-Mic HAT
8. Reboot
9. Record TV remote IR codes: `ir-ctl -d /dev/lirc1 -r --one-shot > ir-codes/power.txt`
10. Run: `docker compose up --build`
11. Send "Turn off the TV" via Telegram -> TV should turn off
