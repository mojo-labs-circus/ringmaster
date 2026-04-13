import sqlite3

from db.history.models import HistoryEntry
from db.history.repository import HistoryRepository


class SQLiteHistoryRepository(HistoryRepository):

    def __init__(self, db_path: str) -> None:
        # Path to history.db — connection opened per method, not held open,
        # to avoid SQLite's cross-thread connection issues with FastAPI.
        self.db_path = db_path

    def load(self, user_id: str) -> list[dict]:
        connection = sqlite3.connect(self.db_path)
        cursor = connection.cursor()
        cursor.execute(
            "SELECT role, content FROM history "
            "WHERE user_id = ? "
            "ORDER BY created_at ASC",
            (user_id,),
        )
        rows = cursor.fetchall()
        connection.close()
        # TODO: trim to CONTEXT_WINDOW_BUDGET tokens once tools/tokens.py is built.
        # Walk rows newest-first, accumulate running token count, stop when budget
        # would be exceeded, then reverse to restore chronological order.
        return [{"role": row[0], "content": row[1]} for row in rows]

    def save(self, entry: HistoryEntry) -> None:
        connection = sqlite3.connect(self.db_path)
        cursor = connection.cursor()
        cursor.execute(
            "INSERT INTO history (user_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (entry.user_id, entry.role, entry.content, entry.created_at.isoformat()),
        )
        connection.commit()
        entry.id = cursor.lastrowid  # stamp the database-assigned id back onto the dataclass
        connection.close()
