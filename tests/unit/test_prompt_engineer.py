from unittest.mock import patch

from config import PROMPT_ENGINEER_MODEL
from graph.nodes.prompt_engineer import prompt_engineer
from tools.llm import StreamResult

STATE = {
    "current_input": "whats the weather like tmrw",
    "user_id": "u1",
    "message_id": "m1",
}


def _make_result(tokens):
    return StreamResult(model="any", tokens=iter(tokens))


def test_tokens_joined_and_stripped():
    with patch("graph.nodes.prompt_engineer.stream_chat") as mock_stream_chat:
        mock_stream_chat.return_value = _make_result(["  What is ", "the weather tomorrow?  "])
        result = prompt_engineer(STATE)
    assert result == {"engineered_message": "What is the weather tomorrow?"}


def test_exception_returns_current_input_fallback():
    with patch("graph.nodes.prompt_engineer.stream_chat") as mock_stream_chat:
        mock_stream_chat.side_effect = Exception("model down")
        result = prompt_engineer(STATE)
    assert result == {"engineered_message": STATE["current_input"]}


def test_correct_model_passed():
    with patch("graph.nodes.prompt_engineer.stream_chat") as mock_stream_chat:
        mock_stream_chat.return_value = _make_result(["ok"])
        prompt_engineer(STATE)
    # call_args[0] is positional args tuple — [0] is the model name
    assert mock_stream_chat.call_args[0][0] == PROMPT_ENGINEER_MODEL
