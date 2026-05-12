"""api/routes/tasks.py
Task list endpoints — GET /tasks and DELETE /tasks/{id}. Task creation and
completion are handled by the TASKS graph node, not directly via HTTP.
"""

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status

from api.dependencies import get_current_user
from api.schemas import TaskResponse
from db.auth.models import User
from db.tasks.factory import get_task_repository
from db.tasks.models import Task
from db.tasks.repository import TaskRepository

router = APIRouter(prefix="/tasks", tags=["tasks"])

_PRIORITY_RANK = {"high": 0, "medium": 1, "low": 2}


@router.get("", response_model=list[TaskResponse])
def list_tasks(
    sort_by: Literal["created_at", "priority", "due_date", "status"] = "created_at",
    order: Literal["asc", "desc"] = "desc",
    user: User = Depends(get_current_user),
    task_repo: TaskRepository = Depends(get_task_repository),
) -> list[TaskResponse]:
    """Return all tasks for the authenticated user, sorted as requested.

    Sorting is performed in Python after the full list is loaded — the DB always
    returns all rows unordered. due_date nulls sort last in both directions.

    Args:
        sort_by: Field to sort by — "created_at", "priority", "due_date", or "status".
        order: Sort direction — "asc" or "desc".
    """
    tasks = task_repo.list_tasks(user.username)
    sorted_tasks = _sort_tasks(tasks, sort_by, order)
    return [TaskResponse.from_task(t) for t in sorted_tasks]


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(
    task_id: int,
    user: User = Depends(get_current_user),
    task_repo: TaskRepository = Depends(get_task_repository),
) -> None:
    """Permanently delete a task. Scoped to the authenticated user — cannot delete other users' tasks.

    Raises:
        HTTPException 404: If the task does not exist or belongs to another user.
    """
    deleted = task_repo.delete_task(task_id, user.username)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")


def _sort_tasks(tasks: list[Task], sort_by: str, order: str) -> list[Task]:
    """Sort a list of Task objects by the given field and direction.

    Args:
        tasks: Unsorted list of Task objects.
        sort_by: Field name to sort by — "created_at", "priority", "due_date", or "status".
        order: "asc" or "desc".

    Returns:
        New sorted list — does not modify the input.
    """
    reverse = order == "desc"

    if sort_by == "priority":
        return sorted(tasks, key=lambda t: _PRIORITY_RANK[t.priority], reverse=reverse)

    if sort_by == "due_date":
        # (is_null, value) key keeps nulls last after reverse because is_null=1 > is_null=0
        # in both directions
        return sorted(
            tasks,
            key=lambda t: (t.due_date is None, t.due_date or datetime.min),
            reverse=reverse,
        )

    return sorted(tasks, key=lambda t: getattr(t, sort_by), reverse=reverse)
