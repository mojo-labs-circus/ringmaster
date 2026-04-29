import logging

from db.history.factory import get_history_repository

logger = logging.getLogger(__name__)

_repo = get_history_repository()


def get_history(user_id: str, limit: int) -> list[dict]:
    try:
        history = _repo.load(user_id)
        return history[-limit:]
    except Exception:
        logger.warning("Failed to load history for user %s — returning empty list", user_id)
        # TODO: consider calling notify_admin here so persistent DB errors don't go unnoticed
        return []
