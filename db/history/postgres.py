"""db/history/postgres.py
Postgres implementation of HistoryRepository. Stub only — all methods raise
NotImplementedError. Full implementation is deferred to the server deployment milestone.
"""

from db.history.models import HistoryEntry
from db.history.repository import HistoryRepository


class PostgresHistoryRepository(HistoryRepository):
    """HistoryRepository backed by Postgres. Stub only — raises NotImplementedError on all methods."""

    # Full implementation deferred to Phase 5 — SQLite is the dev backend until then

    def load(self, user_id: str) -> list[HistoryEntry]:
        raise NotImplementedError("PostgresHistoryRepository is not implemented until Phase 5")

    def save(self, entry: HistoryEntry) -> None:
        raise NotImplementedError("PostgresHistoryRepository is not implemented until Phase 5")
