"""graph/graph.py
Wires the JARVIS nodes together into a LangGraph graph.
Flow: START → router → memory → responder → END"""

from langgraph.graph import StateGraph, START, END
from graph.state import JarvisState
from graph.nodes import router_node, memory_node, responder_node
from langgraph.graph.state import CompiledStateGraph

def build_graph() -> CompiledStateGraph:
    """Builds and compiles the JARVIS LangGraph graph."""
    graph = StateGraph(JarvisState)

    graph.add_node("router", router_node)
    graph.add_node("memory", memory_node)
    graph.add_node("responder", responder_node)

    graph.add_edge(START, "router")
    graph.add_edge("router", "memory")
    graph.add_edge("memory", "responder")
    graph.add_edge("responder", END)

    return graph.compile()

jarvis_graph = build_graph()