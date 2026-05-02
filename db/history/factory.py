"""db/history/factory.py
Factory for HistoryRepository. Returns the correct implementation based on
JARVIS_DB_BACKEND. Used as a FastAPI dependency and imported at module level
by tools/history.py.
"""

import os

from config import DB_BACKEND, DB_PATH
from db.history.postgres import PostgresHistoryRepository
from db.history.repository import HistoryRepository
from db.history.sqlite import SQLiteHistoryRepository


def get_history_repository() -> HistoryRepository:
    """Return the configured HistoryRepository implementation.

    Returns:
        SQLiteHistoryRepository in dev, PostgresHistoryRepository in production.

    Raises:
        ValueError: If JARVIS_DB_BACKEND is set to an unrecognised value.
    """
    if DB_BACKEND == "sqlite":
        db_path = os.path.join(DB_PATH, "history.db")
        return SQLiteHistoryRepository(db_path)
    elif DB_BACKEND == "postgres":
        return PostgresHistoryRepository()
    else:
        raise ValueError(f"Unknown JARVIS_DB_BACKEND: '{DB_BACKEND}' — expected 'sqlite' or 'postgres'")
