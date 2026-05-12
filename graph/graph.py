"""graph/graph.py
Wires the JARVIS nodes into a compiled LangGraph graph.

Mk1 stub — a single node returns a hardcoded response so the full
WebSocket pipeline (auth, history, frame contract) can be verified before
real nodes are wired in. Replace stub_node with real nodes as each is built.

Wiring notes for when real nodes are added:
- START → PROMPT_ENGINEER (normal path) or RESPONDER (when state["correction"] is set)
- PROMPT_ENGINEER → ROUTER → PLANNER → DECOMPOSER → ORCHESTRATOR
- ORCHESTRATOR → CONVERSATION | TASKS | WEB | MEMORY | SYSTEM | CODE for built-in intents
- ORCHESTRATOR → SKILLS when current_step.intent == "skill"
- Any top-level node setting error → RESPONDER (universal error edge)
- Agent nodes dispatched by ORCHESTRATOR always route back to ORCHESTRATOR regardless of error
"""

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from graph.nodes.skills import skills
from graph.state import JarvisState


def _stub_node(state: JarvisState) -> dict:
    # Placeholder until real nodes exist — sets the two fields FastAPI reads
    # after the graph completes: assembled_response and refresh.
    return {
        "assembled_response": "[JARVIS stub] Graph not yet wired.",
        "refresh": [],
    }


def _build_graph() -> CompiledStateGraph:
    builder = StateGraph(JarvisState)
    builder.add_node("stub_node", _stub_node)
    builder.add_node("skills", skills)
    # skills node is wired by ORCHESTRATOR conditional edge — not connected in stub
    builder.add_edge(START, "stub_node")
    builder.add_edge("stub_node", END)
    return builder.compile()


# Module-level compiled graph — imported by chat.py.
# Re-compiling on every request would be expensive; compile once at startup.
jarvis_graph = _build_graph()
