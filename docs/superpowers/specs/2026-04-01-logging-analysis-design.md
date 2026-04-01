# Logging & Analysis Redesign

## Context

Clawdia's logging is currently stdlib `logging` to stdout only — no persistence, no file rotation. The SQLite interaction database (`clawdia_interactions.db`) lives inside the Docker container and is lost on recreation. Conversation history is in-memory only. There's no easy way to analyze logs or chat history on the Pi.

This redesign adds persistent, analyzable logging and chat storage outside the container, plus a Claude Code skill for remote analysis.

## 1. Loguru System Logging

**New module: `src/clawdia/log.py`**

- Configure loguru with two sinks:
  - **stdout**: colored output, format `{time} [{name}] {level}: {message}`
  - **file**: `/app/data/clawdia.log`, daily rotation, 7-day retention, plain text (no compression)
- Intercept stdlib `logging` so third-party libraries (httpx, telegram, spotipy) route through loguru
- HTTP library muting stays (set to WARNING level)

**Module changes:**
- Remove `logging.basicConfig()` from `main.py`
- Replace `import logging` / `logger = logging.getLogger(__name__)` with `from loguru import logger` across all modules
- `main.py` calls `log.setup()` at startup

**Dependency:** Add `loguru` to `pyproject.toml`

## 2. SQLite Persistence & Conversation History

**Move db to `/app/data/clawdia.db`** (mounted volume)

**Keep existing `interactions` table** unchanged:
```sql
CREATE TABLE IF NOT EXISTS interactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL DEFAULT (datetime('now')),
    source TEXT NOT NULL,
    context_id TEXT,
    user_input TEXT NOT NULL,
    action TEXT,
    action_detail TEXT,
    response_message TEXT,
    success INTEGER,
    duration_ms INTEGER,
    llm_duration_ms INTEGER
);
```

**Add `conversations` table:**
```sql
CREATE TABLE IF NOT EXISTS conversations (
    context_id TEXT PRIMARY KEY,
    messages TEXT NOT NULL,        -- JSON-serialized PydanticAI ModelMessage list
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```

**Brain changes:**
- On startup, `Brain` loads existing conversation history from db (per context_id)
- After each exchange, `Brain` upserts the trimmed history back to db
- The 3-exchange trim logic stays as-is — db stores the trimmed version
- `Brain` receives a reference to the database (InteractionLogger or similar) at init

## 3. Docker Volume Mount

**`docker-compose.yml`:**
```yaml
volumes:
  - ./data:/app/data    # Persistent logs and database
  # ... existing volumes unchanged
```

**Repo changes:**
- Create `data/.gitkeep`
- Add to `.gitignore`: `data/*.db`, `data/*.log`

## 4. Claude Code Analysis Skill

**New skill: `.claude/skills/clawdia-logs/`**

Lean skill that tells Claude Code:
- How to connect: `ssh clawdia`
- Where system logs are: `~/clawdia/data/clawdia.log` (+ rotated files `clawdia.log.YYYY-MM-DD`)
- Where the database is: `~/clawdia/data/clawdia.db`
- How to query it: `sqlite3 ~/clawdia/data/clawdia.db`
- What's in each table: schema descriptions for `interactions` and `conversations`

No canned queries — the skill provides context and lets the LLM figure out the right queries.

Created using the `superpowers:writing-skills` skill for proper format.

## 5. Files to Modify

| File | Change |
|------|--------|
| `src/clawdia/log.py` | **New** — loguru configuration module |
| `src/clawdia/main.py` | Remove logging.basicConfig, call log.setup(), update db path |
| `src/clawdia/logger_db.py` | Add conversations table, add save/load history methods, update db path |
| `src/clawdia/brain/__init__.py` | Load/save conversation history via db |
| `src/clawdia/orchestrator.py` | Replace stdlib logging with loguru |
| `src/clawdia/config.py` | Add data_dir setting (default `/app/data`) |
| `src/clawdia/health.py` | Replace stdlib logging with loguru |
| `src/clawdia/ir/controller.py` | Replace stdlib logging with loguru |
| `src/clawdia/music/controller.py` | Replace stdlib logging with loguru |
| `src/clawdia/pc/controller.py` | Replace stdlib logging with loguru |
| `src/clawdia/voice/listener.py` | Replace stdlib logging with loguru |
| `src/clawdia/voice/stt.py` | Replace stdlib logging with loguru |
| `src/clawdia/playback/coordinator.py` | Replace stdlib logging with loguru |
| `src/clawdia/telegram_bot/bot.py` | Replace stdlib logging with loguru |
| `docker-compose.yml` | Add `./data:/app/data` volume |
| `pyproject.toml` | Add `loguru` dependency |
| `.gitignore` | Add data/*.db, data/*.log |
| `data/.gitkeep` | **New** — keep empty data dir in repo |
| `.claude/skills/clawdia-logs/` | **New** — analysis skill |
| `tests/` | Update any tests that mock logging |

## 6. Verification

1. **Unit tests**: `pytest tests/ -q` — all tests pass (update mocks as needed)
2. **Local run**: Start app locally, verify logs appear in both stdout and `data/clawdia.log`
3. **DB persistence**: Send a command, restart app, verify interactions and conversation history survive
4. **Log rotation**: Check that loguru creates dated files and removes files older than 7 days
5. **Pi deploy**: `ssh clawdia "cd ~/clawdia && git pull && docker compose up -d --build"` — verify `data/` directory populates with .log and .db files
6. **Skill test**: Use the Claude Code skill to SSH in and read logs/query db
