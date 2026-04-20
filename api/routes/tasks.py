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
    tasks = task_repo.list_tasks(user.username)
    sorted_tasks = _sort_tasks(tasks, sort_by, order)
    return [TaskResponse.from_task(t) for t in sorted_tasks]


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(
    task_id: int,
    user: User = Depends(get_current_user),
    task_repo: TaskRepository = Depends(get_task_repository),
) -> None:
    deleted = task_repo.delete_task(task_id, user.username)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")


def _sort_tasks(tasks: list[Task], sort_by: str, order: str) -> list[Task]:
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
