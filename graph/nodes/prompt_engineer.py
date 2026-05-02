"""graph/nodes/prompt_engineer.py
First node in the JARVIS graph. Cleans and normalises the raw user message
before any reasoning takes place. Output lives in state["engineered_message"]
and is used by all downstream nodes in place of current_input.
"""

import logging

from config import PROMPT_ENGINEER_MODEL
from graph.state import JarvisState
from tools.llm import stream_chat

logger = logging.getLogger(__name__)

_BASE_PROMPT = (
    "You are a prompt engineer. Your job is to fix spelling and grammar, normalise "
    "informal or colloquial language into clear phrasing, and restructure fragmented "
    "or incomplete sentences into well-formed prompts. Do not resolve implicit "
    "references or add context from outside the message. Do not answer the prompt — "
    "only rewrite it. Do not change the meaning or add information not present in "
    "the original. Output the rewritten prompt only — no labels, no quotes, no preamble.\n\n"
    "Unprocessed prompt: "
)


def prompt_engineer(state: JarvisState) -> dict:
    """Clean and normalise the user's raw message via LLM inference.

    Corrects spelling, grammar, and informal phrasing without changing meaning
    or resolving implicit references. On inference failure, falls back to passing
    current_input through unchanged so the graph can continue uninterrupted.

    Args:
        state: Full JarvisState. Reads current_input.

    Returns:
        dict with key "engineered_message" — the cleaned prompt, or current_input
        verbatim if inference failed.

    Side effects:
        Logs a WARNING on inference failure. Never raises.
    """
    messages = [{"role": "user", "content": _BASE_PROMPT + state["current_input"]}]
    try:
        result = stream_chat(PROMPT_ENGINEER_MODEL, messages)
        engineered = "".join(result.tokens).strip()
        return {"engineered_message": engineered}
    except Exception:
        logger.warning("PROMPT_ENGINEER inference failed — passing through current_input unchanged")
        return {"engineered_message": state["current_input"]}
