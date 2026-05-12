"""maintenance/cleanup.py
Daily maintenance pass — designed to accumulate tasks over time.
New maintenance needs get added here rather than spinning up separate jobs.

Run by ofelia (Phase 6) on a daily schedule, or directly:
    python -m maintenance.cleanup
"""

import logging
import os
import sqlite3
from datetime import datetime, timedelta, timezone

from config import DB_PATH, LOG_ERROR_THRESHOLD, LOG_PATH, RETENTION_DAYS
from logging_config import LOG_FORMAT
from notifications.notify import notify_admin

logger = logging.getLogger(__name__)


def run_cleanup() -> None:
    logger.info("Maintenance pass starting")
    _purge_expired_refresh_tokens()
    _purge_expired_invites()
    _purge_old_history()
    _check_error_log()
    logger.info("Maintenance pass complete")


def _purge_expired_refresh_tokens() -> None:
    now = datetime.now(timezone.utc).isoformat()
    connection = sqlite3.connect(os.path.join(DB_PATH, "auth.db"))
    cursor = connection.cursor()
    cursor.execute("DELETE FROM refresh_tokens WHERE expires_at < ?", (now,))
    count = cursor.rowcount
    connection.commit()
    connection.close()
    logger.info("Purged %d expired refresh token(s)", count)


def _purge_expired_invites() -> None:
    now = datetime.now(timezone.utc).isoformat()
    connection = sqlite3.connect(os.path.join(DB_PATH, "auth.db"))
    cursor = connection.cursor()
    cursor.execute("DELETE FROM invites WHERE expires_at < ?", (now,))
    count = cursor.rowcount
    connection.commit()
    connection.close()
    logger.info("Purged %d expired invite(s)", count)


def _purge_old_history() -> None:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)).isoformat()
    connection = sqlite3.connect(os.path.join(DB_PATH, "history.db"))
    cursor = connection.cursor()
    cursor.execute("DELETE FROM history WHERE created_at < ?", (cutoff,))
    count = cursor.rowcount
    connection.commit()
    connection.close()
    logger.info("Purged %d history entry/entries older than %d days", count, RETENTION_DAYS)


def _check_error_log() -> None:
    # Count ERROR-level lines written in the last 24 hours.
    # Lines start with a date prefix (e.g. "2026-04-13 14:23:01,234") — we check
    # whether the date portion matches today or yesterday to cover the full 24h window.
    if not os.path.exists(LOG_PATH):
        return

    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")
    yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")

    error_count = 0
    with open(LOG_PATH, "r") as f:
        for line in f:
            date_prefix = line[:10]
            if date_prefix in (today, yesterday) and " ERROR " in line:
                error_count += 1

    logger.info("Found %d ERROR log line(s) in the last 24 hours", error_count)

    if error_count > LOG_ERROR_THRESHOLD:
        notify_admin(
            "HighErrorRate",
            f"{error_count} ERROR-level log entries in the last 24 hours (threshold: {LOG_ERROR_THRESHOLD})",
        )


if __name__ == "__main__":
    # Allow running directly: python -m maintenance.cleanup
    # Set up basic logging so output is visible when run outside the server.
    logging.basicConfig(format=LOG_FORMAT, level=logging.INFO)
    run_cleanup()
