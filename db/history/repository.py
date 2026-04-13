from abc import ABC, abstractmethod

from db.history.models import HistoryEntry


class HistoryRepository(ABC):

    @abstractmethod
    def load(self, user_id: str) -> list[dict]:
        # Returns recent history as [{"role": ..., "content": ...}, ...] in chronological order.
        # Bounded by CONTEXT_WINDOW_BUDGET tokens — oldest entries dropped first.
        ...

    @abstractmethod
    def save(self, entry: HistoryEntry) -> None:
        # Appends a single turn to the user's history.
        ...
