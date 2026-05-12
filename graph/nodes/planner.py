"""graph/nodes/planner.py
PLANNER node — translates the classified intent list into a concrete
list[Step] execution plan. Runs in two phases: LLM inference produces raw
JSON, then Step construction validates required fields. Each phase has its
own error path so failures are diagnosable.
"""

import json
import logging

from config import PLANNER_MODEL
from graph.state import JarvisState, Step
from tools.llm import stream_chat, extract_json

logger = logging.getLogger(__name__)

_BASE_PROMPT = (
    "You are a planner node. Your job is to read the user's message and a list of "
    "already-classified intents and detected skills, then produce a step plan as a JSON array.\n\n"
    "Each step must have exactly these fields:\n"
    '- "id": short unique identifier (e.g. "add_milk", "search_flights")\n'
    '- "intent": the node to dispatch to — must be one of the classified intents provided\n'
    '- "skill_name": registry name of the skill if intent is "skill", otherwise null\n'
    '- "description": neutral plain-language label for this step\n'
    '- "depends_on": list of step IDs that must succeed before this one runs. Empty list if none.\n\n'
    "Dependency rules:\n"
    "- Create one step per intent type by default — agent nodes handle multiple items within a single step\n"
    "- Only create multiple steps of the same intent type if the message implies a strict ordering "
    "dependency between two distinct operations\n"
    "- A step depends on another when it requires that step's output to execute correctly\n\n"
    "skill_name rules:\n"
    "- Must be null for all non-skill intent steps\n"
    "- For skill intent steps, must be a name from the detected skills list — never invent a name\n\n"
    "Output a JSON array only — no labels, no explanation, no preamble.\n"
    'Example: [{{"id": "add_milk", "intent": "tasks", "skill_name": null, '
    '"description": "Add milk to the task list", "depends_on": []}}]\n\n'
    "Classified intents: {intents_block}\n\n"
    "Detected skills: {skills_block}\n\n"
    "User message: "
)


def planner(state: JarvisState) -> dict:
    """Produce a step-by-step execution plan from the classified intents.

    Two-phase execution: (1) LLM inference produces a raw JSON array, (2) Step
    construction validates each element has the required fields. Phase 1 failure
    (inference or JSON parse error) and Phase 2 failure (missing fields) produce
    distinct error messages so failures are diagnosable.

    Args:
        state: Full JarvisState. Reads intent, detected_skills, engineered_message.

    Returns:
        dict with key "step_plan": list[Step] ready for ORCHESTRATOR.
        On failure: {"error": str}, which routes the request to RESPONDER.

    Side effects:
        Logs an ERROR on both failure paths.
    """
    intents_block = ", ".join(state["intent"]) or "conversation"
    skills_block = ", ".join(state["detected_skills"]) or "None"

    prompt = _BASE_PROMPT.format(
        intents_block=intents_block,
        skills_block=skills_block,
    ) + state["engineered_message"]
    messages = [{"role": "user", "content": prompt}]

    try:
        result = stream_chat(PLANNER_MODEL, messages)
        steps_data = json.loads(extract_json("".join(result.tokens)))
    except Exception:
        logger.error("PLANNER inference or parse failed", exc_info=True)
        return {"error": "PLANNER failed to produce a step plan"}

    try:
        step_plan: list[Step] = [
            Step(
                id=s["id"],
                intent=s["intent"],
                skill_name=s.get("skill_name"),
                description=s["description"],
                depends_on=s.get("depends_on", []),
                prompt="",
            )
            for s in steps_data
        ]
    except (KeyError, TypeError):
        logger.error("PLANNER output missing required fields")
        return {"error": "PLANNER output was malformed"}

    return {"step_plan": step_plan}
