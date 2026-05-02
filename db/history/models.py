"""db/history/models.py
Dataclass representing a single conversation turn in the history table.
One HistoryEntry per message — user and assistant sides are stored as
separate rows so the budget trimmer can calculate token cost per turn.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class HistoryEntry:
    """A single conversation turn (one message) stored in the history table.

    role is always "user" or "assistant". id is None before insert — stamped by
    the database on first write.
    """

    id: int | None    # None before insert — assigned by the database on first write
    user_id: str
    role: str         # "user" | "assistant"
    content: str
    created_at: datetime
