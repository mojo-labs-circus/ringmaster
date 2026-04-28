"""tools/llm.py
Single point of contact for all Ollama inference.
Nodes never instantiate ChatOllama directly — they call stream_chat() and
iterate the returned tokens.
"""

import logging
from dataclasses import dataclass
from typing import Generator

from langchain_ollama import ChatOllama

from config import FALLBACK_MODEL, OLLAMA_BASE_URL, OLLAMA_TIMEOUT
from tools.log import log_improvement

logger = logging.getLogger(__name__)


@dataclass
class StreamResult:
    model: str
    tokens: Generator


def stream_chat(
    model: str,
    messages: list[dict],
    *,
    node: str,
    user_id: str,
    message_id: str,
) -> StreamResult:
    """Stream a chat response from Ollama.

    Tries the requested model first. If it fails for any reason, retries once
    on FALLBACK_MODEL. If that also fails, raises the exception — the node is
    responsible for catching it and setting an error on state.

    Returns a StreamResult so the caller always knows which model was actually
    used — nodes can surface this in a status frame for admin users.
    """
    try:
        return StreamResult(model=model, tokens=_stream(model, messages))
    except Exception as exc:
        logger.warning("Model %s failed, retrying with fallback %s", model, FALLBACK_MODEL)
        log_improvement(
            "model_fallback",
            user_id,
            message_id,
            node=node,
            primary_model=model,
            fallback_model=FALLBACK_MODEL,
            failure_reason=type(exc).__name__,
        )

    # Fallback attempt — let any exception propagate to the caller
    return StreamResult(model=FALLBACK_MODEL, tokens=_stream(FALLBACK_MODEL, messages))


def _stream(model: str, messages: list[dict]) -> Generator[str, None, None]:
    """Open a streaming connection to Ollama and yield tokens as they arrive."""
    llm = ChatOllama(model=model, base_url=OLLAMA_BASE_URL, timeout=OLLAMA_TIMEOUT)
    for chunk in llm.stream(messages):
        yield chunk.content
