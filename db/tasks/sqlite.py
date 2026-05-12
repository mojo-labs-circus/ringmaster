"""db/tasks/sqlite.py
SQLite implementation of TaskRepository. Connects per-method to avoid
cross-thread connection sharing with FastAPI.
"""

import sqlite3
from datetime import datetime

from db.tasks.models import Task
from db.tasks.repository import TaskRepository


def _row_to_task(row: tuple) -> Task:
    """Convert a raw SELECT row tuple to a Task dataclass."""
    return Task(
        id=row[0],
        user_id=row[1],
        title=row[2],
        status=row[3],
        priority=row[4],
        due_date=datetime.fromisoformat(row[5]) if row[5] else None,
        created_at=datetime.fromisoformat(row[6]),
    )


class SQLiteTaskRepository(TaskRepository):
    """TaskRepository backed by a local SQLite file at DB_PATH/tasks.db."""

    def __init__(self, db_path: str) -> None:
        # Connection opened per method, not held open, to avoid SQLite's
        # cross-thread connection issues with FastAPI.
        self.db_path = db_path

    def create_task(self, task: Task) -> Task:
        """Insert a task row and stamp the database-assigned id back onto task."""
        connection = sqlite3.connect(self.db_path)
        cursor = connection.cursor()
        cursor.execute(
            "INSERT INTO tasks (user_id, title, status, priority, due_date, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                task.user_id,
                task.title,
                task.status,
                task.priority,
                task.due_date.isoformat() if task.due_date else None,
                task.created_at.isoformat(),
            ),
        )
        connection.commit()
        task.id = cursor.lastrowid
        connection.close()
        return task

    def get_task(self, task_id: int, user_id: str) -> Task | None:
        """Return the Task for task_id owned by user_id, or None if not found or not owned."""
        connection = sqlite3.connect(self.db_path)
        cursor = connection.cursor()
        cursor.execute(
            "SELECT id, user_id, title, status, priority, due_date, created_at "
            "FROM tasks WHERE id = ? AND user_id = ?",
            (task_id, user_id),
        )
        row = cursor.fetchone()
        connection.close()
        if row is None:
            return None
        return _row_to_task(row)

    def list_tasks(self, user_id: str) -> list[Task]:
        """Return all tasks for user_id, unsorted. Sorting is the caller's responsibility."""
        connection = sqlite3.connect(self.db_path)
        cursor = connection.cursor()
        cursor.execute(
            "SELECT id, user_id, title, status, priority, due_date, created_at "
            "FROM tasks WHERE user_id = ?",
            (user_id,),
        )
        rows = cursor.fetchall()
        connection.close()
        return [_row_to_task(row) for row in rows]

    def update_task(self, task_id: int, user_id: str, title: str | None, priority: str | None, due_date: datetime | None) -> bool:
        """Update whichever of title, priority, due_date are non-None. Returns True if found and updated."""
        connection = sqlite3.connect(self.db_path)
        cursor = connection.cursor()
        cursor.execute(
            "UPDATE tasks SET title = COALESCE(?, title), priority = COALESCE(?, priority), due_date = COALESCE(?, due_date) "
            "WHERE id = ? AND user_id = ?",
            (
                title,
                priority,
                due_date.isoformat() if due_date else None,
                task_id,
                user_id,
            ),
        )
        connection.commit()
        updated = cursor.rowcount > 0
        connection.close()
        return updated

    def complete_task(self, task_id: int, user_id: str) -> bool:
        """Set status to 'closed'. Returns True if found and updated."""
        connection = sqlite3.connect(self.db_path)
        cursor = connection.cursor()
        cursor.execute(
            "UPDATE tasks SET status = 'closed' WHERE id = ? AND user_id = ?",
            (task_id, user_id),
        )
        connection.commit()
        updated = cursor.rowcount > 0
        connection.close()
        return updated

    def delete_task(self, task_id: int, user_id: str) -> bool:
        """Permanently delete the task. Returns True if found and deleted."""
        connection = sqlite3.connect(self.db_path)
        cursor = connection.cursor()
        cursor.execute(
            "DELETE FROM tasks WHERE id = ? AND user_id = ?",
            (task_id, user_id),
        )
        connection.commit()
        deleted = cursor.rowcount > 0
        connection.close()
        return deleted
