"""db/history/sqlite.py
SQLite implementation of HistoryRepository. Connects per-method to avoid
cross-thread connection sharing with FastAPI.
"""

import sqlite3
from datetime import datetime

from db.history.models import HistoryEntry
from db.history.repository import HistoryRepository


def _row_to_entry(row: tuple) -> HistoryEntry:
    """Convert a raw SELECT row tuple to a HistoryEntry dataclass."""
    return HistoryEntry(
        id=row[0],
        user_id=row[1],
        role=row[2],
        content=row[3],
        created_at=datetime.fromisoformat(row[4]),
    )


class SQLiteHistoryRepository(HistoryRepository):
    """HistoryRepository backed by a local SQLite file at DB_PATH/history.db."""

    def __init__(self, db_path: str) -> None:
        # Path to history.db — connection opened per method, not held open,
        # to avoid SQLite's cross-thread connection issues with FastAPI.
        self.db_path = db_path

    def load(self, user_id: str) -> list[HistoryEntry]:
        """Return all history entries for user_id in chronological order."""
        connection = sqlite3.connect(self.db_path)
        cursor = connection.cursor()
        cursor.execute(
            "SELECT id, user_id, role, content, created_at FROM history "
            "WHERE user_id = ? "
            "ORDER BY created_at ASC",
            (user_id,),
        )
        rows = cursor.fetchall()
        connection.close()
        return [_row_to_entry(row) for row in rows]

    def save(self, entry: HistoryEntry) -> None:
        """Append a history entry and stamp the database-assigned id back onto entry."""
        connection = sqlite3.connect(self.db_path)
        cursor = connection.cursor()
        cursor.execute(
            "INSERT INTO history (user_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (entry.user_id, entry.role, entry.content, entry.created_at.isoformat()),
        )
        connection.commit()
        entry.id = cursor.lastrowid  # stamp the database-assigned id back onto the dataclass
        connection.close()
