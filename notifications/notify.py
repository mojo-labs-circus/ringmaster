"""notifications/notify.py
Admin and (future) user notification dispatch.

notify_admin  — wraps ntfy for acute failures. Cooldown keyed on
                (error_class, message) so two distinct errors that share
                a class don't suppress each other.
"""

import logging
import time

from config import NOTIFY_COOLDOWN_SECONDS

logger = logging.getLogger(__name__)

# In-memory cooldown state — not persisted. Process restart clears it, which is
# fine: if JARVIS just crashed and restarted, the admin should hear about it again.
_last_notified: dict[tuple[str, str], float] = {}


def notify_admin(error_class: str, message: str) -> None:
    """Send an admin alert via ntfy, subject to a 10-minute cooldown.

    Cooldown is per (error_class, message) pair — distinct errors with the
    same class each get their own bucket.

    ntfy is not running on nomadbaker yet, so the HTTP call is stubbed.
    Swap the stub body for a real requests.post() call when ntfy is available.
    """
    key = (error_class, message)
    now = time.monotonic()

    if now - _last_notified.get(key, 0.0) < NOTIFY_COOLDOWN_SECONDS:
        return

    _last_notified[key] = now

    # --- stub: replace with real ntfy call when the service is running ---
    # import requests
    # requests.post(
    #     "http://localhost:2586/jarvis-admin",
    #     data=message.encode(),
    #     headers={"Title": error_class, "Priority": "high"},
    #     timeout=5,
    # )
    logger.warning("ADMIN NOTIFY [%s]: %s", error_class, message)
    # --- end stub ---
