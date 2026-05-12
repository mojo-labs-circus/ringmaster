import os

# Must be set before any import that transitively imports config.py,
# which reads JARVIS_SECRET_KEY from the environment at module load time.
os.environ.setdefault("JARVIS_SECRET_KEY", "test-secret-key")

import sqlite3
from unittest.mock import patch

import pytest

from db.auth.models import User
from tools.llm import StreamResult


# ---------------------------------------------------------------------------
# User fixtures — dataclasses only, no DB insert
# ---------------------------------------------------------------------------

@pytest.fixture
def user_standard():
    return User(
        username="teststandard",
        password_hash="$2b$12$fakehashforstandard",
        tier="standard",
        assistant_name="Jarvis",
        token_version=0,
        disabled=False,
    )


@pytest.fixture
def user_power():
    return User(
        username="testpower",
        password_hash="$2b$12$fakehashforpower",
        tier="power",
        assistant_name="Jarvis",
        token_version=0,
        disabled=False,
    )


@pytest.fixture
def user_admin():
    return User(
        username="testadmin",
        password_hash="$2b$12$fakehashforadmin",
        tier="admin",
        assistant_name="Jarvis",
        token_version=0,
        disabled=False,
    )


# ---------------------------------------------------------------------------
# test_db — three temp SQLite files with the real schema, wiped after each test
# ---------------------------------------------------------------------------

def _apply_schema(db_path: str, ddl: str) -> None:
    conn = sqlite3.connect(db_path)
    conn.executescript(ddl)
    conn.commit()
    conn.close()


_AUTH_DDL = """
CREATE TABLE IF NOT EXISTS users (
    username       TEXT PRIMARY KEY,
    password_hash  TEXT NOT NULL,
    tier           TEXT NOT NULL,
    assistant_name TEXT NOT NULL,
    token_version  INTEGER NOT NULL DEFAULT 0,
    disabled       INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS refresh_tokens (
    id          INTEGER PRIMARY KEY,
    user_id     TEXT NOT NULL REFERENCES users(username),
    token_hash  TEXT NOT NULL UNIQUE,
    expires_at  TEXT NOT NULL,
    revoked     INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS invites (
    id             INTEGER PRIMARY KEY,
    token_hash     TEXT NOT NULL UNIQUE,
    type           TEXT NOT NULL DEFAULT 'invite',
    username       TEXT NOT NULL,
    tier           TEXT,
    assistant_name TEXT,
    expires_at     TEXT NOT NULL,
    used           INTEGER NOT NULL DEFAULT 0
);
"""

_HISTORY_DDL = """
CREATE TABLE IF NOT EXISTS history (
    id         INTEGER PRIMARY KEY,
    user_id    TEXT NOT NULL,
    role       TEXT NOT NULL,
    content    TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""

_TASKS_DDL = """
CREATE TABLE IF NOT EXISTS tasks (
    id         INTEGER PRIMARY KEY,
    user_id    TEXT NOT NULL,
    title      TEXT NOT NULL,
    status     TEXT NOT NULL DEFAULT 'open',
    priority   TEXT NOT NULL,
    due_date   TEXT,
    created_at TEXT NOT NULL
);
"""


@pytest.fixture
def test_db(tmp_path):
    auth_path = str(tmp_path / "auth.db")
    history_path = str(tmp_path / "history.db")
    tasks_path = str(tmp_path / "tasks.db")

    _apply_schema(auth_path, _AUTH_DDL)
    _apply_schema(history_path, _HISTORY_DDL)
    _apply_schema(tasks_path, _TASKS_DDL)

    yield {"auth": auth_path, "history": history_path, "tasks": tasks_path}

    # tmp_path is managed by pytest — cleaned up automatically after the test


# ---------------------------------------------------------------------------
# mock_ollama — patches tools.llm.stream_chat for the duration of the test
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_ollama():
    """Patches stream_chat so no test ever calls Ollama.

    Default return value is StreamResult(model="mock", tokens=iter(["mock response"])).
    Tests that need a specific response reassign mock_ollama.return_value before
    calling the code under test.
    The mock is yielded so tests can also assert on call arguments:
        mock_ollama.assert_called_once_with(ROUTER_MODEL, ..., node="router", ...)
    """
    with patch("tools.llm.stream_chat") as mock:
        mock.return_value = StreamResult(model="mock", tokens=iter(["mock response"]))
        yield mock
