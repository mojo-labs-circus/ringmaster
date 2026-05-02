import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock

from api import connections
from api.connections import deregister, push_profile, register
from api.dependencies import ConnectedClient


@pytest.fixture(autouse=True)
def clear_registry():
    connections._registry.clear()
    yield
    connections._registry.clear()


def _make_client():
    return ConnectedClient(user=MagicMock(), client_type="tui", websocket=AsyncMock())


def test_register_adds_client():
    client = _make_client()
    register("u1", client)
    assert connections._registry["u1"] == [client]


def test_register_appends_second_client():
    client_a = _make_client()
    client_b = _make_client()
    register("u1", client_a)
    register("u1", client_b)
    assert connections._registry["u1"] == [client_a, client_b]


def test_deregister_removes_last_client_and_deletes_entry():
    client = _make_client()
    register("u1", client)
    deregister("u1", client)
    assert "u1" not in connections._registry


def test_deregister_one_of_two_clients_keeps_other():
    client_a = _make_client()
    client_b = _make_client()
    register("u1", client_a)
    register("u1", client_b)
    deregister("u1", client_a)
    assert connections._registry["u1"] == [client_b]


def test_deregister_unknown_user_is_noop():
    client = _make_client()
    deregister("unknown", client)  # should not raise


def test_push_profile_sends_correct_frame_to_all_clients():
    client_a = _make_client()
    client_b = _make_client()
    register("u1", client_a)
    register("u1", client_b)
    asyncio.run(push_profile("u1"))
    expected = {"type": "profile", "message_id": "__push__"}
    client_a.websocket.send_json.assert_called_once_with(expected)
    client_b.websocket.send_json.assert_called_once_with(expected)


def test_push_profile_dead_connection_swallowed_and_continues():
    client_a = _make_client()
    client_b = _make_client()
    client_a.websocket.send_json.side_effect = Exception("dead")
    register("u1", client_a)
    register("u1", client_b)
    asyncio.run(push_profile("u1"))  # should not raise
    client_b.websocket.send_json.assert_called_once_with({"type": "profile", "message_id": "__push__"})


def test_push_profile_unknown_user_is_noop():
    asyncio.run(push_profile("unknown"))  # should not raise
