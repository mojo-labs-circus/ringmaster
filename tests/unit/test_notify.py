import pytest
from unittest.mock import patch

from config import NOTIFY_COOLDOWN_SECONDS
from notifications.notify import notify_admin

_BASE_TIME = 1000.0


@pytest.fixture
def notify_patched():
    with (
        patch("notifications.notify._last_notified", {}),
        patch("notifications.notify.time.monotonic", return_value=_BASE_TIME) as mock_time,
        patch("notifications.notify.logger") as mock_logger,
    ):
        yield mock_time, mock_logger


def test_first_call_fires(notify_patched):
    mock_time, mock_logger = notify_patched
    notify_admin("SomeError", "something happened")
    mock_logger.warning.assert_called_once()


def test_second_call_within_cooldown_suppressed(notify_patched):
    mock_time, mock_logger = notify_patched
    notify_admin("SomeError", "something happened")
    mock_time.return_value = _BASE_TIME + NOTIFY_COOLDOWN_SECONDS - 1
    notify_admin("SomeError", "something happened")
    assert mock_logger.warning.call_count == 1


def test_distinct_pairs_fire_independently(notify_patched):
    mock_time, mock_logger = notify_patched
    notify_admin("ErrorA", "msg1")
    notify_admin("ErrorB", "msg2")
    assert mock_logger.warning.call_count == 2


def test_after_cooldown_fires_again(notify_patched):
    mock_time, mock_logger = notify_patched
    notify_admin("SomeError", "something happened")
    mock_time.return_value = _BASE_TIME + NOTIFY_COOLDOWN_SECONDS + 1
    notify_admin("SomeError", "something happened")
    assert mock_logger.warning.call_count == 2
