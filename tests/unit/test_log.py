import json
from unittest.mock import patch

import pytest

from tools.log import log_improvement


@pytest.fixture
def log_entry(tmp_path):
    log_file = str(tmp_path / "improve.jsonl")
    with patch("tools.log.IMPROVE_LOG_PATH", log_file):
        log_improvement("test_event", "user1", "msg1", foo="bar", baz="qux")
    with open(log_file) as f:
        return json.loads(f.read())


def test_entry_has_correct_keys(log_entry):
    assert set(log_entry.keys()) == {"ts", "event", "user_id", "message_id", "data"}


def test_extra_kwargs_land_in_data(log_entry):
    assert log_entry["data"] == {"foo": "bar", "baz": "qux"}


def test_oserror_calls_notify_admin():
    with (
        patch("tools.log.IMPROVE_LOG_PATH", "NON_EXISTANT_PATH/improve.jsonl"),
        patch("tools.log.notify_admin") as mock_notify,
    ):
        log_improvement("test_event", "user1", "msg1")
        mock_notify.assert_called_once()
