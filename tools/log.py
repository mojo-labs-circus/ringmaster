import json
import logging
from datetime import datetime, timezone

from config import IMPROVE_LOG_PATH
from notifications.notify import notify_admin

logger = logging.getLogger(__name__)


def log_improvement(event: str, user_id: str, message_id: str, **data) -> None:
    entry = {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "event": event,
        "user_id": user_id,
        "message_id": message_id,
        "data": data,
    }
    try:
        with open(IMPROVE_LOG_PATH, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError:
        logger.warning("Failed to write to improve.jsonl — check disk/permissions")
        notify_admin("ImproveLogError", "Failed to write improve.jsonl — check disk/permissions")
