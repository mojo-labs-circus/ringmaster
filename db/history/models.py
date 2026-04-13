from dataclasses import dataclass
from datetime import datetime


@dataclass
class HistoryEntry:
    id: int | None    # None before insert — assigned by the database on first write
    user_id: str
    role: str         # "user" | "assistant"
    content: str
    created_at: datetime
