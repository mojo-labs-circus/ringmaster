"""db/tasks/models.py
Dataclass representing a row in the tasks table. Tasks are created and updated
by the TASKS graph node and read directly via GET /tasks.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class Task:
    """A single task row. id is None before insert — stamped by the database on first write.

    status is "open" or "closed" — there is no "in progress" state in Mk1.
    """

    id: int | None        # None before insert — assigned by the database on first write
    user_id: str
    title: str
    status: str           # open | closed
    priority: str         # low | medium | high
    due_date: datetime | None
    created_at: datetime
