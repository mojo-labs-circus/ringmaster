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

logger = logging.getLogger(__name__)


@dataclass
class StreamResult:
    """Result from a stream_chat call.

    model is the actual model used — may differ from the requested model if
    fallback was triggered. tokens is a generator that yields str chunks as
    they arrive from Ollama; it is not exhausted until iterated.
    """

    model: str
    tokens: Generator


def stream_chat(model: str, messages: list[dict]) -> StreamResult:
    """Stream a chat response from Ollama.

    Tries the requested model first. If it fails for any reason, retries once
    on FALLBACK_MODEL. If that also fails, raises the exception — the node is
    responsible for catching it and setting an error on state.

    Args:
        model: Primary model to call, from config.py (e.g. ROUTER_MODEL).
        messages: List of {"role": ..., "content": ...} dicts to send.

    Returns:
        StreamResult with the actual model used and a token generator. model may
        differ from the requested model if fallback was triggered.

    Raises:
        Exception: Whatever Ollama or LangChain throws, if both primary and
            fallback fail.
    """
    try:
        return StreamResult(model=model, tokens=_stream(model, messages))
    except Exception:
        logger.warning("Model %s failed, retrying with fallback %s", model, FALLBACK_MODEL)

    # Fallback attempt — let any exception propagate to the caller
    return StreamResult(model=FALLBACK_MODEL, tokens=_stream(FALLBACK_MODEL, messages))


def extract_json(text: str) -> str:
    """Extract the JSON value from LLM output.

    Handles fences, leading prose, and trailing prose by slicing directly
    to the outermost { } or [ ] boundary.
    """
    brace = text.find("{")
    bracket = text.find("[")

    if brace == -1 and bracket == -1:
        return text

    if brace == -1 or (bracket != -1 and bracket < brace):
        return text[bracket : text.rfind("]") + 1]
    else:
        return text[brace : text.rfind("}") + 1]


def _stream(model: str, messages: list[dict]) -> Generator[str, None, None]:
    """Open a ChatOllama streaming session and yield content chunks.

    Raises whatever exception Ollama or LangChain throws — stream_chat catches
    the first failure and retries with the fallback model.
    """
    llm = ChatOllama(model=model, base_url=OLLAMA_BASE_URL, timeout=OLLAMA_TIMEOUT)
    for chunk in llm.stream(messages):
        yield chunk.content
