from datetime import datetime

import pytest

from db.history.models import HistoryEntry
from db.history.sqlite import SQLiteHistoryRepository


def test_save_and_load(test_db):
    repo = SQLiteHistoryRepository(test_db["history"])
    user_entry = HistoryEntry(
        id=None,
        user_id="alice",
        role="user",
        content="hello",
        created_at=datetime(2026, 1, 1, 12, 0, 0),
    )
    assistant_entry = HistoryEntry(
        id=None,
        user_id="alice",
        role="assistant",
        content="hello back",
        created_at=datetime(2026, 1, 1, 12, 0, 1),
    )

    repo.save(user_entry)
    repo.save(assistant_entry)
    results = repo.load("alice")

    assert len(results) == 2
    assert results[0].role == "user"
    assert results[0].content == "hello"
    assert results[0].created_at == datetime(2026, 1, 1, 12, 0, 0)
    assert results[1].role == "assistant"
    assert results[1].content == "hello back"


def test_save_stamps_id(test_db):
    repo = SQLiteHistoryRepository(test_db["history"])
    entry = HistoryEntry(
        id=None,
        user_id="alice",
        role="user",
        content="hello",
        created_at=datetime(2026, 1, 1, 12, 0, 0),
    )

    repo.save(entry)

    assert entry.id is not None


def test_load_empty(test_db):
    repo = SQLiteHistoryRepository(test_db["history"])

    results = repo.load("alice")

    assert results == []


def test_load_scoped_to_user(test_db):
    repo = SQLiteHistoryRepository(test_db["history"])
    repo.save(HistoryEntry(
        id=None,
        user_id="alice",
        role="user",
        content="alice's message",
        created_at=datetime(2026, 1, 1, 12, 0, 0),
    ))
    repo.save(HistoryEntry(
        id=None,
        user_id="bob",
        role="user",
        content="bob's message",
        created_at=datetime(2026, 1, 1, 12, 0, 1),
    ))

    results = repo.load("alice")

    assert len(results) == 1
    assert results[0].content == "alice's message"
