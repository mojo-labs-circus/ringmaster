"""db/tasks/factory.py
Factory for TaskRepository. Returns the correct implementation based on
JARVIS_DB_BACKEND. Used as a FastAPI dependency via Depends(get_task_repository).
"""

import os

from config import DB_BACKEND, DB_PATH
from db.tasks.postgres import PostgresTaskRepository
from db.tasks.repository import TaskRepository
from db.tasks.sqlite import SQLiteTaskRepository


def get_task_repository() -> TaskRepository:
    """Return the configured TaskRepository implementation.

    Returns:
        SQLiteTaskRepository in dev, PostgresTaskRepository in production.

    Raises:
        ValueError: If JARVIS_DB_BACKEND is set to an unrecognised value.
    """
    if DB_BACKEND == "sqlite":
        db_path = os.path.join(DB_PATH, "tasks.db")
        return SQLiteTaskRepository(db_path)
    elif DB_BACKEND == "postgres":
        return PostgresTaskRepository()
    else:
        raise ValueError(f"Unknown JARVIS_DB_BACKEND: '{DB_BACKEND}' — expected 'sqlite' or 'postgres'")
