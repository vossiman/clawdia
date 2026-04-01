---
name: clawdia-logs
description: Use when analyzing Clawdia logs, debugging issues on the Pi, reading user interactions, checking error rates, or reviewing conversation history. Triggers on "check logs", "what happened", "errors", "interactions", "debug", "analyze usage".
---

# Clawdia Logs & Analysis

Read system logs and query the interaction database on the Clawdia Raspberry Pi.

## Connect

```bash
ssh clawdia
```

## System Logs (loguru)

Location: `~/clawdia/data/clawdia.log`
Rotated daily, 7-day retention. Older files: `clawdia.log.YYYY-MM-DD`

```bash
# Current log
cat ~/clawdia/data/clawdia.log

# All log files
ls -la ~/clawdia/data/clawdia.log*

# Search for errors
grep -i error ~/clawdia/data/clawdia.log
```

## Database (SQLite)

Location: `~/clawdia/data/clawdia.db`

```bash
sqlite3 ~/clawdia/data/clawdia.db
```

### interactions table

Logs every command processed through the orchestrator.

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Auto-increment PK |
| timestamp | TEXT | UTC datetime |
| source | TEXT | `telegram` or `voice` |
| context_id | TEXT | Chat ID or `default` |
| user_input | TEXT | What the user said |
| action | TEXT | `ir`, `music`, `pc`, `respond`, `learn` |
| action_detail | TEXT | JSON with action parameters |
| response_message | TEXT | What Clawdia replied |
| success | INTEGER | 1 = success, 0 = failure |
| duration_ms | INTEGER | Total processing time |
| llm_duration_ms | INTEGER | LLM thinking time only |

### conversations table

Persists chat context per user (survives restarts).

| Column | Type | Description |
|--------|------|-------------|
| context_id | TEXT | PK — chat ID or `default` |
| messages | TEXT | JSON array of PydanticAI ModelMessage objects |
| updated_at | TEXT | Last update timestamp |
