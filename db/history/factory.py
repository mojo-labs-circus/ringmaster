import os

from config import DB_BACKEND, DB_PATH
from db.history.postgres import PostgresHistoryRepository
from db.history.repository import HistoryRepository
from db.history.sqlite import SQLiteHistoryRepository


def get_history_repository() -> HistoryRepository:
    if DB_BACKEND == "sqlite":
        db_path = os.path.join(DB_PATH, "history.db")
        return SQLiteHistoryRepository(db_path)
    elif DB_BACKEND == "postgres":
        return PostgresHistoryRepository()
    else:
        raise ValueError(f"Unknown JARVIS_DB_BACKEND: '{DB_BACKEND}' — expected 'sqlite' or 'postgres'")
