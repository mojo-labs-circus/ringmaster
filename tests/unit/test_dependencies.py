import pytest
from unittest.mock import MagicMock, patch
from fastapi import HTTPException

from api.dependencies import (
    ConnectedClient,
    _get_user_from_payload,
    get_connected_client_ws,
    require_admin,
    require_power_or_above,
)


def test_missing_user_id_raises():
    repo = MagicMock()
    with pytest.raises(HTTPException) as exc:
        _get_user_from_payload({"token_version": 1}, repo, 401)
    assert exc.value.status_code == 401


def test_missing_token_version_raises():
    repo = MagicMock()
    with pytest.raises(HTTPException) as exc:
        _get_user_from_payload({"user_id": "u1"}, repo, 401)
    assert exc.value.status_code == 401


def test_user_not_found_raises():
    repo = MagicMock()
    repo.get_user.return_value = None
    with pytest.raises(HTTPException) as exc:
        _get_user_from_payload({"user_id": "u1", "token_version": 1}, repo, 401)
    assert exc.value.status_code == 401


def test_disabled_user_raises():
    repo = MagicMock()
    repo.get_user.return_value = MagicMock(disabled=True)
    with pytest.raises(HTTPException) as exc:
        _get_user_from_payload({"user_id": "u1", "token_version": 1}, repo, 401)
    assert exc.value.status_code == 401


def test_token_version_mismatch_raises():
    repo = MagicMock()
    repo.get_user.return_value = MagicMock(disabled=False, token_version=2)
    with pytest.raises(HTTPException) as exc:
        _get_user_from_payload({"user_id": "u1", "token_version": 1}, repo, 401)
    assert exc.value.status_code == 401


def test_valid_payload_returns_user():
    user = MagicMock(disabled=False, token_version=1)
    repo = MagicMock()
    repo.get_user.return_value = user
    result = _get_user_from_payload({"user_id": "u1", "token_version": 1}, repo, 401)
    assert result is user


def test_invalid_client_type_raises_403():
    with patch("api.dependencies._decode_token") as mock_decode:
        mock_decode.return_value = {"client_type": "invalid", "user_id": "u1", "token_version": 1}
        # websocket and token are passed through to _decode_token which is patched — their values don't matter
        with pytest.raises(HTTPException) as exc:
            get_connected_client_ws(MagicMock(), "tok", MagicMock())
    assert exc.value.status_code == 403


def test_valid_client_type_returns_connected_client():
    user = MagicMock(disabled=False, token_version=1)
    repo = MagicMock()
    repo.get_user.return_value = user
    with patch("api.dependencies._decode_token") as mock_decode:
        mock_decode.return_value = {"client_type": "tui", "user_id": "u1", "token_version": 1}
        # websocket and token are passed through to _decode_token which is patched — their values don't matter
        result = get_connected_client_ws(MagicMock(), "tok", repo)
    assert isinstance(result, ConnectedClient)
    assert result.user is user
    assert result.client_type == "tui"


def test_require_admin_non_admin_raises_403():
    user = MagicMock(tier="power")
    with pytest.raises(HTTPException) as exc:
        require_admin(user)
    assert exc.value.status_code == 403


def test_require_admin_admin_returns_user():
    user = MagicMock(tier="admin")
    assert require_admin(user) is user


def test_require_power_or_above_standard_raises_403():
    user = MagicMock(tier="standard")
    with pytest.raises(HTTPException) as exc:
        require_power_or_above(user)
    assert exc.value.status_code == 403


def test_require_power_or_above_power_returns_user():
    user = MagicMock(tier="power")
    assert require_power_or_above(user) is user
