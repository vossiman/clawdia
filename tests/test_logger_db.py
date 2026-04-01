"""Tests for InteractionLogger — interactions and conversation persistence."""

import json

import pytest

from clawdia.logger_db import InteractionLogger


@pytest.fixture
async def db(tmp_path):
    logger = InteractionLogger(db_path=str(tmp_path / "test.db"))
    await logger.init_db()
    return logger


async def test_log_interaction(db):
    await db.log(
        source="telegram",
        context_id="123",
        user_input="turn on the tv",
        action="ir",
        response_message="Done!",
        success=True,
        duration_ms=150,
    )
    # No exception means success — logger swallows errors


async def test_save_and_load_history(db):
    messages = json.dumps([{"role": "user", "content": "hello"}])
    await db.save_history("ctx1", messages)
    await db.save_history("ctx2", json.dumps([{"role": "user", "content": "hi"}]))

    loaded = await db.load_all_history()
    assert "ctx1" in loaded
    assert "ctx2" in loaded
    assert json.loads(loaded["ctx1"]) == [{"role": "user", "content": "hello"}]


async def test_save_history_upsert(db):
    await db.save_history("ctx1", json.dumps([{"role": "user", "content": "v1"}]))
    await db.save_history("ctx1", json.dumps([{"role": "user", "content": "v2"}]))

    loaded = await db.load_all_history()
    assert json.loads(loaded["ctx1"]) == [{"role": "user", "content": "v2"}]


async def test_load_empty(db):
    loaded = await db.load_all_history()
    assert loaded == {}
