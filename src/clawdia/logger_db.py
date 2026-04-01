from __future__ import annotations

import json
import time

import aiosqlite
from loguru import logger

_SCHEMA = """
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

CREATE TABLE IF NOT EXISTS conversations (
    context_id TEXT PRIMARY KEY,
    messages TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


class InteractionLogger:
    """Logs interactions and persists conversation history to SQLite."""

    def __init__(self, db_path: str = "clawdia_interactions.db"):
        self._db_path = db_path

    async def init_db(self) -> None:
        async with aiosqlite.connect(self._db_path) as db:
            await db.executescript(_SCHEMA)

    async def log(
        self,
        *,
        source: str,
        context_id: str | None,
        user_input: str,
        action: str | None = None,
        action_detail: str | dict | None = None,
        response_message: str | None = None,
        success: bool | None = None,
        duration_ms: int | None = None,
        llm_duration_ms: int | None = None,
    ) -> None:
        detail = action_detail
        if isinstance(detail, dict):
            detail = json.dumps(detail)
        try:
            async with aiosqlite.connect(self._db_path) as db:
                await db.execute(
                    """INSERT INTO interactions
                       (source, context_id, user_input, action, action_detail,
                        response_message, success, duration_ms, llm_duration_ms)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        source,
                        context_id,
                        user_input,
                        action,
                        detail,
                        response_message,
                        int(success) if success is not None else None,
                        duration_ms,
                        llm_duration_ms,
                    ),
                )
                await db.commit()
        except Exception:
            logger.exception("Failed to log interaction")

    async def save_history(self, context_id: str, messages_json: str) -> None:
        """Persist conversation history for a context."""
        try:
            async with aiosqlite.connect(self._db_path) as db:
                await db.execute(
                    """INSERT INTO conversations (context_id, messages, updated_at)
                       VALUES (?, ?, datetime('now'))
                       ON CONFLICT(context_id) DO UPDATE
                       SET messages = excluded.messages, updated_at = datetime('now')""",
                    (context_id, messages_json),
                )
                await db.commit()
        except Exception:
            logger.exception("Failed to save conversation history")

    async def load_all_history(self) -> dict[str, str]:
        """Load all conversation histories. Returns {context_id: messages_json}."""
        try:
            async with aiosqlite.connect(self._db_path) as db:
                cursor = await db.execute("SELECT context_id, messages FROM conversations")
                rows = await cursor.fetchall()
                return {row[0]: row[1] for row in rows}
        except Exception:
            logger.exception("Failed to load conversation history")
            return {}


def ms_since(start: float) -> int:
    """Convert a time.monotonic() start to milliseconds elapsed."""
    return int((time.monotonic() - start) * 1000)
