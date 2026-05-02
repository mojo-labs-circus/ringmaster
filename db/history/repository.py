from abc import ABC, abstractmethod

from db.history.models import HistoryEntry


class HistoryRepository(ABC):

    @abstractmethod
    def load(self, user_id: str) -> list[HistoryEntry]:
        # Returns all history for user_id in chronological order.
        # Token budget enforcement and message formatting are the caller's responsibility.
        ...

    @abstractmethod
    def save(self, entry: HistoryEntry) -> None:
        # Appends a single turn to the user's history.
        ...
