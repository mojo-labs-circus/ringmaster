"""db/history/repository.py
Abstract base class defining the HistoryRepository interface. Both
SQLiteHistoryRepository and PostgresHistoryRepository implement this contract.
"""

from abc import ABC, abstractmethod

from db.history.models import HistoryEntry


class HistoryRepository(ABC):
    """Interface for conversation history storage.

    load() returns all history for a user in chronological order — token budget
    enforcement and message limit are the caller's responsibility (tools/history.py).
    """

    @abstractmethod
    def load(self, user_id: str) -> list[HistoryEntry]:
        # Returns all history for user_id in chronological order.
        # Token budget enforcement and message formatting are the caller's responsibility.
        ...

    @abstractmethod
    def save(self, entry: HistoryEntry) -> None:
        # Appends a single turn to the user's history.
        ...
