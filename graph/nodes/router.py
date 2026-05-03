"""graph/nodes/router.py
ROUTER node — classifies the engineered message into one or more intents
and checks each against the user's tier. Sets error on state if inference
or JSON parse fails, which routes the request directly to RESPONDER.
"""

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
from tools.llm import stream_chat

logger = logging.getLogger(__name__)

_BASE_PROMPT = (
    "You are a routing node. Your job is to read a user message and classify it into "
    "one or more intents. Output only a JSON object — no labels, no explanation, no preamble.\n\n"
    "Available intents:\n"
    '- "conversation" — general chat, general knowledge questions, and anything that does not fit another intent\n'
    '- "tasks" — creating, updating, completing, listing, or deleting tasks and to-dos\n'
    '- "memory" — explicit requests to query, recall, update, or delete personal information and facts that were previously stored\n'
    '- "web" — requests requiring live or up-to-date data: current weather, breaking news, live prices, recent events. Not general knowledge questions.\n\n'
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
    """Return the skills block for the router prompt.

    Mk1 stub — no skills exist yet. Mk2 reads approved skills from the vault
    and formats them as a bulleted list for the LLM.
    """
    # Mk1 stub — no skills exist yet. Mk2: read from vault procedural/approved/
    return "None"


def _format_history(history: list[dict]) -> str:
    """Format history dicts into a plain-text block for the router prompt.

    Returns "None" when history is empty so the LLM sees an explicit signal
    rather than a blank section.
    """
    if not history:
        return "None"
    lines = []
    for turn in history:
        role = "User" if turn["role"] == "user" else "Assistant"
        lines.append(f"{role}: {turn['content']}")
    return "\n".join(lines)


def router(state: JarvisState) -> dict:
    """Classify the engineered message into intents and check tier access.

    Calls the LLM, parses a JSON object with "intents" and "detected_skills",
    deduplicates intents while preserving order, and computes tier_gate for
    any intent the user's tier cannot access. Sets error on state if the LLM
    call or JSON parse fails.

    Args:
        state: Full JarvisState. Reads engineered_message, user_id, tier.

    Returns:
        dict with keys "intent", "detected_skills", and "tier_gate" on success.
        On failure: {"error": str}, which routes the request to RESPONDER.

    Side effects:
        Logs an ERROR on failure.
    """
    history = get_history(state["user_id"], HISTORY_LIMITS["router"])
    prompt = _BASE_PROMPT.format(
        skills_block=_read_skills(state["user_id"]),
        history_block=_format_history(history),
    ) + state["engineered_message"]
    messages = [{"role": "user", "content": prompt}]

    try:
        result = stream_chat(ROUTER_MODEL, messages)
        parsed = json.loads("".join(result.tokens).strip())
    except Exception:
        logger.error("ROUTER failed")
        return {"error": "ROUTER failed to classify your message"}

    intents = list(dict.fromkeys(parsed.get("intents", ["conversation"])))
    detected_skills = parsed.get("detected_skills", [])

    tier_gate = []
    for intent in intents:
        required = INTENT_TIERS.get(intent, "standard")
        if TIER_RANK[state["tier"]] < TIER_RANK[required]:
            tier_gate.append(intent)

    return {
        "intent": intents,
        "detected_skills": detected_skills,
        "tier_gate": tier_gate,
    }
