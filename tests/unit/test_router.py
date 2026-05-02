from unittest.mock import patch

from graph.nodes.router import _format_history, router
from tools.llm import StreamResult

STATE = {
    "user_id": "u1",
    "message_id": "m1",
    "engineered_message": "what tasks do i have?",
    "tier": "standard",
}

ADMIN_STATE = {**STATE, "tier": "admin"}


def _make_result(tokens):
    return StreamResult(model="any", tokens=iter(tokens))


def test_duplicate_intents_deduplicated():
    # model output is mocked — engineered_message content has no effect on the result
    model_output = '{"intents": ["tasks", "tasks", "conversation"], "detected_skills": []}'
    with patch("graph.nodes.router.stream_chat") as mock_stream_chat, \
         patch("graph.nodes.router.get_history", return_value=[]):
        mock_stream_chat.return_value = _make_result([model_output])
        result = router(STATE)
    assert result["intent"] == ["tasks", "conversation"]


def test_tier_gate_hit_for_standard_user():
    model_output = '{"intents": ["code"], "detected_skills": []}'
    with patch("graph.nodes.router.stream_chat") as mock_stream_chat, \
         patch("graph.nodes.router.get_history", return_value=[]), \
         patch("graph.nodes.router.log_improvement"):
        mock_stream_chat.return_value = _make_result([model_output])
        result = router(STATE)
    assert result["tier_gate"] == ["code"]


def test_tier_gate_empty_for_admin():
    model_output = '{"intents": ["code"], "detected_skills": []}'
    with patch("graph.nodes.router.stream_chat") as mock_stream_chat, \
         patch("graph.nodes.router.get_history", return_value=[]):
        mock_stream_chat.return_value = _make_result([model_output])
        result = router(ADMIN_STATE)
    assert result["tier_gate"] == []


def test_exception_sets_error_on_state():
    with patch("graph.nodes.router.stream_chat") as mock_stream_chat, \
         patch("graph.nodes.router.get_history", return_value=[]), \
         patch("graph.nodes.router.log_improvement"):
        mock_stream_chat.side_effect = Exception("model down")
        result = router(STATE)
    assert "error" in result


def test_exception_calls_log_improvement():
    with patch("graph.nodes.router.stream_chat") as mock_stream_chat, \
         patch("graph.nodes.router.get_history", return_value=[]), \
         patch("graph.nodes.router.log_improvement") as mock_log:
        mock_stream_chat.side_effect = Exception("model down")
        router(STATE)
    mock_log.assert_called_once_with("router_failure", "u1", "m1")


def test_format_history_empty_returns_none():
    assert _format_history([]) == "None"


def test_format_history_formats_turns():
    history = [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi there"},
    ]
    assert _format_history(history) == "User: hello\nAssistant: hi there"
