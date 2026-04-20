from dataclasses import dataclass
from datetime import datetime


@dataclass
class Task:
    id: int | None        # None before insert — assigned by the database on first write
    user_id: str
    title: str
    status: str           # open | closed
    priority: str         # low | medium | high
    due_date: datetime | None
    created_at: datetime
