from datetime import datetime

import pytest

from db.tasks.models import Task
from db.tasks.sqlite import SQLiteTaskRepository


def test_create_and_get_task(test_db):
    repo = SQLiteTaskRepository(test_db["tasks"])
    task = Task(
        id=None,
        user_id="alice",
        title="Buy milk",
        status="open",
        priority="low",
        due_date=datetime(2026, 6, 1, 9, 0, 0),
        created_at=datetime(2026, 1, 1, 12, 0, 0),
    )

    returned = repo.create_task(task)
    result = repo.get_task(returned.id, "alice")

    assert result is not None
    assert result.user_id == "alice"
    assert result.title == "Buy milk"
    assert result.status == "open"
    assert result.priority == "low"
    assert result.due_date == datetime(2026, 6, 1, 9, 0, 0)
    assert result.created_at == datetime(2026, 1, 1, 12, 0, 0)


def test_create_task_due_date_none(test_db):
    repo = SQLiteTaskRepository(test_db["tasks"])
    task = Task(
        id=None,
        user_id="alice",
        title="Buy milk",
        status="open",
        priority="low",
        due_date=None,
        created_at=datetime(2026, 1, 1, 12, 0, 0),
    )

    returned = repo.create_task(task)
    result = repo.get_task(returned.id, "alice")

    assert result.due_date is None


def test_get_task_missing(test_db):
    repo = SQLiteTaskRepository(test_db["tasks"])

    result = repo.get_task(999, "alice")

    assert result is None


def test_get_task_wrong_user(test_db):
    repo = SQLiteTaskRepository(test_db["tasks"])
    task = Task(
        id=None,
        user_id="alice",
        title="Buy milk",
        status="open",
        priority="low",
        due_date=None,
        created_at=datetime(2026, 1, 1, 12, 0, 0),
    )
    returned = repo.create_task(task)

    result = repo.get_task(returned.id, "bob")

    assert result is None


def test_list_tasks_scoped_to_user(test_db):
    repo = SQLiteTaskRepository(test_db["tasks"])
    repo.create_task(Task(
        id=None,
        user_id="alice",
        title="Alice's task",
        status="open",
        priority="low",
        due_date=None,
        created_at=datetime(2026, 1, 1, 12, 0, 0),
    ))
    repo.create_task(Task(
        id=None,
        user_id="bob",
        title="Bob's task",
        status="open",
        priority="low",
        due_date=None,
        created_at=datetime(2026, 1, 1, 12, 0, 1),
    ))

    results = repo.list_tasks("alice")

    assert len(results) == 1
    assert results[0].title == "Alice's task"


def test_list_tasks_empty(test_db):
    repo = SQLiteTaskRepository(test_db["tasks"])

    results = repo.list_tasks("alice")

    assert results == []


def test_update_task(test_db):
    repo = SQLiteTaskRepository(test_db["tasks"])
    returned = repo.create_task(Task(
        id=None,
        user_id="alice",
        title="Buy milk",
        status="open",
        priority="low",
        due_date=None,
        created_at=datetime(2026, 1, 1, 12, 0, 0),
    ))

    updated = repo.update_task(returned.id, "alice", title="Buy oat milk", priority=None, due_date=None)
    result = repo.get_task(returned.id, "alice")

    assert updated is True
    assert result.title == "Buy oat milk"
    assert result.priority == "low"


def test_update_task_missing(test_db):
    repo = SQLiteTaskRepository(test_db["tasks"])

    updated = repo.update_task(999, "alice", title="Buy oat milk", priority=None, due_date=None)

    assert updated is False


def test_complete_task(test_db):
    repo = SQLiteTaskRepository(test_db["tasks"])
    returned = repo.create_task(Task(
        id=None,
        user_id="alice",
        title="Buy milk",
        status="open",
        priority="low",
        due_date=None,
        created_at=datetime(2026, 1, 1, 12, 0, 0),
    ))

    updated = repo.complete_task(returned.id, "alice")
    result = repo.get_task(returned.id, "alice")

    assert updated is True
    assert result.status == "closed"


def test_complete_task_missing(test_db):
    repo = SQLiteTaskRepository(test_db["tasks"])

    updated = repo.complete_task(999, "alice")

    assert updated is False


def test_delete_task(test_db):
    repo = SQLiteTaskRepository(test_db["tasks"])
    returned = repo.create_task(Task(
        id=None,
        user_id="alice",
        title="Buy milk",
        status="open",
        priority="low",
        due_date=None,
        created_at=datetime(2026, 1, 1, 12, 0, 0),
    ))

    deleted = repo.delete_task(returned.id, "alice")
    result = repo.get_task(returned.id, "alice")

    assert deleted is True
    assert result is None


def test_delete_task_missing(test_db):
    repo = SQLiteTaskRepository(test_db["tasks"])

    deleted = repo.delete_task(999, "alice")

    assert deleted is False
