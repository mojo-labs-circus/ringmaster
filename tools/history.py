import logging

from config import CONTEXT_WINDOW_BUDGET
from db.history.factory import get_history_repository
from tools.tokens import count_tokens

logger = logging.getLogger(__name__)

_repo = get_history_repository()


def get_history(user_id: str, limit: int) -> list[dict]:
    try:
        entries = _repo.load(user_id)
    except Exception:
        logger.warning("Failed to load history for user %s — returning empty list", user_id)
        # TODO: consider calling notify_admin here so persistent DB errors don't go unnoticed
        return []

    # Walk newest-first, accumulate token count, drop oldest entries that
    # would push us over the budget. Reversed at the end to restore
    # chronological order for the model.
    kept = []
    total = 0
    for entry in reversed(entries):
        cost = count_tokens(entry.role + entry.content)
        if total + cost > CONTEXT_WINDOW_BUDGET:
            break
        kept.append(entry)
        total += cost

    history = [{"role": entry.role, "content": entry.content} for entry in reversed(kept)]
    return history[-limit:]
