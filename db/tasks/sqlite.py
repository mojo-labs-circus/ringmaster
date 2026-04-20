import sqlite3
from datetime import datetime

from db.tasks.models import Task
from db.tasks.repository import TaskRepository


class SQLiteTaskRepository(TaskRepository):

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path

    def create_task(self, task: Task) -> Task:
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


def _row_to_task(row: tuple) -> Task:
    return Task(
        id=row[0],
        user_id=row[1],
        title=row[2],
        status=row[3],
        priority=row[4],
        due_date=datetime.fromisoformat(row[5]) if row[5] else None,
        created_at=datetime.fromisoformat(row[6]),
    )
