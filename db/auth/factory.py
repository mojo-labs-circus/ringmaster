import os

from config import DB_BACKEND, DB_PATH
from db.auth.postgres import PostgresAuthRepository
from db.auth.repository import AuthRepository
from db.auth.sqlite import SQLiteAuthRepository


def get_auth_repository() -> AuthRepository:
    if DB_BACKEND == "sqlite":
        db_path = os.path.join(DB_PATH, "auth.db")
        return SQLiteAuthRepository(db_path)
    elif DB_BACKEND == "postgres":
        return PostgresAuthRepository()
    else:
        raise ValueError(f"Unknown JARVIS_DB_BACKEND: '{DB_BACKEND}' — expected 'sqlite' or 'postgres'")
