import json
import logging

from config import (
    HISTORY_LIMITS,
    INTENT_TIERS,
    ROUTER_MODEL,
    TIER_RANK,
)
from graph.state import JarvisState
from tools.history import get_history
from tools.log import log_improvement
from tools.llm import stream_chat

logger = logging.getLogger(__name__)

_BASE_PROMPT = (
    "You are a routing node. Your job is to read a user message and classify it into "
    "one or more intents. Output only a JSON object — no labels, no explanation, no preamble.\n\n"
    "Available intents:\n"
    '- "conversation" — general chat, questions, anything that does not fit another intent\n'
    '- "tasks" — creating, updating, completing, listing, or deleting tasks and to-dos\n'
    '- "memory" — explicit requests to query, recall, or delete stored memories\n'
    '- "web" — requests that require searching the internet for current information\n\n'
    "If the user's message matches one of the available intents, add it to the intents list. "
    "A message may have more than one intent.\n\n"
    "Available skills (may be empty):\n"
    "{skills_block}\n\n"
    "If the user's message matches a listed skill, add \"skill\" to the intents list and "
    "add the skill name to detected_skills. If no skills are listed or none match, "
    "detected_skills must be empty.\n\n"
    'Output format — strictly JSON, nothing else:\n{{"intents": ["conversation"], "detected_skills": []}}\n\n'
    "Recent conversation history:\n"
    "{history_block}\n\n"
    "Current message: "
)


def _read_skills(user_id: str) -> str:
    # Mk1 stub — no skills exist yet. Mk2: read from vault procedural/approved/
    return "None"


def _format_history(history: list[dict]) -> str:
    if not history:
        return "None"
    lines = []
    for turn in history:
        role = "User" if turn["role"] == "user" else "Assistant"
        lines.append(f"{role}: {turn['content']}")
    return "\n".join(lines)


def router(state: JarvisState) -> dict:
    history = get_history(state["user_id"], HISTORY_LIMITS["router"])
    prompt = _BASE_PROMPT.format(
        skills_block=_read_skills(state["user_id"]),
        history_block=_format_history(history),
    ) + state["engineered_message"]
    messages = [{"role": "user", "content": prompt}]

    try:
        result = stream_chat(
            ROUTER_MODEL, messages,
            node="router", user_id=state["user_id"], message_id=state["message_id"],
        )
        parsed = json.loads("".join(result.tokens).strip())
    except Exception:
        logger.error("ROUTER failed")
        log_improvement("router_failure", state["user_id"], state["message_id"])
        return {"error": "ROUTER failed to classify your message"}

    intents = list(dict.fromkeys(parsed.get("intents", ["conversation"])))
    detected_skills = parsed.get("detected_skills", [])

    tier_gate = []
    for intent in intents:
        required = INTENT_TIERS.get(intent, "standard")
        if TIER_RANK[state["tier"]] < TIER_RANK[required]:
            tier_gate.append(intent)
            log_improvement("tier_gate_hit", state["user_id"], state["message_id"], intent=intent)

    return {
        "intent": intents,
        "detected_skills": detected_skills,
        "tier_gate": tier_gate,
    }
