import pytest
from unittest.mock import MagicMock, patch

from config import FALLBACK_MODEL, OLLAMA_BASE_URL, OLLAMA_TIMEOUT
from tools.llm import _stream, stream_chat

PRIMARY_MODEL = "llama3:test"
MESSAGES = [{"role": "user", "content": "hello"}]


def test_happy_path_returns_correct_model_and_tokens():
    with patch("tools.llm._stream") as mock_stream:
        mock_stream.return_value = iter(["tok1", "tok2"])
        result = stream_chat(PRIMARY_MODEL, MESSAGES)

    assert result.model == PRIMARY_MODEL
    assert list(result.tokens) == ["tok1", "tok2"]


def test_primary_failure_attempts_fallback():
    with patch("tools.llm._stream") as mock_stream:
        mock_stream.side_effect = [Exception("primary failed"), iter(["fb1", "fb2"])]
        result = stream_chat(PRIMARY_MODEL, MESSAGES)

    assert result.model == FALLBACK_MODEL
    assert list(result.tokens) == ["fb1", "fb2"]


def test_fallback_failure_propagates():
    with patch("tools.llm._stream") as mock_stream:
        mock_stream.side_effect = [Exception("primary failed"), Exception("fallback down")]
        with pytest.raises(Exception, match="fallback down"):
            stream_chat(PRIMARY_MODEL, MESSAGES)


def test_stream_yields_chunk_content():
    chunk1 = MagicMock()
    chunk1.content = "tok1"
    chunk2 = MagicMock()
    chunk2.content = "tok2"
    with patch("tools.llm.ChatOllama") as MockChatOllama:
        mock_instance = MockChatOllama.return_value
        mock_instance.stream.return_value = [chunk1, chunk2]
        tokens = list(_stream("llama3:test", MESSAGES))

    assert tokens == ["tok1", "tok2"]
    MockChatOllama.assert_called_once_with(
        model="llama3:test",
        base_url=OLLAMA_BASE_URL,
        timeout=OLLAMA_TIMEOUT,
    )
    mock_instance.stream.assert_called_once_with(MESSAGES)
