"""db/tasks/postgres.py
Postgres implementation of TaskRepository. Stub only — all methods raise
NotImplementedError. Full implementation is deferred to the server deployment milestone.
"""

from datetime import datetime

from db.tasks.models import Task
from db.tasks.repository import TaskRepository


class PostgresTaskRepository(TaskRepository):
    """TaskRepository backed by Postgres. Stub only — raises NotImplementedError on all methods."""

    # Full implementation deferred to Phase 5 — SQLite is the dev backend until then

    def create_task(self, task: Task) -> Task:
        raise NotImplementedError("PostgresTaskRepository is not implemented until Phase 5")

    def get_task(self, task_id: int, user_id: str) -> Task | None:
        raise NotImplementedError("PostgresTaskRepository is not implemented until Phase 5")

    def list_tasks(self, user_id: str) -> list[Task]:
        raise NotImplementedError("PostgresTaskRepository is not implemented until Phase 5")

    def update_task(self, task_id: int, user_id: str, title: str | None, priority: str | None, due_date: datetime | None) -> bool:
        raise NotImplementedError("PostgresTaskRepository is not implemented until Phase 5")

    def complete_task(self, task_id: int, user_id: str) -> bool:
        raise NotImplementedError("PostgresTaskRepository is not implemented until Phase 5")

    def delete_task(self, task_id: int, user_id: str) -> bool:
        raise NotImplementedError("PostgresTaskRepository is not implemented until Phase 5")
