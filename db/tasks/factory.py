import os

from config import DB_BACKEND, DB_PATH
from db.tasks.postgres import PostgresTaskRepository
from db.tasks.repository import TaskRepository
from db.tasks.sqlite import SQLiteTaskRepository


def get_task_repository() -> TaskRepository:
    if DB_BACKEND == "sqlite":
        db_path = os.path.join(DB_PATH, "tasks.db")
        return SQLiteTaskRepository(db_path)
    elif DB_BACKEND == "postgres":
        return PostgresTaskRepository()
    else:
        raise ValueError(f"Unknown JARVIS_DB_BACKEND: '{DB_BACKEND}' — expected 'sqlite' or 'postgres'")
