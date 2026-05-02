"""tools/history.py
History retrieval for nodes that need recent conversation context.
Enforces the CONTEXT_WINDOW_BUDGET token cap and the per-node limit
from HISTORY_LIMITS, returning entries in chronological order.
"""

import logging

from config import CONTEXT_WINDOW_BUDGET
from db.history.factory import get_history_repository
from tools.tokens import count_tokens

logger = logging.getLogger(__name__)

_repo = get_history_repository()


def get_history(user_id: str, limit: int) -> list[dict]:
    """Load conversation history for a user, trimmed to the context budget.

    Loads all history for user_id, then walks newest-first accumulating token
    counts until CONTEXT_WINDOW_BUDGET is reached. The kept entries are reversed
    back to chronological order and truncated to limit.

    On DB failure, returns an empty list rather than raising — nodes degrade
    gracefully to a no-history state.

    Args:
        user_id: The user whose history to load.
        limit: Maximum number of messages to return after budget trimming.

    Returns:
        list of {"role": str, "content": str} dicts in chronological order,
        at most limit entries.

    Side effects:
        Logs a WARNING on DB failure.
    """
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
