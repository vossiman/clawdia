# PC Remote Control via Telegram

## Overview

Add the ability to remote control a Linux PC (Cinnamon/X11) via Telegram commands sent to Clawdia. The system uses Claude Computer Use for GUI interactions and direct shell commands for simple tasks, with a learning knowledge base that improves over time from user corrections.

## Architecture

```
User (Telegram) → Clawdia Brain (Pi) → SSH → PC Agent (Linux PC) → Computer Use Loop
```

### Components

1. **Brain extension (Pi)** — New `"pc"` action type alongside existing `"ir"` and `"respond"`. Classifies commands as simple shell tasks or GUI interactions requiring computer use.

2. **PC Agent (Linux PC)** — Standalone Python script invoked over SSH. Runs the computer use loop locally: screenshot → Claude vision → execute action → repeat.

3. **Knowledge base** — YAML file of learned facts about the user's setup, fed into system prompts. Grows via user corrections.

## Brain & Intent Routing

### New action type: `"pc"`

The brain's `ClawdiaResponse` model gets a new action variant:

- `action: "pc"` with fields:
  - `command_type`: `"shell"` or `"computer_use"`
  - `shell_command`: (optional) direct command for simple tasks, e.g. `firefox http://emby:8096`
  - `goal`: (optional) natural language goal for the computer use agent

### New action type: `"learn"`

For when the user's message is feedback/correction about the previous action rather than a new command. The brain extracts the fact and returns it as structured data. The orchestrator writes the update to the knowledge base YAML file on the Pi.

### Routing logic

- **`"shell"`** — task can be done with a single command (open URL, launch app, adjust volume, run terminal command)
- **`"computer_use"`** — task requires seeing and interacting with the screen (clicking through menus, filling forms, navigating within apps)

The brain's system prompt is enriched with the knowledge base so it can generate accurate shell commands and goals.

### Multi-step commands

For commands like "open Emby and play Stranger Things", the orchestrator calls the brain in a loop. The brain returns one action at a time. After each action completes, the orchestrator feeds the result back to the brain, which decides the next action (or responds with `"respond"` when done). Example sequence:

1. Brain returns `action: "pc", command_type: "shell", shell_command: "firefox http://emby:8096"` → orchestrator executes via SSH
2. Orchestrator reports success back to brain
3. Brain returns `action: "pc", command_type: "computer_use", goal: "navigate to TV Shows and play Stranger Things S01E01"` → orchestrator triggers PC agent via SSH
4. PC agent returns result → orchestrator reports to brain
5. Brain returns `action: "respond", message: "Playing Stranger Things S01E01 on Emby"` → done

## PC Agent & Computer Use Loop

### Invocation

Clawdia invokes the agent over SSH:

```
ssh pc "cd ~/clawdia-agent && python -m pc_agent --goal 'play Stranger Things on Emby'"
```

### The loop

1. **Screenshot** — `scrot /tmp/screenshot.png` (full screen capture)
2. **Send to Claude** — Screenshot image + goal + knowledge base + action history, using the Claude computer use tool type
3. **Receive action** — Claude returns a structured action:
   - `click(x, y)` → `xdotool mousemove x y click 1`
   - `type(text)` → `xdotool type "text"`
   - `key(combo)` → `xdotool key "ctrl+t"`
   - `screenshot()` → take another screenshot to reassess
   - `done(summary)` → goal achieved, exit loop
   - `fail(reason)` → can't accomplish goal, exit and report
4. **Execute** — Run the action on the X11 display (`DISPLAY=:0`)
5. **Repeat** — Back to step 1 until `done`, `fail`, or max iterations (safety cap: 30)

### Output

The agent returns a result (success/failure + summary) to stdout. Clawdia picks this up from the SSH session and relays it back to the user via Telegram.

### Dependencies on the PC

- Python 3.11+
- `scrot` — screenshot capture
- `xdotool` — mouse/keyboard simulation
- `anthropic` or `openai` SDK (for OpenRouter) — Claude API access

### Deployment

The agent is a small self-contained Python package within the Clawdia repo. Synced to the PC via git clone or scp. No always-on daemon — only runs when invoked via SSH.

## Knowledge Base & Learning

### Storage

A YAML file stored in the Clawdia repo on the Pi. Passed to the PC agent as a CLI argument or piped via stdin when invoked over SSH — no separate sync step needed.

### Structure

```yaml
pc:
  hostname: "192.168.1.100"
  username: "vossi"
  browser: "firefox"

services:
  emby:
    url: "http://192.168.1.50:8096"
    username: "vossi"
    notes: "use the TV Shows section for series"

preferences:
  - "always fullscreen the browser after opening"
  - "use keyboard shortcuts over clicking when possible"

corrections:
  - trigger: "open emby"
    learned: "emby is a local server, not emby.media"
    date: "2026-03-30"
```

### Correction flow

1. Clawdia executes a PC command
2. Reports result back via Telegram: "Done — opened Emby in Firefox"
3. User replies: "wrong URL, it's at 192.168.1.50:8096"
4. Brain detects this as a correction (`action: "learn"`)
5. Brain extracts the fact and updates the knowledge base YAML
6. Next time, the updated knowledge base is part of the system prompt

## SSH Setup & Security

### Connection

- Key-based SSH authentication (no passwords)
- Pi has a private key, PC has the corresponding public key in `authorized_keys`

### Environment

- `DISPLAY=:0` set for GUI commands
- `XAUTHORITY` passed if needed
- Standard X11 remote execution

### Configuration

New entries in Clawdia's `.env`:

```
PC_SSH_HOST=192.168.1.100
PC_SSH_USER=vossi
PC_SSH_KEY_PATH=~/.ssh/id_ed25519
PC_AGENT_PATH=~/clawdia-agent
```

### Security posture

- No extra daemon on the PC — agent only runs when invoked via SSH
- No open ports beyond existing SSH
- No confirmation step — commands execute immediately (user preference)
- LLM model: Claude Sonnet via OpenRouter (computer use capable), falls back to direct Anthropic API if needed

## API & Model

- **Primary:** OpenRouter with Claude Sonnet (supports computer use tool type via Anthropic compatibility layer)
- **Fallback:** Direct Anthropic API key if OpenRouter doesn't pass through computer use tools cleanly
- **Cost:** Minimal for personal use — only API calls when Telegram commands are sent, screenshots are the main token cost

## Scope boundaries

This feature covers:
- Telegram → PC command execution (shell and computer use)
- Knowledge base with correction-based learning
- SSH-based communication

This feature does NOT cover:
- Voice-triggered PC commands (future — uses same pipeline once voice is wired up)
- Multi-PC support (single target only)
- PC-to-Pi feedback (e.g., PC notifying Clawdia of events)
- Scheduled/automated PC tasks
