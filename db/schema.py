"""db/schema.py
SQLite-only. Creates all tables across all three database files on startup.
Called from FastAPI's lifespan context manager, gated on DB_BACKEND == 'sqlite'.
Never called at module import time. Never called when DB_BACKEND == 'postgres' —
Postgres schema is managed by Alembic migrations introduced in Phase 5.

To reset a table during development, delete the relevant .db file and restart —
startup will recreate it. Delete auth.db for auth tables, tasks.db for tasks,
history.db for history.
"""

import os
import sqlite3

from config import DB_PATH


def create_tables() -> None:
    _create_auth_tables()
    _create_tasks_tables()
    _create_history_tables()


def _create_auth_tables() -> None:
    """Create users, refresh_tokens, and invites tables in auth.db if they don't exist."""
    connection = sqlite3.connect(os.path.join(DB_PATH, "auth.db"))
    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username       TEXT PRIMARY KEY,
            password_hash  TEXT NOT NULL,
            tier           TEXT NOT NULL,
            assistant_name TEXT NOT NULL,
            token_version  INTEGER NOT NULL DEFAULT 0,
            disabled       INTEGER NOT NULL DEFAULT 0
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS refresh_tokens (
            id          INTEGER PRIMARY KEY,
            user_id     TEXT NOT NULL REFERENCES users(username),
            token_hash  TEXT NOT NULL UNIQUE,
            expires_at  TEXT NOT NULL,
            revoked     INTEGER NOT NULL DEFAULT 0
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS invites (
            id             INTEGER PRIMARY KEY,
            token_hash     TEXT NOT NULL UNIQUE,
            type           TEXT NOT NULL DEFAULT 'invite',
            username       TEXT NOT NULL,
            tier           TEXT,
            assistant_name TEXT,
            expires_at     TEXT NOT NULL,
            used           INTEGER NOT NULL DEFAULT 0
        )
    """)

    connection.commit()
    connection.close()


def _create_tasks_tables() -> None:
    """Create the tasks table in tasks.db if it doesn't exist."""
    connection = sqlite3.connect(os.path.join(DB_PATH, "tasks.db"))
    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id         INTEGER PRIMARY KEY,
            user_id    TEXT NOT NULL,
            title      TEXT NOT NULL,
            status     TEXT NOT NULL DEFAULT 'open',
            priority   TEXT NOT NULL,
            due_date   TEXT,
            created_at TEXT NOT NULL
        )
    """)

    connection.commit()
    connection.close()


def _create_history_tables() -> None:
    """Create the history table in history.db if it doesn't exist."""
    connection = sqlite3.connect(os.path.join(DB_PATH, "history.db"))
    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id         INTEGER PRIMARY KEY,
            user_id    TEXT NOT NULL,
            role       TEXT NOT NULL,
            content    TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    connection.commit()
    connection.close()
