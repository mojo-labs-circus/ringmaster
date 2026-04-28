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
    messages = [{"role": "user", "content": _BASE_PROMPT + state["current_input"]}]
    try:
        result = stream_chat(
            PROMPT_ENGINEER_MODEL,
            messages,
            node="prompt_engineer",
            user_id=state["user_id"],
            message_id=state["message_id"],
        )
        engineered = "".join(result.tokens).strip()
        return {"engineered_message": engineered}
    except Exception:
        logger.warning("PROMPT_ENGINEER inference failed — passing through current_input unchanged")
        return {"engineered_message": state["current_input"]}
