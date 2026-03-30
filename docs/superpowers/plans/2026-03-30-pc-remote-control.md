# PC Remote Control Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable remote control of a Linux PC via Telegram commands, using SSH for transport and Claude Computer Use for GUI interactions.

**Architecture:** The brain gains two new action types (`pc` and `learn`). Simple shell commands execute directly via SSH. GUI interactions invoke a standalone PC agent that runs a computer use loop (screenshot → Claude vision → xdotool action → repeat). A YAML knowledge base of learned facts feeds into system prompts and grows via user corrections.

**Tech Stack:** Python 3.11+, asyncio subprocess (SSH), anthropic SDK (computer use), scrot + xdotool (PC-side), PyYAML (knowledge base)

**Note — multi-step orchestrator loop (deferred to v2):** The spec describes the orchestrator calling the brain in a loop for multi-step commands (e.g., shell to open browser → then computer_use to navigate). In v1, the brain emits a single action per command. For "open Emby and play Stranger Things", the brain should emit a single `computer_use` action with the full goal — the PC agent handles the complete sequence (opening browser + navigating) within its own loop. The orchestrator loop optimization can be added later if needed.

---

## File Structure

### New files

| File | Responsibility |
|------|---------------|
| `src/clawdia/pc/__init__.py` | Package init, exports `PCController` |
| `src/clawdia/pc/controller.py` | SSH command execution + PC agent invocation |
| `src/clawdia/pc/knowledge.py` | YAML knowledge base read/write |
| `src/clawdia/pc_agent/__init__.py` | Package init |
| `src/clawdia/pc_agent/__main__.py` | CLI entry point for computer use agent |
| `src/clawdia/pc_agent/agent.py` | Computer use loop: screenshot → Claude → action → repeat |
| `src/clawdia/pc_agent/actions.py` | Action executors: click, type, key via xdotool/scrot |
| `pc_knowledge.yaml` | Knowledge base file (project root) |
| `tests/test_pc_knowledge.py` | Knowledge base tests |
| `tests/test_pc_controller.py` | SSH executor tests |
| `tests/test_pc_models.py` | PC action model tests |
| `tests/test_pc_orchestrator.py` | Orchestrator PC routing tests |
| `tests/test_pc_agent_actions.py` | PC agent action executor tests |
| `tests/test_pc_agent.py` | Computer use loop tests |

### Modified files

| File | Change |
|------|--------|
| `src/clawdia/config.py` | Add PC SSH settings |
| `src/clawdia/brain/models.py` | Add `PCAction`, `LearnAction`, extend `ClawdiaResponse` |
| `src/clawdia/brain/agent.py` | Add PC section to system prompt, accept knowledge base |
| `src/clawdia/orchestrator.py` | Handle `pc` and `learn` action routing |
| `src/clawdia/main.py` | Wire up `PCController` and knowledge base |
| `src/clawdia/telegram_bot/bot.py` | Add `/pc` command to list PC capabilities |
| `.env.example` | Add PC SSH config vars |
| `pyproject.toml` | Add `pyyaml` dependency, `pc-agent` entry point |

---

### Task 1: Configuration

**Files:**
- Modify: `src/clawdia/config.py:1-41`
- Modify: `.env.example`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**

In `tests/test_config.py`, add:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/vossi/local_dev/clawdia && python -m pytest tests/test_config.py::test_pc_settings_defaults tests/test_config.py::test_pc_enabled_when_configured -v`
Expected: FAIL — `Settings` has no `pc_ssh_host` attribute

- [ ] **Step 3: Write minimal implementation**

In `src/clawdia/config.py`, add to the `Settings` class after the Spotify section:

```python
    # PC Remote Control
    pc_ssh_host: str = ""
    pc_ssh_user: str = ""
    pc_ssh_key_path: str = "~/.ssh/id_ed25519"
    pc_agent_path: str = "~/clawdia-agent"

    @property
    def pc_enabled(self) -> bool:
        return bool(self.pc_ssh_host and self.pc_ssh_user)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/vossi/local_dev/clawdia && python -m pytest tests/test_config.py -v`
Expected: PASS

- [ ] **Step 5: Update .env.example**

Add to `.env.example`:

```
# PC Remote Control
PC_SSH_HOST=
PC_SSH_USER=
PC_SSH_KEY_PATH=~/.ssh/id_ed25519
PC_AGENT_PATH=~/clawdia-agent
```

- [ ] **Step 6: Commit**

```bash
git add src/clawdia/config.py tests/test_config.py .env.example
git commit -m "feat(pc): add PC SSH configuration settings"
```

---

### Task 2: Knowledge Base

**Files:**
- Create: `src/clawdia/pc/__init__.py`
- Create: `src/clawdia/pc/knowledge.py`
- Create: `pc_knowledge.yaml`
- Test: `tests/test_pc_knowledge.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_pc_knowledge.py`:

```python
import pytest
from pathlib import Path
from clawdia.pc.knowledge import KnowledgeBase


@pytest.fixture
def kb_path(tmp_path):
    return tmp_path / "knowledge.yaml"


@pytest.fixture
def kb(kb_path):
    return KnowledgeBase(kb_path)


def test_load_empty(kb):
    assert kb.to_prompt_context() == ""


def test_load_existing(kb_path):
    kb_path.write_text(
        "pc:\n  browser: firefox\nservices:\n  emby:\n    url: http://emby:8096\n"
    )
    kb = KnowledgeBase(kb_path)
    context = kb.to_prompt_context()
    assert "firefox" in context
    assert "emby" in context
    assert "http://emby:8096" in context


def test_update_section(kb, kb_path):
    kb.update("pc", "browser", "firefox")
    kb2 = KnowledgeBase(kb_path)
    assert kb2.data["pc"]["browser"] == "firefox"


def test_update_nested_section(kb, kb_path):
    kb.update("services", "emby", {"url": "http://emby:8096", "username": "vossi"})
    kb2 = KnowledgeBase(kb_path)
    assert kb2.data["services"]["emby"]["url"] == "http://emby:8096"


def test_add_preference(kb, kb_path):
    kb.add_preference("use keyboard shortcuts when possible")
    kb2 = KnowledgeBase(kb_path)
    assert "use keyboard shortcuts when possible" in kb2.data["preferences"]


def test_add_correction(kb, kb_path):
    kb.add_correction("open emby", "emby is at http://emby:8096, not emby.media")
    kb2 = KnowledgeBase(kb_path)
    assert len(kb2.data["corrections"]) == 1
    assert kb2.data["corrections"][0]["trigger"] == "open emby"
    assert "emby:8096" in kb2.data["corrections"][0]["learned"]


def test_to_prompt_context_formatted(kb):
    kb.update("pc", "browser", "firefox")
    kb.update("services", "emby", {"url": "http://emby:8096"})
    kb.add_preference("fullscreen browser after opening")
    kb.add_correction("open emby", "use local URL not emby.media")
    context = kb.to_prompt_context()
    assert "browser: firefox" in context
    assert "emby" in context
    assert "fullscreen" in context
    assert "use local URL" in context
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/vossi/local_dev/clawdia && python -m pytest tests/test_pc_knowledge.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'clawdia.pc'`

- [ ] **Step 3: Create package init**

Create `src/clawdia/pc/__init__.py`:

```python
from clawdia.pc.knowledge import KnowledgeBase

__all__ = ["KnowledgeBase"]
```

- [ ] **Step 4: Write implementation**

Create `src/clawdia/pc/knowledge.py`:

```python
from __future__ import annotations

from datetime import date
from pathlib import Path

import yaml


class KnowledgeBase:
    """YAML-backed knowledge base of learned facts about the user's PC setup."""

    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.data: dict = {}
        if self.path.exists():
            text = self.path.read_text()
            if text.strip():
                self.data = yaml.safe_load(text) or {}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(yaml.dump(self.data, default_flow_style=False, sort_keys=False))

    def update(self, section: str, key: str, value: str | dict) -> None:
        if section not in self.data:
            self.data[section] = {}
        self.data[section][key] = value
        self._save()

    def add_preference(self, preference: str) -> None:
        if "preferences" not in self.data:
            self.data["preferences"] = []
        if preference not in self.data["preferences"]:
            self.data["preferences"].append(preference)
        self._save()

    def add_correction(self, trigger: str, learned: str) -> None:
        if "corrections" not in self.data:
            self.data["corrections"] = []
        self.data["corrections"].append({
            "trigger": trigger,
            "learned": learned,
            "date": str(date.today()),
        })
        self._save()

    def to_prompt_context(self) -> str:
        if not self.data:
            return ""
        return yaml.dump(self.data, default_flow_style=False, sort_keys=False).strip()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /home/vossi/local_dev/clawdia && python -m pytest tests/test_pc_knowledge.py -v`
Expected: PASS

- [ ] **Step 6: Create initial knowledge base file**

Create `pc_knowledge.yaml` at project root:

```yaml
# Clawdia PC Knowledge Base
# This file is updated automatically when you correct Clawdia.
# You can also edit it manually.
```

- [ ] **Step 7: Add pyyaml dependency**

In `pyproject.toml`, add `"pyyaml>=6.0"` to the `dependencies` list.

- [ ] **Step 8: Commit**

```bash
git add src/clawdia/pc/ tests/test_pc_knowledge.py pc_knowledge.yaml pyproject.toml
git commit -m "feat(pc): add YAML knowledge base for PC facts and corrections"
```

---

### Task 3: Brain Models

**Files:**
- Modify: `src/clawdia/brain/models.py:1-47`
- Test: `tests/test_pc_models.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_pc_models.py`:

```python
import pytest
from clawdia.brain.models import ClawdiaResponse, PCAction, LearnAction


def test_pc_shell_response():
    r = ClawdiaResponse(
        action="pc",
        pc=PCAction(command_type="shell", shell_command="firefox http://emby:8096"),
        message="Opening Emby in Firefox",
    )
    assert r.action == "pc"
    assert r.pc.command_type == "shell"
    assert r.pc.shell_command == "firefox http://emby:8096"
    assert r.pc.goal is None


def test_pc_computer_use_response():
    r = ClawdiaResponse(
        action="pc",
        pc=PCAction(command_type="computer_use", goal="navigate to TV Shows in Emby"),
        message="Navigating Emby",
    )
    assert r.pc.command_type == "computer_use"
    assert r.pc.goal == "navigate to TV Shows in Emby"
    assert r.pc.shell_command is None


def test_pc_response_requires_pc_field():
    with pytest.raises(Exception):
        ClawdiaResponse(action="pc", message="oops")


def test_learn_response():
    r = ClawdiaResponse(
        action="learn",
        learn=LearnAction(
            section="services",
            key="emby",
            value={"url": "http://192.168.1.50:8096"},
        ),
        message="Got it, I'll remember that.",
    )
    assert r.action == "learn"
    assert r.learn.section == "services"
    assert r.learn.key == "emby"


def test_learn_response_requires_learn_field():
    with pytest.raises(Exception):
        ClawdiaResponse(action="learn", message="oops")


def test_existing_ir_response_still_works():
    from clawdia.brain.models import IRAction
    r = ClawdiaResponse(
        action="ir",
        ir=IRAction(command="power"),
        message="Turning off the TV",
    )
    assert r.action == "ir"


def test_existing_respond_still_works():
    r = ClawdiaResponse(action="respond", message="Hello!")
    assert r.action == "respond"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/vossi/local_dev/clawdia && python -m pytest tests/test_pc_models.py -v`
Expected: FAIL — `ImportError: cannot import name 'PCAction'`

- [ ] **Step 3: Write implementation**

In `src/clawdia/brain/models.py`, add the new models and update `ClawdiaResponse`:

```python
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class IRAction(BaseModel):
    """An IR command to send to the TV."""
    command: str = Field(description="IR command name, e.g. 'power', 'vol_up', 'channel_3'")
    repeat: int = Field(default=1, description="Number of times to send the command", ge=1, le=10)


class MusicAction(BaseModel):
    """A music playback command."""
    command: Literal[
        "play", "pause", "skip", "previous", "volume",
        "search", "play_query", "play_playlist", "queue",
        "now_playing", "list_playlists",
    ] = Field(description="Music command to execute")
    query: str | None = Field(default=None, description="Search query or playlist name")
    volume: int | None = Field(default=None, description="Volume level 0-100", ge=0, le=100)


class PCAction(BaseModel):
    """A command to execute on the remote Linux PC."""
    command_type: Literal["shell", "computer_use"] = Field(
        description="'shell' for direct commands, 'computer_use' for GUI interaction"
    )
    shell_command: str | None = Field(
        default=None, description="Shell command to run, required if command_type='shell'"
    )
    goal: str | None = Field(
        default=None, description="Natural language goal for computer use agent, required if command_type='computer_use'"
    )


class LearnAction(BaseModel):
    """A correction or fact to add to the knowledge base."""
    section: str = Field(description="Knowledge base section: 'pc', 'services', 'preferences', or 'corrections'")
    key: str = Field(description="Key within the section, e.g. 'browser', 'emby'")
    value: str | dict = Field(description="The fact to store")


class ClawdiaResponse(BaseModel):
    """Structured response from the Clawdia brain."""
    action: Literal["ir", "respond", "music", "pc", "learn"] = Field(
        description=(
            "'ir' to send an IR command, 'respond' to reply with text, "
            "'music' to control music, 'pc' to control the Linux PC, "
            "'learn' to store a correction or fact"
        )
    )
    ir: IRAction | None = Field(
        default=None, description="IR command details, required if action='ir'"
    )
    music: MusicAction | None = Field(
        default=None, description="Music command details, required if action='music'"
    )
    pc: PCAction | None = Field(
        default=None, description="PC command details, required if action='pc'"
    )
    learn: LearnAction | None = Field(
        default=None, description="Learning details, required if action='learn'"
    )
    message: str = Field(
        description="Human-readable message describing what was done or the answer"
    )

    @model_validator(mode="after")
    def validate_action_fields(self) -> ClawdiaResponse:
        if self.action == "ir" and self.ir is None:
            raise ValueError("'ir' field is required when action is 'ir'")
        if self.action == "music" and self.music is None:
            raise ValueError("'music' field is required when action is 'music'")
        if self.action == "pc" and self.pc is None:
            raise ValueError("'pc' field is required when action is 'pc'")
        if self.action == "learn" and self.learn is None:
            raise ValueError("'learn' field is required when action is 'learn'")
        return self
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/vossi/local_dev/clawdia && python -m pytest tests/test_pc_models.py tests/test_brain_models.py tests/test_music_models.py -v`
Expected: ALL PASS (new tests pass, existing model tests still pass)

- [ ] **Step 5: Commit**

```bash
git add src/clawdia/brain/models.py tests/test_pc_models.py
git commit -m "feat(pc): add PCAction and LearnAction brain models"
```

---

### Task 4: SSH Executor

**Files:**
- Create: `src/clawdia/pc/controller.py`
- Modify: `src/clawdia/pc/__init__.py`
- Test: `tests/test_pc_controller.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_pc_controller.py`:

```python
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from clawdia.pc.controller import PCController


@pytest.fixture
def controller():
    return PCController(
        ssh_host="192.168.1.100",
        ssh_user="vossi",
        ssh_key_path="~/.ssh/id_ed25519",
        agent_path="~/clawdia-agent",
    )


def test_build_ssh_command(controller):
    cmd = controller._build_ssh_cmd("echo hello")
    assert "ssh" in cmd
    assert "-i" in cmd
    assert "~/.ssh/id_ed25519" in cmd
    assert "vossi@192.168.1.100" in cmd
    assert "echo hello" in cmd


def test_build_ssh_command_includes_display(controller):
    cmd = controller._build_ssh_cmd("firefox http://emby:8096")
    joined = " ".join(cmd)
    assert "DISPLAY=:0" in joined


async def test_run_shell_command(controller):
    mock_process = AsyncMock()
    mock_process.communicate.return_value = (b"ok\n", b"")
    mock_process.returncode = 0

    with patch("asyncio.create_subprocess_exec", return_value=mock_process) as mock_exec:
        result = await controller.run_shell("echo hello")

    assert result.success is True
    assert result.output == "ok"
    mock_exec.assert_called_once()


async def test_run_shell_command_failure(controller):
    mock_process = AsyncMock()
    mock_process.communicate.return_value = (b"", b"error\n")
    mock_process.returncode = 1

    with patch("asyncio.create_subprocess_exec", return_value=mock_process):
        result = await controller.run_shell("bad command")

    assert result.success is False
    assert "error" in result.output


async def test_run_computer_use(controller):
    mock_process = AsyncMock()
    mock_process.communicate.return_value = (b'{"success": true, "summary": "done"}\n', b"")
    mock_process.returncode = 0

    with patch("asyncio.create_subprocess_exec", return_value=mock_process) as mock_exec:
        result = await controller.run_computer_use("navigate to TV shows", "browser: firefox")

    assert result.success is True
    assert result.output == "done"
    call_args = mock_exec.call_args[0]
    joined = " ".join(call_args)
    assert "pc_agent" in joined
    assert "navigate to TV shows" in joined
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/vossi/local_dev/clawdia && python -m pytest tests/test_pc_controller.py -v`
Expected: FAIL — `ImportError: cannot import name 'PCController'`

- [ ] **Step 3: Write implementation**

Create `src/clawdia/pc/controller.py`:

```python
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class PCResult:
    success: bool
    output: str


class PCController:
    """Executes commands on a remote Linux PC via SSH."""

    def __init__(
        self,
        ssh_host: str,
        ssh_user: str,
        ssh_key_path: str = "~/.ssh/id_ed25519",
        agent_path: str = "~/clawdia-agent",
    ):
        self.ssh_host = ssh_host
        self.ssh_user = ssh_user
        self.ssh_key_path = ssh_key_path
        self.agent_path = agent_path

    def _build_ssh_cmd(self, remote_cmd: str) -> list[str]:
        return [
            "ssh",
            "-i", self.ssh_key_path,
            "-o", "StrictHostKeyChecking=no",
            "-o", "ConnectTimeout=5",
            f"{self.ssh_user}@{self.ssh_host}",
            f"DISPLAY=:0 {remote_cmd}",
        ]

    async def _run_ssh(self, remote_cmd: str, timeout: float = 30.0) -> PCResult:
        cmd = self._build_ssh_cmd(remote_cmd)
        logger.info("SSH command: %s", " ".join(cmd))

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=timeout
            )
        except asyncio.TimeoutError:
            logger.error("SSH command timed out after %.0fs", timeout)
            return PCResult(success=False, output="Command timed out")
        except Exception as e:
            logger.exception("SSH command failed")
            return PCResult(success=False, output=str(e))

        if process.returncode == 0:
            return PCResult(success=True, output=stdout.decode().strip())
        else:
            error = stderr.decode().strip() or stdout.decode().strip()
            return PCResult(success=False, output=error)

    async def run_shell(self, command: str) -> PCResult:
        """Run a shell command on the remote PC."""
        return await self._run_ssh(command)

    async def run_computer_use(self, goal: str, knowledge_context: str) -> PCResult:
        """Invoke the PC agent for GUI interaction via computer use."""
        escaped_goal = goal.replace("'", "'\\''")
        escaped_ctx = knowledge_context.replace("'", "'\\''")
        remote_cmd = (
            f"cd {self.agent_path} && "
            f"python -m pc_agent --goal '{escaped_goal}' --context '{escaped_ctx}'"
        )
        result = await self._run_ssh(remote_cmd, timeout=300.0)

        if result.success:
            try:
                data = json.loads(result.output)
                return PCResult(success=data.get("success", False), output=data.get("summary", result.output))
            except json.JSONDecodeError:
                return result
        return result
```

- [ ] **Step 4: Update package init**

Update `src/clawdia/pc/__init__.py`:

```python
from clawdia.pc.controller import PCController
from clawdia.pc.knowledge import KnowledgeBase

__all__ = ["PCController", "KnowledgeBase"]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /home/vossi/local_dev/clawdia && python -m pytest tests/test_pc_controller.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/clawdia/pc/ tests/test_pc_controller.py
git commit -m "feat(pc): add SSH-based PC controller"
```

---

### Task 5: Brain System Prompt Update

**Files:**
- Modify: `src/clawdia/brain/agent.py:1-85`
- Test: `tests/test_brain_agent.py`

- [ ] **Step 1: Read existing test file**

Read `tests/test_brain_agent.py` to understand existing test patterns.

- [ ] **Step 2: Write the failing tests**

Add to `tests/test_brain_agent.py`:

```python
from clawdia.brain.agent import build_system_prompt


def test_system_prompt_includes_pc_section_when_enabled():
    ir = MagicMock()
    ir.list_commands_with_descriptions.return_value = []
    prompt = build_system_prompt(ir=ir, pc_knowledge="browser: firefox\nservices:\n  emby:\n    url: http://emby:8096")
    assert "PC Remote Control" in prompt
    assert "firefox" in prompt
    assert "emby" in prompt


def test_system_prompt_pc_disabled_when_no_knowledge():
    ir = MagicMock()
    ir.list_commands_with_descriptions.return_value = []
    prompt = build_system_prompt(ir=ir, pc_knowledge="")
    assert "PC remote control is not configured" in prompt or "PC Remote Control" not in prompt


def test_system_prompt_includes_learn_action():
    ir = MagicMock()
    ir.list_commands_with_descriptions.return_value = []
    prompt = build_system_prompt(ir=ir, pc_knowledge="browser: firefox")
    assert "learn" in prompt
    assert "correction" in prompt.lower()
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd /home/vossi/local_dev/clawdia && python -m pytest tests/test_brain_agent.py::test_system_prompt_includes_pc_section_when_enabled -v`
Expected: FAIL — `build_system_prompt() got an unexpected keyword argument 'pc_knowledge'`

- [ ] **Step 4: Write implementation**

Update `src/clawdia/brain/agent.py`. Add the PC section to `SYSTEM_PROMPT` and update `build_system_prompt`:

```python
from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic_ai import Agent

from clawdia.brain.models import ClawdiaResponse

if TYPE_CHECKING:
    from clawdia.ir import IRController
    from clawdia.music import MusicController

SYSTEM_PROMPT = """\
You are Clawdia, a voice-controlled home assistant running on a Raspberry Pi.

You can control devices via infrared commands, control music playback, control a Linux PC remotely, and answer general questions.

## Available IR Commands

{ir_commands}

## Music Playback

{music_section}

## PC Remote Control

{pc_section}

## Rules

1. If the user wants to control a device (TV, etc.), respond with action="ir" and the exact command name.
2. If the user wants to play music, search for songs, control playback (pause, skip, volume, etc.), or manage playlists, respond with action="music" with the appropriate command.
3. If the user wants to control the Linux PC (open apps, browse websites, interact with desktop, run commands), respond with action="pc".
   - Use command_type="shell" for simple commands (opening URLs, launching apps, adjusting volume, terminal commands).
   - Use command_type="computer_use" when the task requires seeing and interacting with the screen (clicking through menus, navigating web apps, filling forms).
4. If the user is correcting or providing feedback about a previous action (e.g. "wrong URL", "not that browser"), respond with action="learn" to store the correction.
5. If the user asks a question or wants information, respond with action="respond" and your answer.
6. Always include a brief, friendly message describing what you did or your answer.
7. If you're unsure what the user wants, respond with action="respond" and ask for clarification.

### Music Commands Reference

- play: Resume playback
- pause: Pause playback
- skip: Skip to next track
- previous: Go to previous track
- volume: Set volume (include volume field, 0-100)
- play_query: Search and play a track (include query field)
- play_playlist: Find and play a playlist by name (include query field)
- queue: Add a track to the queue (include query field)
- search: Search for tracks (include query field)
- now_playing: Show what's currently playing
- list_playlists: List available playlists

### Learn Action

When the user corrects a previous action, extract the fact and store it:
- section: which part of the knowledge base to update ("pc", "services", "preferences", "corrections")
- key: the specific item (e.g. "browser", "emby")
- value: the corrected information (string or dict)
"""

MUSIC_ENABLED = "Music playback is available via Spotify. Use action=\"music\" for any music-related requests."
MUSIC_DISABLED = "Music playback is not currently configured."

PC_ENABLED = """\
PC remote control is available. Use action="pc" for any PC-related requests.

### Known facts about the PC:

{pc_knowledge}"""

PC_DISABLED = "PC remote control is not configured."


def build_system_prompt(
    ir: IRController,
    music: MusicController | None = None,
    pc_knowledge: str = "",
) -> str:
    commands = ir.list_commands_with_descriptions()
    if commands:
        lines = [f"- {name}: {desc}" if desc else f"- {name}" for name, desc in commands]
        ir_commands = "\n".join(lines)
    else:
        ir_commands = "No IR commands recorded yet."

    music_section = MUSIC_ENABLED if music else MUSIC_DISABLED

    if pc_knowledge:
        pc_section = PC_ENABLED.format(pc_knowledge=pc_knowledge)
    else:
        pc_section = PC_DISABLED

    return SYSTEM_PROMPT.format(
        ir_commands=ir_commands,
        music_section=music_section,
        pc_section=pc_section,
    )


def create_agent(
    model: str = "openrouter:anthropic/claude-haiku-4.5",
    ir: IRController | None = None,
    music: MusicController | None = None,
    pc_knowledge: str = "",
) -> Agent:
    """Create the Clawdia PydanticAI agent."""
    if ir:
        prompt = build_system_prompt(ir=ir, music=music, pc_knowledge=pc_knowledge)
    else:
        prompt = SYSTEM_PROMPT.format(
            ir_commands="No IR commands recorded yet.",
            music_section=MUSIC_ENABLED if music else MUSIC_DISABLED,
            pc_section=PC_ENABLED.format(pc_knowledge=pc_knowledge) if pc_knowledge else PC_DISABLED,
        )
    return Agent(
        model,
        output_type=ClawdiaResponse,
        instructions=prompt,
    )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /home/vossi/local_dev/clawdia && python -m pytest tests/test_brain_agent.py -v`
Expected: PASS

- [ ] **Step 6: Update Brain class to accept pc_knowledge**

In `src/clawdia/brain/__init__.py`, update the `Brain` class:

```python
from __future__ import annotations

from typing import TYPE_CHECKING

from clawdia.brain.agent import create_agent
from clawdia.brain.models import ClawdiaResponse

if TYPE_CHECKING:
    from clawdia.ir import IRController
    from clawdia.music import MusicController


class Brain:
    """High-level interface to the Clawdia intent engine."""

    def __init__(
        self,
        model: str = "openrouter:anthropic/claude-haiku-4.5",
        ir: IRController | None = None,
        music: MusicController | None = None,
        pc_knowledge: str = "",
    ):
        self._model = model
        self._ir = ir
        self._music = music
        self._pc_knowledge = pc_knowledge
        self.agent = create_agent(model=model, ir=ir, music=music, pc_knowledge=pc_knowledge)

    def reload_commands(self, pc_knowledge: str | None = None) -> None:
        """Rebuild the agent with current IR commands and knowledge."""
        if pc_knowledge is not None:
            self._pc_knowledge = pc_knowledge
        self.agent = create_agent(
            model=self._model, ir=self._ir, music=self._music,
            pc_knowledge=self._pc_knowledge,
        )

    async def process(self, text: str) -> ClawdiaResponse:
        """Process a text command and return a structured response."""
        result = await self.agent.run(text)
        return result.output
```

- [ ] **Step 7: Run all brain tests**

Run: `cd /home/vossi/local_dev/clawdia && python -m pytest tests/test_brain.py tests/test_brain_agent.py tests/test_brain_models.py -v`
Expected: ALL PASS

- [ ] **Step 8: Commit**

```bash
git add src/clawdia/brain/
git commit -m "feat(pc): add PC remote control to brain system prompt"
```

---

### Task 6: Orchestrator PC & Learn Routing

**Files:**
- Modify: `src/clawdia/orchestrator.py:1-114`
- Test: `tests/test_pc_orchestrator.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_pc_orchestrator.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from clawdia.brain.models import ClawdiaResponse, PCAction, LearnAction
from clawdia.orchestrator import Orchestrator
from clawdia.pc.controller import PCResult


@pytest.fixture
def mock_brain():
    return AsyncMock()


@pytest.fixture
def mock_ir():
    ir = MagicMock()
    ir.has_command.return_value = True
    ir.send = AsyncMock(return_value=True)
    return ir


@pytest.fixture
def mock_telegram():
    return AsyncMock()


@pytest.fixture
def mock_pc():
    pc = AsyncMock()
    pc.run_shell = AsyncMock(return_value=PCResult(success=True, output="ok"))
    pc.run_computer_use = AsyncMock(return_value=PCResult(success=True, output="done"))
    return pc


@pytest.fixture
def mock_knowledge():
    kb = MagicMock()
    kb.to_prompt_context.return_value = "browser: firefox"
    return kb


@pytest.fixture
def orchestrator(mock_brain, mock_ir, mock_telegram, mock_pc, mock_knowledge):
    return Orchestrator(
        brain=mock_brain, ir=mock_ir, telegram=mock_telegram,
        pc=mock_pc, knowledge=mock_knowledge,
    )


async def test_handle_pc_shell_command(orchestrator, mock_brain, mock_pc, mock_telegram):
    response = ClawdiaResponse(
        action="pc",
        pc=PCAction(command_type="shell", shell_command="firefox http://emby:8096"),
        message="Opening Emby in Firefox",
    )
    mock_brain.process.return_value = response

    await orchestrator.handle_text_command("open emby")

    mock_pc.run_shell.assert_called_once_with("firefox http://emby:8096")
    mock_telegram.notify.assert_called_once_with("Opening Emby in Firefox")


async def test_handle_pc_shell_failure(orchestrator, mock_brain, mock_pc, mock_telegram):
    response = ClawdiaResponse(
        action="pc",
        pc=PCAction(command_type="shell", shell_command="badcmd"),
        message="Running command",
    )
    mock_brain.process.return_value = response
    mock_pc.run_shell.return_value = PCResult(success=False, output="command not found")

    await orchestrator.handle_text_command("run bad thing")

    mock_telegram.notify.assert_called_once()
    assert "failed" in mock_telegram.notify.call_args[0][0].lower()


async def test_handle_pc_computer_use(orchestrator, mock_brain, mock_pc, mock_telegram, mock_knowledge):
    response = ClawdiaResponse(
        action="pc",
        pc=PCAction(command_type="computer_use", goal="play Stranger Things"),
        message="Navigating Emby",
    )
    mock_brain.process.return_value = response

    await orchestrator.handle_text_command("play stranger things on emby")

    mock_pc.run_computer_use.assert_called_once_with("play Stranger Things", "browser: firefox")
    mock_telegram.notify.assert_called()


async def test_handle_learn_action(orchestrator, mock_brain, mock_telegram, mock_knowledge):
    response = ClawdiaResponse(
        action="learn",
        learn=LearnAction(section="services", key="emby", value={"url": "http://192.168.1.50:8096"}),
        message="Got it, I'll remember that Emby is at 192.168.1.50:8096",
    )
    mock_brain.process.return_value = response

    await orchestrator.handle_text_command("emby is at 192.168.1.50:8096")

    mock_knowledge.update.assert_called_once_with("services", "emby", {"url": "http://192.168.1.50:8096"})
    mock_brain.reload_commands.assert_called_once()
    mock_telegram.notify.assert_called_once_with("Got it, I'll remember that Emby is at 192.168.1.50:8096")


async def test_handle_pc_without_controller(mock_brain, mock_ir, mock_telegram):
    orchestrator = Orchestrator(brain=mock_brain, ir=mock_ir, telegram=mock_telegram)
    response = ClawdiaResponse(
        action="pc",
        pc=PCAction(command_type="shell", shell_command="echo hi"),
        message="hi",
    )
    mock_brain.process.return_value = response

    await orchestrator.handle_text_command("say hi on pc")

    mock_telegram.notify.assert_called_once()
    assert "not configured" in mock_telegram.notify.call_args[0][0].lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/vossi/local_dev/clawdia && python -m pytest tests/test_pc_orchestrator.py -v`
Expected: FAIL — `Orchestrator.__init__() got an unexpected keyword argument 'pc'`

- [ ] **Step 3: Write implementation**

Update `src/clawdia/orchestrator.py`:

```python
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from clawdia.brain import Brain
    from clawdia.brain.models import MusicAction
    from clawdia.ir import IRController
    from clawdia.music import MusicController
    from clawdia.pc.controller import PCController
    from clawdia.pc.knowledge import KnowledgeBase
    from clawdia.telegram_bot import ClawdiaTelegramBot
    from clawdia.voice.stt import SpeechToText

logger = logging.getLogger(__name__)

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

    Connects: voice -> STT -> brain -> action routing (IR / Music / PC / Telegram).
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
    ):
        self.brain = brain
        self.ir = ir
        self.telegram = telegram
        self.stt = stt
        self.music = music
        self.pc = pc
        self.knowledge = knowledge

    async def _handle_music(self, action: MusicAction) -> str:
        """Dispatch a music action to the controller."""
        if not self.music:
            return "Music playback is not configured."
        handler = MUSIC_DISPATCH.get(action.command)
        if not handler:
            return f"Unknown music command: {action.command}"
        result = await handler(self.music, action)
        if isinstance(result, list):
            if not result:
                return "No results found."
            lines = [f"• {r['name']} — {r.get('artists', '')}" if 'artists' in r else f"• {r['name']}" for r in result]
            return "\n".join(lines)
        return result

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

        elif response.action == "music" and response.music:
            result = await self._handle_music(response.music)
            await self.telegram.notify(result)

        elif response.action == "pc" and response.pc:
            if not self.pc:
                await self.telegram.notify("PC remote control is not configured.")
                return

            if response.pc.command_type == "shell" and response.pc.shell_command:
                result = await self.pc.run_shell(response.pc.shell_command)
            elif response.pc.command_type == "computer_use" and response.pc.goal:
                knowledge_ctx = self.knowledge.to_prompt_context() if self.knowledge else ""
                result = await self.pc.run_computer_use(response.pc.goal, knowledge_ctx)
            else:
                await self.telegram.notify("Invalid PC command.")
                return

            if result.success:
                await self.telegram.notify(response.message)
            else:
                await self.telegram.notify(f"PC command failed: {result.output}")

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
            await self.telegram.notify(response.message)

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

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/vossi/local_dev/clawdia && python -m pytest tests/test_pc_orchestrator.py tests/test_orchestrator.py tests/test_music_orchestrator.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/clawdia/orchestrator.py tests/test_pc_orchestrator.py
git commit -m "feat(pc): add PC and learn action routing to orchestrator"
```

---

### Task 7: PC Agent — Action Executors

**Files:**
- Create: `src/clawdia/pc_agent/__init__.py`
- Create: `src/clawdia/pc_agent/actions.py`
- Test: `tests/test_pc_agent_actions.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_pc_agent_actions.py`:

```python
import pytest
from unittest.mock import AsyncMock, patch

from clawdia.pc_agent.actions import (
    take_screenshot,
    click,
    type_text,
    press_key,
    ActionResult,
)


async def test_take_screenshot():
    mock_process = AsyncMock()
    mock_process.communicate.return_value = (b"", b"")
    mock_process.returncode = 0

    with patch("asyncio.create_subprocess_exec", return_value=mock_process):
        with patch("pathlib.Path.read_bytes", return_value=b"fake-png-data"):
            result = await take_screenshot()

    assert result.success is True
    assert result.data == b"fake-png-data"


async def test_click():
    mock_process = AsyncMock()
    mock_process.communicate.return_value = (b"", b"")
    mock_process.returncode = 0

    with patch("asyncio.create_subprocess_exec", return_value=mock_process) as mock_exec:
        result = await click(100, 200)

    assert result.success is True
    calls = mock_exec.call_args_list
    # Should have two calls: mousemove and click
    all_args = " ".join(str(c) for c in calls)
    assert "mousemove" in all_args
    assert "100" in all_args
    assert "200" in all_args


async def test_type_text():
    mock_process = AsyncMock()
    mock_process.communicate.return_value = (b"", b"")
    mock_process.returncode = 0

    with patch("asyncio.create_subprocess_exec", return_value=mock_process) as mock_exec:
        result = await type_text("hello world")

    assert result.success is True
    all_args = " ".join(str(c) for c in mock_exec.call_args_list)
    assert "hello world" in all_args


async def test_press_key():
    mock_process = AsyncMock()
    mock_process.communicate.return_value = (b"", b"")
    mock_process.returncode = 0

    with patch("asyncio.create_subprocess_exec", return_value=mock_process) as mock_exec:
        result = await press_key("ctrl+t")

    assert result.success is True
    all_args = " ".join(str(c) for c in mock_exec.call_args_list)
    assert "ctrl+t" in all_args


async def test_take_screenshot_failure():
    mock_process = AsyncMock()
    mock_process.communicate.return_value = (b"", b"scrot: error")
    mock_process.returncode = 1

    with patch("asyncio.create_subprocess_exec", return_value=mock_process):
        result = await take_screenshot()

    assert result.success is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/vossi/local_dev/clawdia && python -m pytest tests/test_pc_agent_actions.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'clawdia.pc_agent'`

- [ ] **Step 3: Create package init**

Create `src/clawdia/pc_agent/__init__.py`:

```python
```

- [ ] **Step 4: Write implementation**

Create `src/clawdia/pc_agent/actions.py`:

```python
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

SCREENSHOT_PATH = Path("/tmp/clawdia_screenshot.png")


@dataclass
class ActionResult:
    success: bool
    data: bytes | None = None
    error: str = ""


async def _run(cmd: list[str]) -> ActionResult:
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
    except Exception as e:
        return ActionResult(success=False, error=str(e))

    if process.returncode != 0:
        return ActionResult(success=False, error=stderr.decode().strip())
    return ActionResult(success=True)


async def take_screenshot() -> ActionResult:
    """Capture full screen screenshot using scrot."""
    result = await _run(["scrot", "-o", str(SCREENSHOT_PATH)])
    if not result.success:
        return result
    try:
        data = SCREENSHOT_PATH.read_bytes()
        return ActionResult(success=True, data=data)
    except Exception as e:
        return ActionResult(success=False, error=str(e))


async def click(x: int, y: int) -> ActionResult:
    """Move mouse to (x, y) and click."""
    result = await _run(["xdotool", "mousemove", str(x), str(y)])
    if not result.success:
        return result
    return await _run(["xdotool", "click", "1"])


async def type_text(text: str) -> ActionResult:
    """Type text using xdotool."""
    return await _run(["xdotool", "type", "--delay", "50", text])


async def press_key(combo: str) -> ActionResult:
    """Press a key combination using xdotool."""
    return await _run(["xdotool", "key", combo])
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /home/vossi/local_dev/clawdia && python -m pytest tests/test_pc_agent_actions.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/clawdia/pc_agent/ tests/test_pc_agent_actions.py
git commit -m "feat(pc-agent): add xdotool/scrot action executors"
```

---

### Task 8: PC Agent — Computer Use Loop

**Files:**
- Create: `src/clawdia/pc_agent/agent.py`
- Create: `src/clawdia/pc_agent/__main__.py`
- Test: `tests/test_pc_agent.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_pc_agent.py`:

```python
import pytest
import base64
from unittest.mock import AsyncMock, patch, MagicMock

from clawdia.pc_agent.agent import ComputerUseAgent, AgentResult


@pytest.fixture
def agent():
    return ComputerUseAgent(
        api_key="test-key",
        model="claude-sonnet-4-6-20250514",
        max_iterations=5,
    )


def test_agent_init(agent):
    assert agent.max_iterations == 5
    assert agent.model == "claude-sonnet-4-6-20250514"


async def test_agent_done_on_first_iteration(agent):
    fake_screenshot = b"fake-png"
    mock_response = MagicMock()
    mock_response.content = [
        MagicMock(type="text", text="Goal achieved — Emby is playing."),
    ]
    mock_response.stop_reason = "end_turn"

    with patch.object(agent, "_take_screenshot", return_value=fake_screenshot):
        with patch.object(agent, "_call_api", return_value=mock_response):
            result = await agent.run("open emby", knowledge_context="")

    assert result.success is True
    assert "Emby" in result.summary


async def test_agent_max_iterations(agent):
    fake_screenshot = b"fake-png"
    mock_tool_use = MagicMock()
    mock_tool_use.type = "tool_use"
    mock_tool_use.name = "computer"
    mock_tool_use.id = "tool_1"
    mock_tool_use.input = {"action": "screenshot"}

    mock_response = MagicMock()
    mock_response.content = [mock_tool_use]
    mock_response.stop_reason = "tool_use"

    with patch.object(agent, "_take_screenshot", return_value=fake_screenshot):
        with patch.object(agent, "_call_api", return_value=mock_response):
            with patch.object(agent, "_execute_tool", return_value=fake_screenshot):
                result = await agent.run("impossible goal", knowledge_context="")

    assert result.success is False
    assert "max iterations" in result.summary.lower()


def test_agent_result_to_json():
    result = AgentResult(success=True, summary="Done")
    data = result.to_json()
    assert '"success": true' in data
    assert '"summary": "Done"' in data
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/vossi/local_dev/clawdia && python -m pytest tests/test_pc_agent.py -v`
Expected: FAIL — `ImportError: cannot import name 'ComputerUseAgent'`

- [ ] **Step 3: Write implementation**

Create `src/clawdia/pc_agent/agent.py`:

```python
from __future__ import annotations

import base64
import json
import logging
from dataclasses import dataclass

import anthropic

from clawdia.pc_agent.actions import take_screenshot, click, type_text, press_key

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 30


@dataclass
class AgentResult:
    success: bool
    summary: str

    def to_json(self) -> str:
        return json.dumps({"success": self.success, "summary": self.summary})


class ComputerUseAgent:
    """Runs the computer use loop: screenshot -> Claude -> action -> repeat."""

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-6-20250514",
        max_iterations: int = MAX_ITERATIONS,
    ):
        self.client = anthropic.AsyncAnthropic(api_key=api_key)
        self.model = model
        self.max_iterations = max_iterations

    async def _take_screenshot(self) -> bytes:
        result = await take_screenshot()
        if not result.success:
            raise RuntimeError(f"Screenshot failed: {result.error}")
        return result.data

    async def _call_api(self, messages: list, system: str) -> anthropic.types.Message:
        return await self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=system,
            messages=messages,
            tools=[
                {
                    "type": "computer_20250124",
                    "name": "computer",
                    "display_width_px": 1920,
                    "display_height_px": 1080,
                    "display_number": 0,
                },
            ],
            betas=["computer-use-2025-01-24"],
        )

    async def _execute_tool(self, tool_input: dict) -> bytes | str:
        action = tool_input.get("action")
        if action == "screenshot":
            return await self._take_screenshot()
        elif action == "left_click":
            coords = tool_input.get("coordinate", [0, 0])
            await click(coords[0], coords[1])
            return await self._take_screenshot()
        elif action == "type":
            await type_text(tool_input.get("text", ""))
            return await self._take_screenshot()
        elif action == "key":
            await press_key(tool_input.get("text", ""))
            return await self._take_screenshot()
        else:
            logger.warning("Unknown action: %s", action)
            return await self._take_screenshot()

    async def run(self, goal: str, knowledge_context: str) -> AgentResult:
        """Execute the computer use loop until the goal is achieved or max iterations reached."""
        system = f"You are controlling a Linux desktop to accomplish a goal.\n\nGoal: {goal}"
        if knowledge_context:
            system += f"\n\nKnown facts about this PC:\n{knowledge_context}"

        screenshot_data = await self._take_screenshot()
        screenshot_b64 = base64.standard_b64encode(screenshot_data).decode()

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": f"Please accomplish this goal: {goal}"},
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": screenshot_b64,
                        },
                    },
                ],
            },
        ]

        for iteration in range(self.max_iterations):
            logger.info("Computer use iteration %d/%d", iteration + 1, self.max_iterations)

            response = await self._call_api(messages, system)

            # Check if Claude wants to use a tool
            tool_uses = [b for b in response.content if b.type == "tool_use"]
            text_blocks = [b for b in response.content if b.type == "text"]

            if not tool_uses:
                # No tool use — Claude is done or giving a text response
                summary = text_blocks[0].text if text_blocks else "Goal completed."
                return AgentResult(success=True, summary=summary)

            # Process each tool use
            messages.append({"role": "assistant", "content": response.content})

            tool_results = []
            for tool_use in tool_uses:
                result_data = await self._execute_tool(tool_use.input)

                if isinstance(result_data, bytes):
                    result_b64 = base64.standard_b64encode(result_data).decode()
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_use.id,
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/png",
                                    "data": result_b64,
                                },
                            },
                        ],
                    })
                else:
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_use.id,
                        "content": str(result_data),
                    })

            messages.append({"role": "user", "content": tool_results})

        return AgentResult(success=False, summary="Reached max iterations without completing the goal.")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/vossi/local_dev/clawdia && python -m pytest tests/test_pc_agent.py -v`
Expected: PASS

- [ ] **Step 5: Create CLI entry point**

Create `src/clawdia/pc_agent/__main__.py`:

```python
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys

from clawdia.pc_agent.agent import ComputerUseAgent


def main():
    parser = argparse.ArgumentParser(description="Clawdia PC Agent — Computer Use")
    parser.add_argument("--goal", required=True, help="The goal to accomplish")
    parser.add_argument("--context", default="", help="Knowledge base context")
    parser.add_argument("--api-key", default=os.environ.get("ANTHROPIC_API_KEY", ""), help="Anthropic API key")
    parser.add_argument("--model", default="claude-sonnet-4-6-20250514", help="Model to use")
    parser.add_argument("--max-iterations", type=int, default=30, help="Max iterations")
    args = parser.parse_args()

    if not args.api_key:
        print('{"success": false, "summary": "ANTHROPIC_API_KEY not set"}')
        sys.exit(1)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s", stream=sys.stderr)

    agent = ComputerUseAgent(
        api_key=args.api_key,
        model=args.model,
        max_iterations=args.max_iterations,
    )

    result = asyncio.run(agent.run(args.goal, args.context))
    print(result.to_json())
    sys.exit(0 if result.success else 1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Add anthropic dependency to pyproject.toml**

In `pyproject.toml`, add `"anthropic>=0.40"` to the `dependencies` list.

- [ ] **Step 7: Run all PC agent tests**

Run: `cd /home/vossi/local_dev/clawdia && python -m pytest tests/test_pc_agent.py tests/test_pc_agent_actions.py -v`
Expected: ALL PASS

- [ ] **Step 8: Commit**

```bash
git add src/clawdia/pc_agent/ tests/test_pc_agent.py pyproject.toml
git commit -m "feat(pc-agent): add computer use loop with Claude vision"
```

---

### Task 9: Integration — main.py + Telegram

**Files:**
- Modify: `src/clawdia/main.py:1-136`
- Modify: `src/clawdia/telegram_bot/bot.py` (add `/pc` command)
- Test: `tests/test_telegram.py` (verify existing tests still pass)

- [ ] **Step 1: Update main.py**

Add PC controller and knowledge base initialization to `src/clawdia/main.py`. Insert after the music initialization block and before the brain initialization:

```python
    # Optional: PC Remote Control (needs SSH config)
    pc = None
    knowledge = None
    pc_knowledge = ""
    if settings.pc_enabled:
        from clawdia.pc import PCController, KnowledgeBase
        pc = PCController(
            ssh_host=settings.pc_ssh_host,
            ssh_user=settings.pc_ssh_user,
            ssh_key_path=settings.pc_ssh_key_path,
            agent_path=settings.pc_agent_path,
        )
        knowledge = KnowledgeBase("pc_knowledge.yaml")
        pc_knowledge = knowledge.to_prompt_context()
        logger.info("PC remote control enabled (host: %s)", settings.pc_ssh_host)
    else:
        logger.info("PC remote control not configured (missing SSH host/user)")
```

Update the brain initialization to pass `pc_knowledge`:

```python
    brain = Brain(model=f"openrouter:{settings.openrouter_model}", ir=ir, music=music, pc_knowledge=pc_knowledge)
```

Update the orchestrator initialization to pass `pc` and `knowledge`:

```python
    orchestrator = Orchestrator(
        brain=brain,
        ir=ir,
        telegram=telegram,
        stt=stt,
        music=music,
        pc=pc,
        knowledge=knowledge,
    )
```

- [ ] **Step 2: Add /pc command to Telegram bot**

In `src/clawdia/telegram_bot/bot.py`, add a handler in `_build_app` after the existing command handlers:

```python
        app.add_handler(CommandHandler("pc", self._handle_pc_status))
```

Add the handler method to the `ClawdiaTelegramBot` class:

```python
    async def _handle_pc_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /pc command - show PC remote control status."""
        # The bot doesn't need to know PC details — just tell the user to send natural language
        await update.message.reply_text(
            "PC Remote Control\n\n"
            "Just send me a message describing what you want to do on your PC.\n"
            "Examples:\n"
            "• 'Open Emby and play Stranger Things'\n"
            "• 'Set the volume to 50%'\n"
            "• 'Open Firefox'\n"
            "• 'Take a screenshot'"
        )
```

Update the `/start` message to mention PC control:

```python
        await update.message.reply_text(
            "Hi! I'm Clawdia, your home assistant.\n\n"
            "Send me a message and I'll process it.\n"
            "Use /ir to see available IR commands.\n"
            "Use /play <query> to play music.\n"
            "Use /pc for PC remote control info."
        )
```

- [ ] **Step 3: Run all existing tests to verify nothing is broken**

Run: `cd /home/vossi/local_dev/clawdia && python -m pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 4: Commit**

```bash
git add src/clawdia/main.py src/clawdia/telegram_bot/bot.py
git commit -m "feat(pc): wire up PC controller and knowledge base in main + telegram"
```

---

### Task 10: End-to-End Smoke Test

**Files:**
- No new files — manual verification

- [ ] **Step 1: Run the full test suite**

Run: `cd /home/vossi/local_dev/clawdia && python -m pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 2: Run ruff linter**

Run: `cd /home/vossi/local_dev/clawdia && python -m ruff check src/ tests/`
Expected: No errors (fix any that appear)

- [ ] **Step 3: Verify import chain**

Run: `cd /home/vossi/local_dev/clawdia && python -c "from clawdia.pc import PCController, KnowledgeBase; from clawdia.pc_agent.agent import ComputerUseAgent; from clawdia.brain.models import PCAction, LearnAction; print('All imports OK')"`
Expected: `All imports OK`

- [ ] **Step 4: Final commit if any fixes were needed**

```bash
git add -A
git commit -m "chore: fix lint issues in PC remote control feature"
```
