"""db/tasks/repository.py
Abstract base class defining the TaskRepository interface. Both
SQLiteTaskRepository and PostgresTaskRepository implement this contract.
"""

from abc import ABC, abstractmethod
from datetime import datetime

from db.tasks.models import Task


class TaskRepository(ABC):
    """Interface for task data operations.

    All mutating methods return bool indicating whether the target row was found
    and operated on. user_id is always checked inside the implementation to
    prevent cross-user access — callers don't need to verify ownership separately.
    """

    @abstractmethod
    def create_task(self, task: Task) -> Task:
        # Returns the same object with id set from the database
        ...

    @abstractmethod
    def get_task(self, task_id: int, user_id: str) -> Task | None:
        # Returns None if not found or not owned by user_id
        ...

    @abstractmethod
    def list_tasks(self, user_id: str) -> list[Task]:
        # Returns all tasks (open and closed) for user_id — sorting done by caller
        ...

    @abstractmethod
    def update_task(self, task_id: int, user_id: str, title: str | None, priority: str | None, due_date: datetime | None) -> bool:
        # Returns True if found and updated, False if not found or not owned
        ...

    @abstractmethod
    def complete_task(self, task_id: int, user_id: str) -> bool:
        # Sets status to closed. Returns True if found and updated, False otherwise
        ...

    @abstractmethod
    def delete_task(self, task_id: int, user_id: str) -> bool:
        # Permanently deletes. Returns True if found and deleted, False otherwise
        ...
