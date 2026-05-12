"""graph/nodes/skills.py
SKILLS node — dispatches to user-defined skills in the approved registry.

Phase 3: stub only. Registry is empty — no skills exist yet.
Phase 8: registry populated, ROUTER classifies skill intents, this node
invokes the matching skill function with full state context.
"""

from graph.state import JarvisState


def skills(state: JarvisState) -> dict:
    skill_name = (state.get("current_step") or {}).get("skill_name", "unknown")
    return {
        "step_response": f"Skill '{skill_name}' is not available yet.",
    }
