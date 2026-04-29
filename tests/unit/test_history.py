from unittest.mock import MagicMock, patch

from tools.history import get_history


def test_returns_last_limit_items():
    mock_repo = MagicMock()
    mock_repo.load.return_value = [{"role": "user", "content": f"msg{i}"} for i in range(10)]
    with patch("tools.history._repo", mock_repo):
        result = get_history("user1", 3)
    assert result == [
        {"role": "user", "content": "msg7"},
        {"role": "user", "content": "msg8"},
        {"role": "user", "content": "msg9"},
    ]


def test_returns_full_list_when_limit_exceeds_length():
    mock_repo = MagicMock()
    mock_repo.load.return_value = [{"role": "user", "content": "msg0"}]
    with patch("tools.history._repo", mock_repo):
        result = get_history("user1", 100)
    assert result == [{"role": "user", "content": "msg0"}]


def test_returns_empty_on_exception():
    mock_repo = MagicMock()
    mock_repo.load.side_effect = Exception("DB error")
    with patch("tools.history._repo", mock_repo):
        result = get_history("user1", 10)
    assert result == []
