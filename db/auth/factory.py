"""db/auth/factory.py
Factory for AuthRepository. Returns the correct implementation based on
JARVIS_DB_BACKEND. Used as a FastAPI dependency via Depends(get_auth_repository).
"""

import os

from config import DB_BACKEND, DB_PATH
from db.auth.postgres import PostgresAuthRepository
from db.auth.repository import AuthRepository
from db.auth.sqlite import SQLiteAuthRepository


def get_auth_repository() -> AuthRepository:
    """Return the configured AuthRepository implementation.

    Returns:
        SQLiteAuthRepository in dev, PostgresAuthRepository in production.

    Raises:
        ValueError: If JARVIS_DB_BACKEND is set to an unrecognised value.
    """
    if DB_BACKEND == "sqlite":
        db_path = os.path.join(DB_PATH, "auth.db")
        return SQLiteAuthRepository(db_path)
    elif DB_BACKEND == "postgres":
        return PostgresAuthRepository()
    else:
        raise ValueError(f"Unknown JARVIS_DB_BACKEND: '{DB_BACKEND}' — expected 'sqlite' or 'postgres'")
